//! HomePilot Remote 중계 서버 (Phase 1 개발용 최소 구현).
//!
//! - PC 에이전트와 휴대폰이 모두 "바깥으로" 이 서버에 접속하므로 공유기 포트 개방이 필요 없다.
//! - 서버는 종단간 암호문을 그대로 넘겨줄 뿐, 화면·입력·키를 볼 수도 저장할 수도 없다.
//! - 계정 인증, 다중 인증(MFA), 기기 소유 증명, 속도 제한, TLS 종단은 Phase 3 에서 추가한다.
//!   운영 환경에서는 반드시 TLS 리버스 프록시(예: Caddy) 뒤에 두고 wss:// 로 접속한다.

use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::{ConnectInfo, Path, State};
use axum::response::IntoResponse;
use axum::routing::get;
use axum::Router;
use clap::Parser;
use futures_util::{SinkExt, StreamExt};
use homepilot_protocol::relay::{decode_agent_frame, encode_agent_frame, is_valid_device_id, AgentToRelay, RelayToAgent, RelayToClient};
use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tokio::sync::mpsc;

/// 한 PC 에 동시에 붙을 수 있는 휴대폰 수.
const MAX_CLIENTS_PER_DEVICE: usize = 4;
/// 메시지 최대 크기 (화면 프레임 포함).
const MAX_MESSAGE: usize = 16 * 1024 * 1024;

#[derive(Parser)]
#[command(name = "homepilot-relay", version, about = "HomePilot Remote 중계 서버")]
struct Args {
    /// 수신 주소
    #[arg(long, default_value = "127.0.0.1:8443")]
    listen: SocketAddr,
}

struct AgentConn {
    generation: u64,
    tx: mpsc::Sender<Message>,
    next_sid: u32,
    clients: HashMap<u32, mpsc::Sender<Message>>,
}

#[derive(Default)]
struct Relay {
    agents: Mutex<HashMap<String, AgentConn>>,
    generation: AtomicU64,
}

type AppState = Arc<Relay>;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::try_from_env("HOMEPILOT_LOG").unwrap_or_else(|_| "info".into()))
        .init();
    let args = Args::parse();
    let state: AppState = Arc::new(Relay::default());
    let app = Router::new()
        .route("/healthz", get(|| async { "ok" }))
        .route("/v1/agent/:device_id", get(agent_ws))
        .route("/v1/client/:device_id", get(client_ws))
        .with_state(state);
    let listener = tokio::net::TcpListener::bind(args.listen).await?;
    tracing::info!("중계 서버 시작: {}", args.listen);
    axum::serve(listener, app.into_make_service_with_connect_info::<SocketAddr>()).await?;
    Ok(())
}

async fn agent_ws(
    ws: WebSocketUpgrade,
    Path(id): Path<String>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    State(st): State<AppState>,
) -> impl IntoResponse {
    if !is_valid_device_id(&id) {
        return (axum::http::StatusCode::BAD_REQUEST, "invalid device id").into_response();
    }
    ws.max_message_size(MAX_MESSAGE).on_upgrade(move |s| handle_agent(s, id, addr, st))
}

async fn client_ws(
    ws: WebSocketUpgrade,
    Path(id): Path<String>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    State(st): State<AppState>,
) -> impl IntoResponse {
    if !is_valid_device_id(&id) {
        return (axum::http::StatusCode::BAD_REQUEST, "invalid device id").into_response();
    }
    ws.max_message_size(64 * 1024).on_upgrade(move |s| handle_client(s, id, addr, st))
}

fn text<T: serde::Serialize>(v: &T) -> Message {
    Message::Text(serde_json::to_string(v).expect("직렬화"))
}

/// 소켓 쓰기 전용 작업. 채널이 닫히면 소켓도 닫는다.
fn spawn_writer(mut sink: futures_util::stream::SplitSink<WebSocket, Message>, cap: usize) -> mpsc::Sender<Message> {
    let (tx, mut rx) = mpsc::channel::<Message>(cap);
    tokio::spawn(async move {
        while let Some(m) = rx.recv().await {
            if sink.send(m).await.is_err() {
                break;
            }
        }
        let _ = sink.close().await;
    });
    tx
}

