//! 휴대폰 한 대와의 세션: 핸드셰이크 → 기기 인증/등록 → 명령 처리.

use crate::app::{SessionView, Shared};
use crate::input;
use crate::net::{OutTx, Outgoing};
use crate::platform::{self, Input};
use crate::stream::{self, StreamHandle, StreamParams};
use anyhow::{anyhow, bail, Context, Result};
use homepilot_protocol::app::{self as proto, AgentMsg, ClientMsg, Decoded, MonitorInfo, Permissions};
use homepilot_protocol::relay::{encode_agent_frame, AgentToRelay};
use homepilot_protocol::secure::{fingerprint, Handshake, Opener, Sealer};
use homepilot_protocol::PROTOCOL_VERSION;
use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::{mpsc, watch};

const HANDSHAKE_TIMEOUT: Duration = Duration::from_secs(15);
const APPROVAL_TIMEOUT: Duration = Duration::from_secs(120);
const IDLE_TIMEOUT: Duration = Duration::from_secs(45);
/// 응답(ack) 없이 보낼 수 있는 화면 프레임 수.
const MAX_IN_FLIGHT: u32 = 2;

struct Wire {
    sid: u32,
    out: OutTx,
    sealer: Sealer,
}

impl Wire {
    async fn raw(&self, payload: Vec<u8>) -> Result<()> {
        self.out.send(Outgoing::Binary(encode_agent_frame(self.sid, &payload))).await.map_err(|_| anyhow!("중계 연결 끊김"))
    }
    async fn send_plain(&mut self, plaintext: &[u8]) -> Result<()> {
        let ct = self.sealer.seal(plaintext)?;
        self.raw(ct).await
    }
    async fn send(&mut self, msg: &AgentMsg) -> Result<()> {
        self.send_plain(&proto::encode_control(msg)).await
    }
    async fn kick(&self) {
        if let Ok(t) = serde_json::to_string(&AgentToRelay::Kick { sid: self.sid }) {
            let _ = self.out.send(Outgoing::Text(t)).await;
        }
    }
}

async fn recv_timeout(inbox: &mut mpsc::Receiver<Vec<u8>>, d: Duration) -> Result<Vec<u8>> {
    tokio::time::timeout(d, inbox.recv()).await.context("응답 시간 초과")?.ok_or_else(|| anyhow!("상대가 연결을 끊음"))
}

fn decode_client(opener: &mut Opener, ct: &[u8]) -> Result<ClientMsg> {
    let pt = opener.open(ct)?;
    match proto::decode::<ClientMsg>(&pt)? {
        Decoded::Control(m) => Ok(m),
        Decoded::Frame(..) => bail!("클라이언트는 프레임을 보낼 수 없음"),
    }
}

pub async fn run(shared: Arc<Shared>, sid: u32, inbox: mpsc::Receiver<Vec<u8>>, out: OutTx) {
    let (id, cancel) = shared.register_session();
    if let Err(e) = run_inner(&shared, id, sid, inbox, out.clone(), cancel).await {
        tracing::info!(sid, "세션 종료: {e:#}");
    }
    shared.unregister_session(id);
    if let Ok(t) = serde_json::to_string(&AgentToRelay::Kick { sid }) {
        let _ = out.send(Outgoing::Text(t)).await;
    }
}

