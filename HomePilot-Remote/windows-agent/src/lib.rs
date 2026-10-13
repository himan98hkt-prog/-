//! HomePilot Remote - Windows PC 에이전트.
//!
//! 사용법 (명령 프롬프트):
//!   homepilot-agent                       트레이 아이콘으로 실행 (기본)
//!   homepilot-agent info                  장치 ID / 지문 / 설정 확인
//!   homepilot-agent config --relay wss://relay.example.com --name "거실 PC"
//!   homepilot-agent clients               등록된 휴대폰 목록
//!   homepilot-agent revoke <지문|이름>    등록 해제
//!   homepilot-agent autostart on|off|status
//!   homepilot-agent unblock               긴급 차단 해제
//!   homepilot-agent log                   최근 접속 기록

// 실행 파일은 두 개: homepilot-agent.exe (창 없는 트레이 프로그램), homepilot-cli.exe (명령 프롬프트용).
// 둘 다 이 라이브러리의 run_main() 을 부른다.
// 트레이 UI 등 일부 기능은 Windows 빌드에서만 쓰인다.
#![cfg_attr(not(windows), allow(dead_code))]

mod ai;
mod app;
mod audio_stream;
mod audit;
mod config;
mod console;
mod discovery;
mod encode;
mod files;
mod home_relay;
mod input;
mod keystore;
mod metrics;
mod net;
mod platform;
mod session;
mod stream;
mod trust;

use anyhow::{bail, Context, Result};
use app::{Approver, Shared};
use clap::{Parser, Subcommand};
use config::{Config, Paths};
use std::sync::Arc;
use trust::TrustStore;

#[derive(Parser)]
#[command(name = "homepilot-agent", version, about = "HomePilot Remote Windows 에이전트")]
struct Cli {
    #[command(subcommand)]
    cmd: Option<Cmd>,
}

#[derive(Subcommand)]
enum Cmd {
    /// 에이전트 실행 (기본 동작)
    Run {
        /// 트레이 아이콘 없이 콘솔에서 실행 (서버·테스트용)
        #[arg(long)]
        headless: bool,
        /// 표준입력 명령 사용 (y/n 등록 승인, block, unblock, pair, end, status)
        #[arg(long)]
        console: bool,
        /// 시작 시 등록 대기를 이 시간(초)만큼 연다
        #[arg(long)]
        pairing_secs: Option<u64>,
    },
    /// 장치 정보 출력
    Info,
    /// 설정 변경
    Config {
        #[arg(long)]
        relay: Option<String>,
        #[arg(long)]
        name: Option<String>,
        /// 원격 제어 표시줄 on/off
        #[arg(long)]
        overlay: Option<bool>,
        /// 중계 서버를 에이전트 안에서 실행 (집 PC 단독 구성)
        #[arg(long)]
        local_relay: Option<bool>,
        /// 외부 공개 방식: off | quick (Cloudflare 빠른 터널)
        #[arg(long, value_parser = ["off", "quick"])]
        tunnel: Option<String>,
        /// cloudflared.exe 경로 (보통 자동으로 찾음)
        #[arg(long)]
        cloudflared: Option<String>,
        /// 내장 중계 서버 포트 (기본 8443)
        #[arg(long)]
        local_relay_port: Option<u16>,
    },
    /// 집 PC 단독 구성 한 번에 설정: 내장 중계 + Cloudflare 빠른 터널
    SetupHome,
    /// 등록된 휴대폰 목록
    Clients,
    /// 이 PC 에서 직접 휴대폰 공개키를 등록 (PC 앞에 있는 사용자만 가능한 로컬 작업)
    TrustClient {
        #[arg(long)]
        name: String,
        /// 휴대폰 공개키 (base64)
        #[arg(long)]
        public_key: String,
        /// 조작 권한 없이 보기만 허용
        #[arg(long)]
        view_only: bool,
        /// 파일 보기·주고받기도 허용
        #[arg(long)]
        files: bool,
        /// AI 작업(Claude Code·Ollama)도 허용
        #[arg(long)]
        ai: bool,
    },
    /// 등록 해제
    Revoke { who: String },
    /// Windows 시작 시 자동 실행 설정
    Autostart {
        #[arg(value_parser = ["on", "off", "status"])]
        action: String,
    },
    /// 긴급 차단 해제
    Unblock,
    /// 최근 접속 기록
    Log {
        #[arg(default_value_t = 30)]
        lines: usize,
    },
}

