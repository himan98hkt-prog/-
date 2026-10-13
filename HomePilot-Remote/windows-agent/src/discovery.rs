//! 고정 접속: 주소가 바뀌어도 휴대폰이 PC 를 찾아오게 한다. 추가 비용 없음.
//!
//! 1. 같은 Wi-Fi: 휴대폰이 UDP 방송으로 "HomePilot PC 있나요?" 를 보내면 응답한다(PC 추가 화면의 자동 찾기),
//!    그리고 내장 중계를 집 네트워크에도 열어 터널 없이 바로 접속한다.
//! 2. 외부: 현재 터널 주소와 집 네트워크 주소를 암호화해 무료 게시판(ntfy.sh)에 올린다.
//!    주소가 바뀌거나 1시간마다 다시 올린다(게시판 보관 12시간).

use crate::app::Shared;
use homepilot_protocol::directory::{self, DirectoryRecord};
use std::sync::Arc;
use std::time::{Duration, Instant};

/// 휴대폰이 같은 Wi-Fi 에서 PC 를 찾을 때 쓰는 UDP 포트
pub const DISCOVERY_PORT: u16 = 47830;
pub const DISCOVERY_QUERY: &[u8] = b"HOMEPILOT_DISCOVER_V1";
const REPUBLISH_EVERY: Duration = Duration::from_secs(55 * 60);

/// 이 PC 의 집 네트워크 IPv4 주소 (기본 경로 기준). 실제 패킷은 보내지 않는다.
pub fn primary_lan_ip() -> Option<std::net::Ipv4Addr> {
    let s = std::net::UdpSocket::bind("0.0.0.0:0").ok()?;
    s.connect("8.8.8.8:80").ok()?;
    match s.local_addr().ok()?.ip() {
        std::net::IpAddr::V4(ip) if !ip.is_loopback() && !ip.is_unspecified() => Some(ip),
        _ => None,
    }
}

pub fn lan_list(shared: &Shared) -> Vec<String> {
    let c = shared.config.lock().unwrap();
    if !(c.local_relay && c.lan_access) {
        return vec![];
    }
    primary_lan_ip().map(|ip| vec![format!("{ip}:{}", c.local_relay_port)]).unwrap_or_default()
}

fn now_unix() -> u64 {
    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

/// 주소 안내판에 올리기. 주소·집 네트워크 주소가 바뀌거나 1시간이 지나면 다시 올린다.
pub async fn run_publisher(shared: Arc<Shared>) {
    let mut last: Option<(String, Vec<String>)> = None;
    let mut last_at = Instant::now();
    let mut fails = 0u32;
    loop {
        tokio::time::sleep(Duration::from_secs(if fails > 0 { 30 } else { 5 })).await;
        let base = shared.config.lock().unwrap().directory_url.trim().trim_end_matches('/').to_string();
        if base.is_empty() {
            continue;
        }
        let url = shared.public_url.lock().unwrap().0.clone().unwrap_or_default();
        let lan = lan_list(&shared);
        if url.is_empty() && lan.is_empty() {
            continue;
        }
        let cur = (url.clone(), lan.clone());
        if last.as_ref() == Some(&cur) && last_at.elapsed() < REPUBLISH_EVERY && fails == 0 {
            continue;
        }
        let pk = shared.keypair.public;
        let rec = DirectoryRecord { v: 1, id: shared.device_id.clone(), url, lan, ts: now_unix() };
        let body = directory::seal(&pk, &rec, rand::random());
        let target = format!("{base}/{}", directory::topic(&pk));
        let res = tokio::task::spawn_blocking(move || {
            ureq::post(&target).timeout(Duration::from_secs(15)).send_string(&body).map(|_| ()).map_err(|e| e.to_string())
        })
        .await;
        match res {
            Ok(Ok(_)) => {
                tracing::info!("주소 안내판 갱신 (외부 {} / 집 {:?})", if cur.0.is_empty() { "없음" } else { &cur.0 }, cur.1);
                last = Some(cur);
                last_at = Instant::now();
                fails = 0;
            }
            Ok(Err(e)) => {
                fails += 1;
                if fails % 10 == 1 {
                    tracing::warn!("주소 안내판 갱신 실패 ({fails}회): {e}");
                }
            }
            Err(e) => tracing::warn!("주소 안내판 작업 오류: {e}"),
        }
    }
}

/// 같은 Wi-Fi 휴대폰의 찾기 요청에 응답한다.
pub async fn run_responder(shared: Arc<Shared>) {
    let sock = match tokio::net::UdpSocket::bind(("0.0.0.0", DISCOVERY_PORT)).await {
        Ok(s) => s,
        Err(e) => {
            tracing::warn!("같은 Wi-Fi 자동 찾기 사용 불가 (UDP {DISCOVERY_PORT}: {e})");
            return;
        }
    };
    tracing::info!("같은 Wi-Fi 자동 찾기 대기 (UDP {DISCOVERY_PORT})");
    let mut buf = [0u8; 256];
    loop {
        let Ok((n, from)) = sock.recv_from(&mut buf).await else { continue };
        if &buf[..n] != DISCOVERY_QUERY {
            continue;
        }
        let reply = {
            let c = shared.config.lock().unwrap();
            serde_json::json!({
                "t": "homepilot_pc",
                "v": 1,
                "id": shared.device_id,
                "name": c.display_name(),
                "fp": shared.fingerprint(),
                "port": if c.local_relay && c.lan_access { c.local_relay_port } else { 0 },
                "url": shared.public_url.lock().unwrap().0.clone().unwrap_or_default(),
            })
            .to_string()
        };
        let _ = sock.send_to(reply.as_bytes(), from).await;
    }
}