async fn run_inner(
    shared: &Arc<Shared>,
    id: u64,
    sid: u32,
    mut inbox: mpsc::Receiver<Vec<u8>>,
    out: OutTx,
    mut cancel: watch::Receiver<Option<String>>,
) -> Result<()> {
    // 1) Noise XX 핸드셰이크 (PC = responder)
    let mut hs = Handshake::responder(&shared.keypair)?;
    hs.read(&recv_timeout(&mut inbox, HANDSHAKE_TIMEOUT).await?)?;
    let m2 = hs.write()?;
    out.send(Outgoing::Binary(encode_agent_frame(sid, &m2))).await.map_err(|_| anyhow!("중계 연결 끊김"))?;
    hs.read(&recv_timeout(&mut inbox, HANDSHAKE_TIMEOUT).await?)?;
    let ch = hs.finish()?;
    let remote = ch.remote_static;
    let sas = ch.sas.clone();
    let fp = fingerprint(&remote);
    let (sealer, mut opener) = ch.into_split();
    let mut wire = Wire { sid, out, sealer };

    // 2) Hello
    let hello = decode_client(&mut opener, &recv_timeout(&mut inbox, HANDSHAKE_TIMEOUT).await?)?;
    let ClientMsg::Hello { client_name, app_version, protocol } = hello else {
        bail!("첫 메시지가 Hello 가 아님");
    };
    let client_name: String = client_name.chars().filter(|c| !c.is_control()).take(64).collect();
    if protocol != PROTOCOL_VERSION {
        wire.send(&AgentMsg::Denied {
            reason: format!("프로토콜 버전 불일치 (PC {PROTOCOL_VERSION}, 앱 {protocol}). 앱/에이전트를 업데이트하세요."),
        })
        .await?;
        bail!("프로토콜 버전 불일치");
    }

    // 3) 인증: 긴급 차단 → 등록 기기 → (등록 대기 중일 때만) PC 사용자 승인
    shared.reload_block_state();
    if shared.is_blocked() {
        shared.audit.record("denied_blocked", &client_name, &fp, "긴급 차단 상태");
        deny(&mut wire, "PC 에서 원격 제어가 차단되어 있습니다. PC 의 HomePilot 메뉴에서 다시 허용하세요.").await;
        bail!("차단 상태");
    }
    shared.reload_trust();
    let known = shared.trust.lock().unwrap().find(&remote).cloned();
    let perms: Permissions = match known {
        Some(c) => c.permissions,
        None => pair_new_device(shared, &mut wire, &mut inbox, &client_name, &fp, &sas, &remote).await?,
    };
    {
        let mut t = shared.trust.lock().unwrap();
        t.touch(&remote);
        let _ = t.save();
    }
    if !perms.view {
        deny(&mut wire, "이 기기에는 화면 보기 권한이 없습니다.").await;
        bail!("보기 권한 없음");
    }
    shared.audit.record("session_start", &client_name, &fp, &format!("앱 {app_version}"));
    shared.set_session_view(id, SessionView { client_name: client_name.clone(), controlling: perms.control });
    wire.send(&AgentMsg::Welcome {
        device_name: shared.display_name(),
        agent_version: env!("CARGO_PKG_VERSION").into(),
        protocol: PROTOCOL_VERSION,
        permissions: perms,
    })
    .await?;

    // 4) 명령 처리
    let started = Instant::now();
    let r = serve(shared, &mut wire, &mut opener, &mut inbox, &mut cancel, perms).await;
    let reason = match &r {
        Ok(s) => s.clone(),
        Err(e) => format!("{e:#}"),
    };
    shared.audit.record("session_end", &client_name, &fp, &format!("{}초, {reason}", started.elapsed().as_secs()));
    r.map(|_| ())
}

async fn deny(wire: &mut Wire, reason: &str) {
    let _ = wire.send(&AgentMsg::Denied { reason: reason.into() }).await;
    tokio::time::sleep(Duration::from_millis(200)).await;
    wire.kick().await;
}

#[allow(clippy::too_many_arguments)]
async fn pair_new_device(
    shared: &Arc<Shared>,
    wire: &mut Wire,
    inbox: &mut mpsc::Receiver<Vec<u8>>,
    client_name: &str,
    fp: &str,
    sas: &str,
    remote: &[u8; 32],
) -> Result<Permissions> {
    if shared.pairing_remaining().is_none() {
        shared.audit.record("denied_unknown", client_name, fp, "등록되지 않은 기기");
        // 처음 10분이 지나 등록 대기가 닫힌 뒤 휴대폰을 추가하면 PC 쪽에는 아무 표시가 없어 헷갈렸다.
        shared.notify(
            "등록되지 않은 휴대폰의 접속 시도",
            &format!("\"{client_name}\" 을(를) 등록하려면 트레이 아이콘 → '새 휴대폰 등록' 을 누른 뒤 휴대폰에서 다시 연결하세요."),
        );
        deny(wire, "등록되지 않은 기기입니다. PC 의 HomePilot 메뉴에서 '새 휴대폰 등록'을 누른 뒤 다시 시도하세요.").await;
        bail!("미등록 기기");
    }
    if shared.pairing_busy.swap(true, Ordering::SeqCst) {
        deny(wire, "PC 에서 다른 등록 요청을 처리 중입니다. 잠시 후 다시 시도하세요.").await;
        bail!("등록 요청 중복");
    }
    wire.send(&AgentMsg::PairingPending { sas: sas.into() }).await?;
    shared.audit.record("pairing_request", client_name, fp, "PC 사용자 승인 대기");
    let approver = shared.approver.clone();
    let (n, f, s) = (client_name.to_string(), fp.to_string(), sas.to_string());
    let sh = shared.clone();
    let mut ask = tokio::task::spawn_blocking(move || {
        let ok = approver(&n, &f, &s);
        sh.pairing_busy.store(false, Ordering::SeqCst);
        ok
    });
    let approved = tokio::select! {
        r = &mut ask => r.unwrap_or(false),
        _ = tokio::time::sleep(APPROVAL_TIMEOUT) => false,
        // 승인 대기 중 휴대폰이 연결을 끊은 경우
        _ = async { while inbox.recv().await.is_some() {} } => false,
    };
    if !approved {
        // 거부된 요청은 공격일 수 있으므로 등록 대기를 바로 닫는다.
        shared.close_pairing();
        shared.audit.record("pairing_denied", client_name, fp, "PC 사용자가 거부했거나 시간 초과");
        deny(wire, "PC 에서 등록을 승인하지 않았습니다.").await;
        bail!("등록 거부");
    }
    let perms = Permissions::default_for_new_device();
    {
        let mut t = shared.trust.lock().unwrap();
        t.add(client_name, remote, perms);
        t.save().context("등록 목록 저장 실패")?;
    }
    // 한 번 등록하면 등록 대기를 닫는다 (추가 기기는 다시 메뉴에서 열어야 함).
    shared.close_pairing();
    shared.audit.record("pairing_approved", client_name, fp, "새 기기 등록");
    Ok(perms)
}