fn init_logging(paths: &Paths, console: bool) -> tracing_appender::non_blocking::WorkerGuard {
    use tracing_subscriber::prelude::*;
    let file = tracing_appender::rolling::daily(&paths.log_dir, "agent.log");
    let (nb, guard) = tracing_appender::non_blocking(file);
    let filter = tracing_subscriber::EnvFilter::try_from_env("HOMEPILOT_LOG").unwrap_or_else(|_| "info".into());
    let file_layer = tracing_subscriber::fmt::layer().with_ansi(false).with_writer(nb);
    let console_layer = console.then(|| tracing_subscriber::fmt::layer().with_writer(std::io::stderr));
    tracing_subscriber::registry().with(filter).with(file_layer).with(console_layer).init();
    guard
}

/// 공통 진입점.
pub fn run_main() {
    let cli = Cli::parse_from(std::env::args_os());
    // 트레이 모드(명령 없이 실행)만 화면 대화상자를 쓴다. 명령줄·콘솔 모드에서 대화상자를 띄우면
    // 화면 앞에 사람이 없을 때(서비스, CI) 영원히 멈추므로 오류는 표준오류로만 알린다.
    let tray_mode = matches!(cli.cmd, None | Some(Cmd::Run { headless: false, console: false, .. }));
    if !tray_mode {
        platform::attach_parent_console();
    }
    if let Err(e) = real_main(cli) {
        eprintln!("오류: {e:#}");
        if tray_mode {
            platform::show_message("HomePilot 오류", &format!("{e:#}"));
        }
        std::process::exit(1);
    }
}

