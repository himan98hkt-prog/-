//! 집 PC 단독 구성: 중계 서버를 에이전트 안에서 실행하고, Cloudflare 빠른 터널로 외부에 공개한다.
//!
//!   휴대폰 ──wss──> Cloudflare ──터널──> cloudflared(이 PC) ──> 내장 중계(127.0.0.1) <── 에이전트
//!
//! - 공유기 포트 개방이 필요 없고 비용이 들지 않는다.
//! - 빠른 터널 주소(https://xxxx.trycloudflare.com)는 cloudflared 를 다시 실행할 때마다 바뀐다.
//!   고정 주소가 필요하면 도메인을 연결한 이름 있는 터널을 쓴다 (docs 참고).
//! - 내장 중계는 127.0.0.1 에만 열리며, 에이전트 등록에는 실행할 때마다 새로 만드는 비밀 토큰이 필요하다.
//!   (터널을 통해 들어온 사람이 같은 장치 ID 로 PC 행세를 하며 연결을 가로채려는 시도를 막음)

use crate::app::Shared;
use anyhow::{Context, Result};
use base64::Engine;
use homepilot_relay::{serve, RelayConfig};
use std::path::PathBuf;
use std::process::Stdio;
use std::sync::Arc;
use std::time::Duration;
use tokio::io::{AsyncBufReadExt, BufReader};

/// 내장 중계 서버 시작. 에이전트가 접속할 주소를 돌려준다.
pub async fn start_local_relay(shared: &Arc<Shared>, port: u16) -> Result<String> {
    let listener = tokio::net::TcpListener::bind(("127.0.0.1", port))
        .await
        .with_context(|| format!("내장 중계 서버 포트 {port} 를 열 수 없습니다 (다른 프로그램이 사용 중?)"))?;
    let token = base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(rand::random::<[u8; 24]>());
    *shared.agent_token.lock().unwrap() = Some(token.clone());
    tokio::spawn(async move {
        if let Err(e) = serve(listener, RelayConfig { agent_token: Some(token) }).await {
            tracing::error!("내장 중계 서버 중지: {e:#}");
        }
    });
    tracing::info!("내장 중계 서버 시작: 127.0.0.1:{port}");
    Ok(format!("ws://127.0.0.1:{port}"))
}

/// cloudflared 실행 파일 찾기: 설정값 → 에이전트와 같은 폴더 → 기본 설치 위치 → PATH.
pub fn find_cloudflared(configured: &str) -> PathBuf {
    if !configured.trim().is_empty() {
        return PathBuf::from(configured.trim());
    }
    let exe_name = if cfg!(windows) { "cloudflared.exe" } else { "cloudflared" };
    let mut candidates = Vec::new();
    if let Some(dir) = std::env::current_exe().ok().and_then(|p| p.parent().map(|d| d.to_path_buf())) {
        candidates.push(dir.join(exe_name));
    }
    for var in ["ProgramFiles(x86)", "ProgramFiles"] {
        if let Some(pf) = std::env::var_os(var) {
            candidates.push(PathBuf::from(pf).join("cloudflared").join(exe_name));
        }
    }
    candidates.into_iter().find(|p| p.is_file()).unwrap_or_else(|| PathBuf::from(exe_name))
}

/// cloudflared 출력에서 빠른 터널 주소를 찾는다.
pub fn parse_quick_tunnel_url(line: &str) -> Option<String> {
    let mut rest = line;
    while let Some(i) = rest.find("https://") {
        let cand: String = rest[i..].chars().take_while(|c| c.is_ascii_alphanumeric() || matches!(c, ':' | '/' | '.' | '-')).collect();
        let host = cand.trim_start_matches("https://").trim_end_matches('/');
        if host.ends_with(".trycloudflare.com") && host != "api.trycloudflare.com" && !host.contains('/') {
            return Some(format!("https://{host}"));
        }
        rest = &rest[i + 8..];
    }
    None
}

/// 빠른 터널을 실행·감시한다. 끊기면 다시 띄우고 새 주소를 알린다.
pub async fn run_quick_tunnel(shared: Arc<Shared>, port: u16) {
    let mut backoff = 5u64;
    loop {
        let path = find_cloudflared(&shared.config.lock().unwrap().cloudflared_path);
        let mut cmd = tokio::process::Command::new(&path);
        cmd.args(["tunnel", "--no-autoupdate", "--url", &format!("http://127.0.0.1:{port}")])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::piped())
            .kill_on_drop(true);
        #[cfg(windows)]
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW: 검은 콘솔 창을 띄우지 않음
        match cmd.spawn() {
            Err(e) => {
                tracing::error!("cloudflared 실행 실패 ({}): {e}. 'winget install Cloudflare.cloudflared' 로 설치하세요.", path.display());
                shared.set_public_url(None, Some("cloudflared 가 설치되어 있지 않습니다".into()));
            }
            Ok(mut child) => {
                tracing::info!("Cloudflare 터널 시작 ({})", path.display());
                shared.set_public_url(None, Some("터널 주소 받는 중…".into()));
                if let Some(err) = child.stderr.take() {
                    let mut lines = BufReader::new(err).lines();
                    while let Ok(Some(line)) = lines.next_line().await {
                        tracing::debug!(target: "cloudflared", "{line}");
                        if let Some(url) = parse_quick_tunnel_url(&line) {
                            tracing::info!("휴대폰용 중계 주소: {url}");
                            shared.set_public_url(Some(url), None);
                            backoff = 5;
                        }
                    }
                }
                let status = child.wait().await;
                tracing::warn!("cloudflared 종료: {status:?}");
                shared.set_public_url(None, Some("터널이 끊겨 다시 연결하는 중…".into()));
            }
        }
        tokio::time::sleep(Duration::from_secs(backoff)).await;
        backoff = (backoff * 2).min(60);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_cloudflared_banner() {
        let l = "2026-10-13T05:00:00Z INF |  https://quiet-river-sample-test.trycloudflare.com                                  |";
        assert_eq!(parse_quick_tunnel_url(l).as_deref(), Some("https://quiet-river-sample-test.trycloudflare.com"));
        assert_eq!(parse_quick_tunnel_url("INF Requesting new quick Tunnel on trycloudflare.com..."), None);
        assert_eq!(parse_quick_tunnel_url("see https://developers.cloudflare.com/x and https://api.trycloudflare.com"), None);
    }
}