async fn serve(
    shared: &Arc<Shared>,
    wire: &mut Wire,
    opener: &mut Opener,
    inbox: &mut mpsc::Receiver<Vec<u8>>,
    cancel: &mut watch::Receiver<Option<String>>,
    perms: Permissions,
) -> Result<String> {
    let monitors = platform::list_monitors().unwrap_or_default();
    let mut current: MonitorInfo =
        monitors.iter().find(|m| m.primary).or(monitors.first()).cloned().ok_or_else(|| anyhow!("모니터를 찾을 수 없음"))?;
    let mut input = Input::new();
    let mut stream: Option<StreamHandle> = None;
    let mut in_flight: u32 = 0;
    let mut pending: Option<Vec<u8>> = None;
    let mut last_rx = Instant::now();
    let mut tick = tokio::time::interval(Duration::from_secs(5));

    loop {
        tokio::select! {
            _ = cancel.changed() => {
                let reason = cancel.borrow().clone().unwrap_or_else(|| "종료".into());
                let _ = wire.send(&AgentMsg::SessionEnded { reason: reason.clone() }).await;
                tokio::time::sleep(Duration::from_millis(200)).await;
                wire.kick().await;
                return Ok(reason);
            }
            frame = async { stream.as_mut().unwrap().frames.recv().await }, if stream.is_some() => {
                let Some(frame) = frame else { stream = None; continue };
                if in_flight < MAX_IN_FLIGHT {
                    in_flight += 1;
                    wire.send_plain(&frame).await?;
                } else {
                    pending = Some(frame); // 최신 프레임만 보관
                }
            }
            _ = tick.tick() => {
                if last_rx.elapsed() > IDLE_TIMEOUT {
                    bail!("휴대폰 응답 없음 (시간 초과)");
                }
            }
            ct = inbox.recv() => {
                let Some(ct) = ct else { return Ok("휴대폰 연결 끊김".into()) };
                last_rx = Instant::now();
                let msg = decode_client(opener, &ct)?;
                match msg {
                    ClientMsg::Hello { .. } => {}
                    ClientMsg::Ping { t } => wire.send(&AgentMsg::Pong { t }).await?,
                    ClientMsg::Bye => return Ok("휴대폰에서 종료".into()),
                    ClientMsg::GetStatus => {
                        let mut s = shared.status.read().unwrap().clone();
                        s.active_sessions = shared.active_sessions().len() as u32;
                        wire.send(&AgentMsg::Status(s)).await?;
                    }
                    ClientMsg::ListMonitors => {
                        let monitors = platform::list_monitors().unwrap_or_default();
                        wire.send(&AgentMsg::Monitors { monitors }).await?;
                    }
                    ClientMsg::StartStream { monitor, quality, scale_pct, max_fps } => {
                        let monitors = platform::list_monitors().unwrap_or_default();
                        let Some(m) = monitors.into_iter().find(|m| m.index == monitor) else {
                            wire.send(&AgentMsg::Error { code: "no_monitor".into(), message: format!("모니터 {monitor} 없음") }).await?;
                            continue;
                        };
                        current = m.clone();
                        drop(stream.take()); // 이전 전송 스레드 정지
                        pending = None;
                        in_flight = 0;
                        let p = StreamParams { quality: quality.clamp(10, 95), scale_pct: scale_pct.clamp(10, 100), max_fps: max_fps.clamp(1, 30) };
                        tracing::info!(monitor, ?p, "화면 전송 시작");
                        stream = Some(stream::start(m.clone(), p));
                        wire.send(&AgentMsg::StreamStarted { monitor, width: m.width, height: m.height }).await?;
                    }
                    ClientMsg::StopStream => {
                        stream = None;
                        pending = None;
                        in_flight = 0;
                        wire.send(&AgentMsg::StreamStopped).await?;
                    }
                    ClientMsg::FrameAck { .. } => {
                        in_flight = in_flight.saturating_sub(1);
                        if let Some(f) = pending.take() {
                            in_flight += 1;
                            wire.send_plain(&f).await?;
                        }
                    }
                    other => {
                        let Some(actions) = input::translate(&other, &current) else { continue };
                        if !perms.control {
                            wire.send(&AgentMsg::Error { code: "no_permission".into(), message: "이 기기에는 조작 권한이 없습니다".into() }).await?;
                            continue;
                        }
                        for a in actions {
                            if let Err(e) = input.apply(a) {
                                wire.send(&AgentMsg::Error { code: "input".into(), message: format!("{e:#}") }).await?;
                                break;
                            }
                        }
                    }
                }
            }
        }
    }
}
