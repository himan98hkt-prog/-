//! 중계 서버 연결 유지. PC 가 바깥으로 연결을 거는 방식이라 공유기 포트 개방이 필요 없다.
//! 끊기면 1초부터 최대 60초까지 늘려 가며 재연결한다.

use crate::app::Shared;
use crate::session;
use anyhow::{bail, Context, Result};
use futures_util::{SinkExt, StreamExt};
use homepilot_protocol::relay::{decode_agent_frame, AgentToRelay, RelayToAgent};
use std::collections::HashMap;
use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::mpsc;
use tokio_tungstenite::tungstenite::Message;

pub enum Outgoing {
    Text(String),
    Binary(Vec<u8>),
}

pub type OutTx = mpsc::Sender<Outgoing>;

pub async fn run_forever(shared: Arc<Shared>) {
    let mut backoff = 1u64;
    loop {
        let started = Instant::now();
        match connect_once(&shared).await {
            Ok(()) => tracing::info!("중계 서버 연결 종료"),
            Err(e) => tracing::warn!("중계 서버 연결 오류: {e:#}"),
        }
        shared.relay_online.store(false, Ordering::Relaxed);
        shared.end_all_sessions("PC 의 네트워크 연결이 끊겼습니다");
        shared.refresh_ui();
        if started.elapsed() > Duration::from_secs(60) {
            backoff = 1;
        }
        let jitter = rand::random::<u64>() % 500;
        tracing::info!("{backoff}초 후 재연결");
        tokio::time::sleep(Duration::from_millis(backoff * 1000 + jitter)).await;
        backoff = (backoff * 2).min(60);
    }
}

async fn connect_once(shared: &Arc<Shared>) -> Result<()> {
    let relay = shared.config.lock().unwrap().relay_url.clone();
    let base = url::Url::parse(relay.trim_end_matches('/')).context("중계 서버 주소 형식 오류")?;
    if !matches!(base.scheme(), "ws" | "wss") {
        bail!("중계 서버 주소는 ws:// 또는 wss:// 로 시작해야 합니다");
    }
    let url = format!("{}/v1/agent/{}", relay.trim_end_matches('/'), shared.device_id);
    tracing::info!("중계 서버 연결 시도: {url}");
    let (ws, _) = tokio::time::timeout(Duration::from_secs(15), tokio_tungstenite::connect_async(url.as_str()))
        .await
        .context("연결 시간 초과")?
        .context("연결 실패")?;
    shared.relay_online.store(true, Ordering::Relaxed);
    shared.refresh_ui();
    tracing::info!("중계 서버 연결됨 (장치 ID {})", shared.device_id);

    let (mut sink, mut stream) = ws.split();
    let (out_tx, mut out_rx) = mpsc::channel::<Outgoing>(64);
    let writer = tokio::spawn(async move {
        while let Some(o) = out_rx.recv().await {
            let m = match o {
                Outgoing::Text(t) => Message::Text(t),
                Outgoing::Binary(b) => Message::Binary(b),
            };
            if sink.send(m).await.is_err() {
                break;
            }
        }
        let _ = sink.close().await;
    });

    let mut sessions: HashMap<u32, mpsc::Sender<Vec<u8>>> = HashMap::new();
    let result = loop {
        // 중계 서버는 20초마다 Ping 을 보낸다. 90초간 아무것도 없으면 끊긴 것으로 본다.
        let msg = match tokio::time::timeout(Duration::from_secs(90), stream.next()).await {
            Err(_) => break Err(anyhow::anyhow!("중계 서버 응답 없음")),
            Ok(None) => break Ok(()),
            Ok(Some(Err(e))) => break Err(e.into()),
            Ok(Some(Ok(m))) => m,
        };
        match msg {
            Message::Text(t) => match serde_json::from_str::<RelayToAgent>(&t) {
                Ok(RelayToAgent::Open { sid }) => {
                    let limit = shared.config.lock().unwrap().max_sessions as usize;
                    sessions.retain(|_, tx| !tx.is_closed());
                    if sessions.len() >= limit {
                        tracing::warn!("동시 세션 한도({limit}) 초과 → 거절");
                        let _ = out_tx.send(Outgoing::Text(serde_json::to_string(&AgentToRelay::Kick { sid })?)).await;
                        continue;
                    }
                    let (tx, rx) = mpsc::channel(64);
                    sessions.insert(sid, tx);
                    tokio::spawn(session::run(shared.clone(), sid, rx, out_tx.clone()));
                }
                Ok(RelayToAgent::Close { sid }) => {
                    sessions.remove(&sid);
                }
                Ok(RelayToAgent::Ping) => {
                    let _ = out_tx.send(Outgoing::Text(serde_json::to_string(&AgentToRelay::Pong)?)).await;
                }
                Ok(RelayToAgent::Registered { device_id }) => tracing::debug!("등록 확인: {device_id}"),
                Err(e) => tracing::warn!("알 수 없는 중계 메시지: {e}"),
            },
            Message::Binary(b) => {
                let Some((sid, payload)) = decode_agent_frame(&b) else { continue };
                if let Some(tx) = sessions.get(&sid) {
                    // 입력 메시지가 유실되지 않도록 기다려서 넣되, 멈춘 세션 때문에 전체가 막히지 않게 제한.
                    let r = tokio::time::timeout(Duration::from_secs(2), tx.send(payload.to_vec())).await;
                    if !matches!(r, Ok(Ok(()))) {
                        sessions.remove(&sid);
                    }
                }
            }
            Message::Close(_) => break Ok(()),
            _ => {}
        }
    };
    drop(sessions);
    drop(out_tx);
    writer.abort();
    result
}