fn real_main(cli: Cli) -> Result<()> {
    let paths = Paths::resolve()?;
    paths.ensure()?;
    let cmd = cli.cmd.unwrap_or(Cmd::Run { headless: false, console: false, pairing_secs: None });
    match cmd {
        Cmd::Run { headless, console, pairing_secs } => run(paths, headless || !cfg!(windows), console, pairing_secs),
        Cmd::Info => {
            let kp = keystore::load_or_create(&paths)?;
            let cfg = Config::load(&paths.config_file())?;
            println!("PC 이름     : {}", cfg.display_name());
            println!("장치 ID     : {}", homepilot_protocol::secure::device_id_from_public(&kp.public));
            println!("PC 지문     : {}", homepilot_protocol::secure::fingerprint(&kp.public));
            if cfg.local_relay {
                println!("중계 서버   : 내장 (127.0.0.1:{}), 터널: {}", cfg.local_relay_port, cfg.tunnel);
                match std::fs::read_to_string(paths.public_url_file()) {
                    Ok(u) => println!("휴대폰 주소 : {}  (실행 중인 에이전트 기준, 다시 시작하면 바뀜)", u.trim()),
                    Err(_) => println!("휴대폰 주소 : (에이전트 실행 후 표시)"),
                }
            } else {
                println!("중계 서버   : {}", cfg.relay_url);
            }
            println!("긴급 차단   : {}", if cfg.remote_blocked { "켜짐 (원격 접속 거부)" } else { "꺼짐" });
            println!("자동 실행   : {}", if platform::autostart_get().unwrap_or(false) { "켜짐" } else { "꺼짐" });
            println!("데이터 폴더 : {}", paths.data_dir.display());
            println!("로그 폴더   : {}", paths.log_dir.display());
            Ok(())
        }
        Cmd::SetupHome => {
            let mut cfg = Config::load(&paths.config_file())?;
            cfg.local_relay = true;
            cfg.tunnel = "quick".into();
            cfg.save(&paths.config_file())?;
            let cf = home_relay::find_cloudflared(&cfg.cloudflared_path);
            println!("집 PC 단독 구성으로 설정했습니다 (내장 중계 + Cloudflare 빠른 터널).");
            if cf.is_file() {
                println!("cloudflared: {}", cf.display());
            } else {
                println!("주의: cloudflared 를 찾지 못했습니다. PowerShell 에서 다음 명령으로 설치하세요:");
                println!("  winget install --id Cloudflare.cloudflared");
            }
            println!("HomePilot 을 (다시) 실행하면 트레이 메뉴 'PC 정보' 에 휴대폰용 주소가 표시됩니다.");
            Ok(())
        }
        Cmd::Config { relay, name, overlay, local_relay, tunnel, cloudflared, local_relay_port } => {
            let mut cfg = Config::load(&paths.config_file())?;
            if let Some(r) = relay {
                let u = url::Url::parse(&r).context("주소 형식 오류")?;
                if !matches!(u.scheme(), "ws" | "wss") {
                    bail!("ws:// 또는 wss:// 주소여야 합니다");
                }
                if u.scheme() == "ws" && !matches!(u.host_str(), Some("127.0.0.1" | "localhost")) {
                    eprintln!("경고: ws:// 는 전송 구간 TLS 가 없습니다. 내용은 종단간 암호화되지만 운영 환경에서는 wss:// 를 쓰세요.");
                }
                cfg.relay_url = r;
                // 외부 중계 서버를 지정하면 내장 중계·터널은 끈다 (--local-relay 로 다시 켤 수 있음)
                cfg.local_relay = false;
                cfg.tunnel = "off".into();
            }
            if let Some(n) = name {
                cfg.device_name = n;
            }
            if let Some(o) = overlay {
                cfg.show_overlay = o;
            }
            if let Some(v) = local_relay {
                cfg.local_relay = v;
            }
            if let Some(v) = tunnel {
                cfg.tunnel = v;
            }
            if let Some(v) = cloudflared {
                cfg.cloudflared_path = v;
            }
            if let Some(v) = local_relay_port {
                cfg.local_relay_port = v;
            }
            cfg.save(&paths.config_file())?;
            println!("저장했습니다. 실행 중인 에이전트는 다시 시작해야 적용됩니다.");
            Ok(())
        }
        Cmd::Clients => {
            let t = TrustStore::load(&paths)?;
            if t.clients.is_empty() {
                println!("등록된 휴대폰이 없습니다.");
            }
            for c in &t.clients {
                let p = c.permissions;
                println!(
                    "{}  [{}]  보기:{} 조작:{} 파일:{} 앱:{}  마지막 접속:{}",
                    c.name,
                    c.fingerprint,
                    yn(p.view),
                    yn(p.control),
                    yn(p.files),
                    yn(p.apps),
                    c.last_seen.map(|t| t.to_string()).unwrap_or_else(|| "-".into())
                );
            }
            Ok(())
        }
        Cmd::TrustClient { name, public_key, view_only, files, ai } => {
            let pk = trust::parse_public_key(&public_key)?;
            let mut t = TrustStore::load(&paths)?;
            let mut perms = homepilot_protocol::app::Permissions::default_for_new_device();
            perms.control = !view_only;
            perms.files = files;
            perms.apps = ai;
            let c = t.add(&name, &pk, perms);
            t.save()?;
            audit::Audit::new(paths.audit_file()).record("trust_local", &c.name, &c.fingerprint, "PC 에서 직접 등록");
            println!("등록했습니다: {} [{}]", c.name, c.fingerprint);
            Ok(())
        }
        Cmd::Revoke { who } => {
            let mut t = TrustStore::load(&paths)?;
            let n = t.revoke(&who);
            t.save()?;
            audit::Audit::new(paths.audit_file()).record("revoke", &who, "-", &format!("{n}개 해제"));
            println!("{n}개 기기의 등록을 해제했습니다. (실행 중인 에이전트는 다음 접속부터 거부)");
            Ok(())
        }
        Cmd::Autostart { action } => {
            match action.as_str() {
                "on" => {
                    platform::autostart_set(true)?;
                    println!("Windows 로그인 시 자동 실행을 켰습니다 (현재 사용자만, 관리자 권한 불필요).");
                }
                "off" => {
                    platform::autostart_set(false)?;
                    println!("자동 실행을 껐습니다.");
                }
                _ => println!("자동 실행: {}", if platform::autostart_get()? { "켜짐" } else { "꺼짐" }),
            }
            Ok(())
        }
        Cmd::Unblock => {
            let mut cfg = Config::load(&paths.config_file())?;
            cfg.remote_blocked = false;
            cfg.save(&paths.config_file())?;
            println!("긴급 차단을 해제했습니다. 실행 중인 에이전트에도 다음 접속부터 바로 적용됩니다.");
            Ok(())
        }
        Cmd::Log { lines } => {
            for l in audit::Audit::new(paths.audit_file()).tail(lines) {
                println!("{l}");
            }
            Ok(())
        }
    }
}