async fn handle_agent(socket: WebSocket, id: String, addr: SocketAddr, st: AppState) {
    let (sink, mut stream) = socket.split();
    let tx = spawn_writer(sink, 256);
    let generation = st.generation.fetch_add(1, Ordering::Relaxed);
    {
        let mut agents = st.agents.lock().unwrap();
        if let Some(old) = agents.remove(&id) {
            // 같은 PC 가 다시 접속: 이전(끊긴 것으로 보이는) 연결을 정리한다.
            tracing::info!(device = %id, "이전 에이전트 연결 교체");
            for c in old.clients.values() {
                let _ = c.try_send(text(&RelayToClient::AgentGone));
                let _ = c.try_send(Message::Close(None));
            }
        }
        agents.insert(id.clone(), AgentConn { generation, tx: tx.clone(), next_sid: 1, clients: HashMap::new() });
    }
    tracing::info!(device = %id, %addr, "에이전트 온라인");
    let _ = tx.send(text(&RelayToAgent::Registered { device_id: id.clone() })).await;

    let mut ping = tokio::time::interval(Duration::from_secs(20));
    loop {
        tokio::select! {
            _ = ping.tick() => {
                if tx.send(text(&RelayToAgent::Ping)).await.is_err() { break; }
            }
            m = tokio::time::timeout(Duration::from_secs(90), stream.next()) => {
                let m = match m {
                    Ok(Some(Ok(m))) => m,
                    _ => break,
                };
                match m {
                    Message::Binary(b) => {
                        let Some((sid, payload)) = decode_agent_frame(&b) else { continue };
                        let client = st.agents.lock().unwrap().get(&id).and_then(|a| a.clients.get(&sid).cloned());
                        if let Some(c) = client {
                            // 느린 휴대폰 하나 때문에 PC 전체가 막히지 않도록 제한 시간을 둔다.
                            if tokio::time::timeout(Duration::from_secs(5), c.send(Message::Binary(payload.to_vec()))).await.is_err() {
                                tracing::warn!(device = %id, sid, "휴대폰 수신 지연 → 연결 종료");
                                drop_client(&st, &id, sid);
                            }
                        }
                    }
                    Message::Text(t) => match serde_json::from_str::<AgentToRelay>(&t) {
                        Ok(AgentToRelay::Kick { sid }) => drop_client(&st, &id, sid),
                        Ok(AgentToRelay::Pong) => {}
                        Err(_) => tracing::debug!(device = %id, "알 수 없는 에이전트 메시지"),
                    },
                    Message::Close(_) => break,
                    _ => {}
                }
            }
        }
    }
    let mut agents = st.agents.lock().unwrap();
    if agents.get(&id).is_some_and(|a| a.generation == generation) {
        if let Some(a) = agents.remove(&id) {
            for c in a.clients.values() {
                let _ = c.try_send(text(&RelayToClient::AgentGone));
                let _ = c.try_send(Message::Close(None));
            }
        }
    }
    tracing::info!(device = %id, "에이전트 오프라인");
}

fn drop_client(st: &AppState, id: &str, sid: u32) {
    let mut agents = st.agents.lock().unwrap();
    if let Some(a) = agents.get_mut(id) {
        if let Some(c) = a.clients.remove(&sid) {
            let _ = c.try_send(Message::Close(None));
            let _ = a.tx.try_send(text(&RelayToAgent::Close { sid }));
        }
    }
}

async fn handle_client(socket: WebSocket, id: String, addr: SocketAddr, st: AppState) {
    let (sink, mut stream) = socket.split();
    let tx = spawn_writer(sink, 8);
    let opened = {
        let mut agents = st.agents.lock().unwrap();
        match agents.get_mut(&id) {
            None => None,
            Some(a) if a.clients.len() >= MAX_CLIENTS_PER_DEVICE => Some(Err(())),
            Some(a) => {
                let sid = a.next_sid;
                a.next_sid = a.next_sid.wrapping_add(1).max(1);
                a.clients.insert(sid, tx.clone());
                Some(Ok((sid, a.tx.clone(), a.generation)))
            }
        }
    };
    let (sid, agent_tx, generation) = match opened {
        None => {
            let _ = tx.send(text(&RelayToClient::Offline)).await;
            return;
        }
        Some(Err(())) => {
            tracing::warn!(device = %id, %addr, "동시 접속 한도 초과");
            let _ = tx.send(Message::Close(None)).await;
            return;
        }
        Some(Ok(v)) => v,
    };
    tracing::info!(device = %id, %addr, sid, "휴대폰 연결");
    let _ = agent_tx.send(text(&RelayToAgent::Open { sid })).await;
    let _ = tx.send(text(&RelayToClient::Connected)).await;

    while let Ok(Some(Ok(m))) = tokio::time::timeout(Duration::from_secs(120), stream.next()).await {
        match m {
            Message::Binary(b) => {
                if agent_tx.send(Message::Binary(encode_agent_frame(sid, &b))).await.is_err() {
                    break;
                }
            }
            Message::Close(_) => break,
            _ => {}
        }
    }
    tracing::info!(device = %id, sid, "휴대폰 연결 종료");
    let mut agents = st.agents.lock().unwrap();
    if let Some(a) = agents.get_mut(&id) {
        if a.generation == generation && a.clients.remove(&sid).is_some() {
            let _ = a.tx.try_send(text(&RelayToAgent::Close { sid }));
        }
    }
}
