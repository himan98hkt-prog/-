//! HomePilot Remote 중계 서버 (단독 실행).
//! 운영 환경에서는 TLS 리버스 프록시(Caddy, Cloudflare Tunnel 등) 뒤에 두고 wss:// 로 접속한다.
//! 계정 인증·다중 인증·속도 제한은 Phase 3 에서 추가한다.

use clap::Parser;
use homepilot_relay::{serve, RelayConfig};
use std::net::SocketAddr;

#[derive(Parser)]
#[command(name = "homepilot-relay", version, about = "HomePilot Remote 중계 서버")]
struct Args {
    /// 수신 주소
    #[arg(long, default_value = "127.0.0.1:8443")]
    listen: SocketAddr,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::try_from_env("HOMEPILOT_LOG").unwrap_or_else(|_| "info".into()))
        .init();
    let args = Args::parse();
    // 에이전트 등록 토큰은 명령줄 대신 환경변수로 받는다 (프로세스 목록에 노출되지 않게).
    let agent_token = std::env::var("HOMEPILOT_AGENT_TOKEN").ok().filter(|s| !s.is_empty());
    if agent_token.is_none() {
        tracing::warn!("HOMEPILOT_AGENT_TOKEN 미설정: 누구나 에이전트로 등록할 수 있습니다 (개발용)");
    }
    let listener = tokio::net::TcpListener::bind(args.listen).await?;
    tracing::info!("중계 서버 시작: {}", args.listen);
    serve(listener, RelayConfig { agent_token }).await
}