fn yn(b: bool) -> &'static str {
    if b {
        "O"
    } else {
        "X"
    }
}

fn run(paths: Paths, headless: bool, console: bool, pairing_secs: Option<u64>) -> Result<()> {
    let _guard = init_logging(&paths, headless || cfg!(debug_assertions));
    // 창 없는 프로그램은 비정상 종료 이유가 보이지 않으므로 로그 폴더의 crash.log 에 즉시 기록한다.
    let crash_file = paths.log_dir.join("crash.log");
    std::panic::set_hook(Box::new(move |info| {
        let msg = format!("[{}] 비정상 종료: {info}\n", trust::now_unix());
        tracing::error!("{msg}");
        use std::io::Write;
        if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(&crash_file) {
            let _ = f.write_all(msg.as_bytes());
        }
    }));
    // 같은 사용자 세션에서 두 번 실행되면 포트·트레이가 충돌하므로 막는다.
    let _instance = platform::single_instance()
        .ok_or_else(|| anyhow::anyhow!("HomePilot 이 이미 실행 중입니다. 작업 표시줄 오른쪽 아래 ^ 안의 HomePilot 아이콘을 확인하세요."))?;
    let _ = rustls::crypto::ring::default_provider().install_default();
    platform::init_process();
    tracing::info!("HomePilot 에이전트 {} 시작", env!("CARGO_PKG_VERSION"));

    let config = Config::load(&paths.config_file())?;
    let trust = TrustStore::load(&paths)?;
    let keypair = keystore::load_or_create(&paths)?;

    let approver: Approver = if console {
        console::approver()
    } else if headless {
        // 화면도 콘솔도 없는 실행에서는 등록 요청을 승인할 사람이 없으므로 모두 거부한다.
        // (PC 에서 `trust-client` 명령으로 직접 등록해야 함)
        Arc::new(|_: &str, _: &str, _: &str| false)
    } else {
        Arc::new(|n: &str, f: &str, s: &str| platform::ask_pairing_approval(n, f, s))
    };

    let shared = Shared::new(paths, config, trust, keypair, approver);
    if let Some(s) = pairing_secs {
        shared.open_pairing(std::time::Duration::from_secs(s));
    }
    tracing::info!("장치 ID {} / 지문 {}", shared.device_id, shared.fingerprint());
    if console {
        console::spawn_reader(shared.clone());
    }
    metrics::spawn_collector(shared.status.clone());

    let rt = tokio::runtime::Builder::new_multi_thread().enable_all().worker_threads(2).build()?;
    let _ = std::fs::remove_file(shared.paths.public_url_file());
    let (local_relay, port, tunnel) = {
        let c = shared.config.lock().unwrap();
        (c.local_relay, c.local_relay_port, c.tunnel.clone())
    };
    if local_relay {
        let port = rt.block_on(home_relay::start_local_relay(&shared, port))?;
        if tunnel == "quick" {
            rt.spawn(home_relay::run_quick_tunnel(shared.clone(), port));
        }
        rt.spawn(discovery::run_responder(shared.clone()));
    }
    rt.spawn(discovery::run_publisher(shared.clone()));
    rt.spawn(net::run_forever(shared.clone()));
    if headless {
        rt.block_on(async {
            tokio::signal::ctrl_c().await.ok();
        });
    } else {
        platform::run_ui(shared.clone(), &rt)?;
    }
    shared.end_all_sessions("PC 에서 HomePilot 을 종료했습니다");
    std::thread::sleep(std::time::Duration::from_millis(300));
    rt.shutdown_timeout(std::time::Duration::from_secs(1));
    tracing::info!("에이전트 종료");
    Ok(())
}
