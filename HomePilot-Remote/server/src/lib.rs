//! HomePilot Remote 중계 서버 (라이브러리).
//!
//! - PC 에이전트와 휴대폰이 모두 "바깥으로" 이 서버에 접속하므로 공유기 포트 개방이 필요 없다.
//! - 서버는 종단간 암호문을 그대로 넘겨줄 뿐, 화면·입력·키를 볼 수도 저장할 수도 없다.
//! - 단독 실행(homepilot-relay) 또는 에이전트 내장(집 PC 에서 Cloudflare 터널과 함께) 두 방식으로 쓴다.

use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::{ConnectInfo, Path, State};
use axum::http::{HeaderMap, StatusCode};
use axum::response::IntoResponse;
use axum::routing::get;
use axum::Router;
use futures_util::{SinkExt, StreamExt};
use homepilot_protocol::relay::{decode_agent_frame, encode_agent_frame, is_valid_device_id, AgentToRelay, RelayToAgent, RelayToClient};
use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tokio::net::TcpListener;
use tokio::sync::mpsc;

/// 에이전트 등록 시 확인하는 헤더. 설정되어 있으면 이 값을 아는 에이전트만 PC 로 등록할 수 있다
/// (공개된 중계 서버에서 남이 같은 장치 ID 로 끼어들어 연결을 방해하는 것을 막음).
pub const AGENT_TOKEN_HEADER: &str = "x-homepilot-agent-token";

#[derive(Clone, Default)]
pub struct RelayConfig {
    pub agent_token: Option<String>,
}

/// 중계 서버 실행 (끝나지 않음).
pub async fn serve(listener: TcpListener, config: RelayConfig) -> anyhow::Result<()> {
    let state: AppState = Arc::new(Relay { config, ..Default::default() });
    let app = Router::new()
        .route("/healthz", get(|| async { "ok" }))
        .route("/v1/agent/:device_id", get(agent_ws))
        .route("/v1/client/:device_id", get(client_ws))
        .with_state(state);
    axum::serve(listener, app.into_make_service_with_connect_info::<SocketAddr>()).await?;
    Ok(())
}

fn token_ok(expected: &Option<String>, headers: &HeaderMap) -> bool {
    let Some(exp) = expected else { return true };
    let got = headers.get(AGENT_TOKEN_HEADER).map(|v| v.as_bytes()).unwrap_or_default();
    // 길이·내용 비교를 일정 시간에 (타이밍 공격 방지)
    got.len() == exp.len() && got.iter().zip(exp.as_bytes()).fold(0u8, |a, (x, y)| a | (x ^ y)) == 0
}

/// 한 PC 에 동시에 붙을 수 있는 휴대폰 수.
const MAX_CLIENTS_PER_DEVICE: usize = 4;
/// 메시지 최대 크기 (화면 프레임 포함).
const MAX_MESSAGE: usize = 16 * 1024 * 1024;
/// 휴대폰 → PC 메시지 최대 크기. 입력·제어는 작지만, 파일 보내기 조각(192KB, base64 로 약 256KB)을
/// 담을 수 있어야 한다. 남용을 막기 위해 PC 쪽(16MB)보다 훨씬 작게 둔다.
const MAX_CLIENT_MESSAGE: usize = 1024 * 1024;

struct AgentConn {
    generation: u64,
    tx: mpsc::Sender<Message>,
    next_sid: u32,
    clients: HashMap<u32, mpsc::Sender<Message>>,
}

#[derive(Default)]
struct Relay {
    config: RelayConfig,
    agents: Mutex<HashMap<String, AgentConn>>,
    generation: AtomicU64,
}

type AppState = Arc<Relay>;

async fn agent_ws(
    ws: WebSocketUpgrade,
    Path(id): Path<String>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    headers: HeaderMap,
    State(st): State<AppState>,
) -> impl IntoResponse {
    if !is_valid_device_id(&id) {
        return (StatusCode::BAD_REQUEST, "invalid device id").into_response();
    }
    if !token_ok(&st.config.agent_token, &headers) {
        tracing::warn!(device = %id, %addr, "에이전트 토큰 불일치 → 거부");
        return (StatusCode::UNAUTHORIZED, "agent token required").into_response();
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
        return (StatusCode::BAD_REQUEST, "invalid device id").into_response();
    }
    ws.max_message_size(MAX_CLIENT_MESSAGE).on_upgrade(move |s| handle_client(s, id, addr, st))
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
