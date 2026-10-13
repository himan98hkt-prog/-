//! hp-cli: 휴대폰 앱과 같은 프로토콜로 PC 에이전트에 접속하는 시험용 클라이언트.
//!
//!   hp-cli keygen                                     내 키 생성 + 공개키 출력
//!   hp-cli --relay ws://127.0.0.1:8443 --device <장치ID> status
//!   hp-cli ... shot --monitor 0 --out screen.jpg
//!   hp-cli ... stream --secs 10
//!   hp-cli ... click 0.5 0.5 [--right] [--double]
//!   hp-cli ... type "안녕하세요"
//!   hp-cli ... combo ctrl c

use anyhow::{anyhow, bail, Context, Result};
use base64::engine::general_purpose::STANDARD as B64;
use base64::Engine;
use clap::{Parser, Subcommand};
use futures_util::{SinkExt, StreamExt};
use homepilot_protocol::app::{self, AgentMsg, ClientMsg, Decoded, FrameHeader, MouseButton};
use homepilot_protocol::relay::RelayToClient;
use homepilot_protocol::secure::{device_id_from_public, fingerprint, Handshake, Opener, Sealer, StaticKeypair};
use homepilot_protocol::PROTOCOL_VERSION;
use std::path::PathBuf;
use std::time::{Duration, Instant};
use tokio_tungstenite::tungstenite::Message;

#[derive(Parser)]
#[command(name = "hp-cli", about = "HomePilot 시험용 클라이언트")]
struct Cli {
    #[arg(long, default_value = "ws://127.0.0.1:8443")]
    relay: String,
    /// PC 장치 ID (PC 의 `homepilot-agent info` 로 확인)
    #[arg(long, default_value = "")]
    device: String,
    /// 내 키 파일
    #[arg(long, default_value = "hp-cli.key")]
    key: PathBuf,
    #[arg(long, default_value = "hp-cli")]
    name: String,
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    Keygen,
    /// 접속만 하고 결과 출력 (등록 확인용)
    Connect,
    Status,
    Monitors,
    Shot {
        #[arg(long, default_value_t = 0)]
        monitor: u32,
        #[arg(long, default_value = "screen.jpg")]
        out: PathBuf,
        #[arg(long, default_value_t = 75)]
        quality: u8,
        #[arg(long, default_value_t = 100)]
        scale: u8,
    },
    Stream {
        #[arg(long, default_value_t = 10)]
        secs: u64,
        #[arg(long, default_value_t = 0)]
        monitor: u32,
        #[arg(long, default_value_t = 60)]
        quality: u8,
        #[arg(long, default_value_t = 50)]
        scale: u8,
        #[arg(long, default_value_t = 15)]
        fps: u8,
        /// jpeg | h264
        #[arg(long, default_value = "jpeg")]
        codec: String,
    },
    Move {
        x: f32,
        y: f32,
    },
    Click {
        x: f32,
        y: f32,
        #[arg(long)]
        right: bool,
        #[arg(long)]
        double: bool,
    },
    Scroll {
        dy: f32,
    },
    Type {
        text: String,
    },
    Key {
        name: String,
    },
    Combo {
        keys: Vec<String>,
    },
    Ping {
        #[arg(long, default_value_t = 5)]
        count: u32,
    },
    /// PC 클립보드 읽기
    ClipGet,
    /// PC 클립보드에 넣기
    ClipSet {
        text: String,
    },
    /// PC 폴더 목록 (경로 생략 = 처음 목록)
    Ls {
        #[arg(default_value = "")]
        path: String,
    },
    /// PC 파일 받기
    Get {
        path: String,
        #[arg(long)]
        out: PathBuf,
    },
    /// PC 로 파일 보내기 (다운로드\HomePilot 에 저장됨)
    Put {
        file: PathBuf,
    },
}

fn load_or_create_key(path: &PathBuf) -> Result<StaticKeypair> {
    if let Ok(s) = std::fs::read_to_string(path) {
        let v = B64.decode(s.trim())?;
        if v.len() == 64 {
            return Ok(StaticKeypair::from_bytes(&v[..32], &v[32..])?);
        }
        bail!("키 파일 형식 오류");
    }
    let kp = StaticKeypair::generate()?;
    let mut v = kp.private.to_vec();
    v.extend_from_slice(&kp.public);
    std::fs::write(path, B64.encode(v))?;
    Ok(kp)
}

type Ws = tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>;

struct Conn {
    ws: Ws,
    sealer: Sealer,
    opener: Opener,
}

impl Conn {
    async fn send(&mut self, m: &ClientMsg) -> Result<()> {
        let ct = self.sealer.seal(&app::encode_control(m))?;
        self.ws.send(Message::Binary(ct)).await?;
        Ok(())
    }

    /// 다음 응용 메시지 (프레임이면 Err 대신 Frame 반환).
    async fn recv(&mut self, timeout: Duration) -> Result<Received> {
        loop {
            let m =
                tokio::time::timeout(timeout, self.ws.next()).await.context("응답 시간 초과")?.ok_or_else(|| anyhow!("연결 종료"))??;
            match m {
                Message::Binary(b) => {
                    let pt = self.opener.open(&b)?;
                    return Ok(match app::decode::<AgentMsg>(&pt)? {
                        Decoded::Control(AgentMsg::SessionEnded { reason }) => bail!("PC 가 연결을 끊음: {reason}"),
                        Decoded::Control(c) => Received::Msg(c),
                        Decoded::Frame(h, data) => Received::Frame(h, data.to_vec()),
                        Decoded::Video(h, _key, data) => Received::Frame(h, data.to_vec()),
                    });
                }
                Message::Text(t) => {
                    if let Ok(RelayToClient::AgentGone) = serde_json::from_str(&t) {
                        bail!("PC 연결이 끊겼습니다");
                    }
                }
                Message::Close(_) => bail!("연결 종료"),
                _ => {}
            }
        }
    }

    async fn expect_msg(&mut self) -> Result<AgentMsg> {
        loop {
            if let Received::Msg(m) = self.recv(Duration::from_secs(15)).await? {
                if let AgentMsg::SessionEnded { reason } | AgentMsg::Denied { reason } = &m {
                    bail!("PC 가 연결을 끊음: {reason}");
                }
                return Ok(m);
            }
        }
    }
}

enum Received {
    Msg(AgentMsg),
    Frame(FrameHeader, Vec<u8>),
}

async fn connect(cli: &Cli, kp: &StaticKeypair) -> Result<Conn> {
    if cli.device.is_empty() {
        bail!("--device 장치 ID 를 지정하세요");
    }
    let url = format!("{}/v1/client/{}", cli.relay.trim_end_matches('/'), cli.device);
    let (mut ws, _) = tokio_tungstenite::connect_async(url.as_str()).await.context("중계 서버 연결 실패")?;
    // 중계 서버 응답 대기
    loop {
        match ws.next().await.ok_or_else(|| anyhow!("중계 서버 연결 종료"))?? {
            Message::Text(t) => match serde_json::from_str::<RelayToClient>(&t)? {
                RelayToClient::Connected => break,
                RelayToClient::Offline => bail!("PC 가 오프라인입니다"),
                RelayToClient::AgentGone => bail!("PC 연결이 끊겼습니다"),
            },
            Message::Close(_) => bail!("중계 서버가 연결을 거부했습니다"),
            _ => {}
        }
    }
    let mut hs = Handshake::initiator(kp)?;
    ws.send(Message::Binary(hs.write()?)).await?;
    let m2 = loop {
        match tokio::time::timeout(Duration::from_secs(15), ws.next()).await?.ok_or_else(|| anyhow!("연결 종료"))?? {
            Message::Binary(b) => break b,
            Message::Close(_) => bail!("연결 종료"),
            _ => {}
        }
    };
    hs.read(&m2)?;
    ws.send(Message::Binary(hs.write()?)).await?;
    let ch = hs.finish()?;
    // 장치 ID 는 PC 공개키의 해시이므로, 입력한 장치 ID 와 맞으면 중간자가 없음이 보장된다.
    if device_id_from_public(&ch.remote_static) != cli.device {
        bail!("보안 경고: PC 공개키가 장치 ID 와 일치하지 않습니다 (중간자 공격 가능성). 연결을 중단합니다.");
    }
    eprintln!("PC 지문 {} 확인, 확인 코드 {}", fingerprint(&ch.remote_static), ch.sas);
    let (sealer, opener) = ch.into_split();
    let mut c = Conn { ws, sealer, opener };
    c.send(&ClientMsg::Hello { client_name: cli.name.clone(), app_version: "hp-cli".into(), protocol: PROTOCOL_VERSION }).await?;
    loop {
        match c.recv(Duration::from_secs(150)).await? {
            Received::Msg(AgentMsg::PairingPending { sas }) => {
                eprintln!("PC 화면에 등록 확인창이 떴습니다. 확인 코드 [{sas}] 가 같으면 PC 에서 [예] 를 누르세요.");
            }
            Received::Msg(AgentMsg::Welcome { device_name, agent_version, permissions, .. }) => {
                eprintln!("접속 성공: {device_name} (에이전트 {agent_version}) 권한 {permissions:?}");
                return Ok(c);
            }
            Received::Msg(AgentMsg::Denied { reason }) => bail!("접속 거부: {reason}"),
            Received::Msg(other) => eprintln!("예상하지 못한 메시지: {other:?}"),
            Received::Frame(..) => {}
        }
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    let _ = rustls::crypto::ring::default_provider().install_default();
    let cli = Cli::parse();
    let kp = load_or_create_key(&cli.key)?;
    if let Cmd::Keygen = cli.cmd {
        println!("{}", B64.encode(kp.public));
        return Ok(());
    }
    let mut c = connect(&cli, &kp).await?;
    match &cli.cmd {
        Cmd::Keygen => unreachable!(),
        Cmd::Connect => {}
        Cmd::Status => {
            c.send(&ClientMsg::GetStatus).await?;
            println!("{}", serde_json::to_string_pretty(&c.expect_msg().await?)?);
        }
        Cmd::Monitors => {
            c.send(&ClientMsg::ListMonitors).await?;
            println!("{}", serde_json::to_string_pretty(&c.expect_msg().await?)?);
        }
        Cmd::Shot { monitor, out, quality, scale } => {
            c.send(&ClientMsg::StartStream {
                monitor: *monitor,
                quality: *quality,
                scale_pct: *scale,
                max_fps: 5,
                codec: String::new(),
                bitrate_kbps: 0,
            })
            .await?;
            loop {
                match c.recv(Duration::from_secs(15)).await? {
                    Received::Frame(h, jpeg) => {
                        std::fs::write(out, &jpeg)?;
                        println!(
                            "저장: {} ({}x{}, 원본 {}x{}, {} KB)",
                            out.display(),
                            h.width,
                            h.height,
                            h.src_width,
                            h.src_height,
                            jpeg.len() / 1024
                        );
                        break;
                    }
                    Received::Msg(AgentMsg::Error { message, .. }) => bail!("{message}"),
                    Received::Msg(_) => {}
                }
            }
            c.send(&ClientMsg::StopStream).await?;
        }
        Cmd::Stream { secs, monitor, quality, scale, fps, codec } => {
            c.send(&ClientMsg::StartStream {
                monitor: *monitor,
                quality: *quality,
                scale_pct: *scale,
                max_fps: *fps,
                codec: codec.clone(),
                bitrate_kbps: 0,
            })
            .await?;
            let t0 = Instant::now();
            let (mut frames, mut bytes) = (0u64, 0u64);
            let mut lat = Vec::new();
            while t0.elapsed() < Duration::from_secs(*secs) {
                match c.recv(Duration::from_secs(15)).await? {
                    Received::Frame(h, data) => {
                        frames += 1;
                        bytes += data.len() as u64;
                        let now = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)?.as_millis() as u64;
                        lat.push(now.saturating_sub(h.captured_ms));
                        c.send(&ClientMsg::FrameAck { frame_id: h.frame_id }).await?;
                    }
                    Received::Msg(AgentMsg::StreamStarted { codec, width, height, .. }) => {
                        eprintln!("전송 방식: {} ({width}x{height})", if codec.is_empty() { "jpeg" } else { &codec });
                    }
                    Received::Msg(_) => {}
                }
            }
            c.send(&ClientMsg::StopStream).await?;
            let s = t0.elapsed().as_secs_f64();
            lat.sort();
            let p50 = lat.get(lat.len() / 2).copied().unwrap_or(0);
            println!(
                "{frames} 프레임 / {s:.1}초 = {:.1} fps, 평균 {:.0} KB/프레임, {:.0} kbps, 지연 중앙값 {p50} ms (같은 PC 시계 기준일 때만 의미 있음)",
                frames as f64 / s,
                bytes as f64 / frames.max(1) as f64 / 1024.0,
                bytes as f64 * 8.0 / s / 1000.0
            );
        }
        Cmd::Move { x, y } => c.send(&ClientMsg::MouseMove { x: *x, y: *y }).await?,
        Cmd::Click { x, y, right, double } => {
            c.send(&ClientMsg::MouseMove { x: *x, y: *y }).await?;
            let button = if *right { MouseButton::Right } else { MouseButton::Left };
            c.send(&ClientMsg::MouseClick { button, double: *double }).await?;
        }
        Cmd::Scroll { dy } => c.send(&ClientMsg::Wheel { dx: 0.0, dy: *dy }).await?,
        Cmd::Type { text } => c.send(&ClientMsg::KeyText { text: text.clone() }).await?,
        Cmd::Key { name } => c.send(&ClientMsg::KeyCombo { keys: vec![name.clone()] }).await?,
        Cmd::Combo { keys } => c.send(&ClientMsg::KeyCombo { keys: keys.clone() }).await?,
        Cmd::Ping { count } => {
            for _ in 0..*count {
                let t = Instant::now();
                c.send(&ClientMsg::Ping { t: 0 }).await?;
                loop {
                    if let AgentMsg::Pong { .. } = c.expect_msg().await? {
                        break;
                    }
                }
                println!("왕복 지연 {} ms", t.elapsed().as_millis());
            }
        }
        Cmd::ClipGet => {
            c.send(&ClientMsg::ClipboardGet).await?;
            loop {
                match c.expect_msg().await? {
                    AgentMsg::Clipboard { text } => {
                        println!("{text}");
                        break;
                    }
                    AgentMsg::Error { message, .. } => bail!("{message}"),
                    _ => {}
                }
            }
        }
        Cmd::ClipSet { text } => c.send(&ClientMsg::ClipboardSet { text: text.clone(), paste: false }).await?,
        Cmd::Ls { path } => {
            c.send(&ClientMsg::FsList { path: path.clone() }).await?;
            loop {
                match c.expect_msg().await? {
                    AgentMsg::FsListing { path, parent, entries } => {
                        println!("[{path}] (상위: {parent})");
                        for e in entries.iter().take(40) {
                            println!(
                                "  {} {}  {}",
                                if e.is_dir { "📁" } else { "  " },
                                e.name,
                                if e.is_dir { String::new() } else { format!("{} B", e.size) }
                            );
                        }
                        break;
                    }
                    AgentMsg::Error { message, .. } => bail!("{message}"),
                    _ => {}
                }
            }
        }
        Cmd::Get { path, out } => {
            let t0 = Instant::now();
            c.send(&ClientMsg::FileDownload { id: 1, path: path.clone() }).await?;
            let mut f = std::fs::File::create(out)?;
            let mut got = 0u64;
            loop {
                match c.expect_msg().await? {
                    AgentMsg::FileChunk { id, offset, total, data, eof } => {
                        use base64::Engine;
                        use std::io::Write;
                        let b = base64::engine::general_purpose::STANDARD.decode(data)?;
                        f.write_all(&b)?;
                        got += b.len() as u64;
                        c.send(&ClientMsg::FileAck { id, offset }).await?;
                        if eof {
                            let s = t0.elapsed().as_secs_f64();
                            println!("받음 {got}/{total} 바이트, {s:.1}초, {:.0} KB/s", got as f64 / 1024.0 / s);
                            break;
                        }
                    }
                    AgentMsg::FileError { message, .. } | AgentMsg::Error { message, .. } => bail!("{message}"),
                    _ => {}
                }
            }
        }
        Cmd::Put { file } => {
            use base64::Engine;
            let data = std::fs::read(file)?;
            let name = file.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
            c.send(&ClientMsg::FileUploadStart { id: 2, name, size: data.len() as u64 }).await?;
            let mut off = 0usize;
            loop {
                match c.expect_msg().await? {
                    AgentMsg::FileAck { .. } if off < data.len() => {
                        let end = (off + 192 * 1024).min(data.len());
                        c.send(&ClientMsg::FileUploadChunk {
                            id: 2,
                            offset: off as u64,
                            data: base64::engine::general_purpose::STANDARD.encode(&data[off..end]),
                        })
                        .await?;
                        off = end;
                    }
                    AgentMsg::FileAck { .. } => c.send(&ClientMsg::FileUploadEnd { id: 2 }).await?,
                    AgentMsg::FileSaved { path, .. } => {
                        println!("PC 에 저장됨: {path}");
                        break;
                    }
                    AgentMsg::FileError { message, .. } | AgentMsg::Error { message, .. } => bail!("{message}"),
                    _ => {}
                }
            }
        }
    }
    // 입력 명령이 처리될 시간을 준 뒤 확인용 Ping 후 종료
    c.send(&ClientMsg::Ping { t: 1 }).await?;
    loop {
        match c.expect_msg().await? {
            AgentMsg::Pong { .. } => break,
            AgentMsg::Error { message, .. } => bail!("PC 오류: {message}"),
            _ => {}
        }
    }
    c.send(&ClientMsg::Bye).await?;
    let _ = c.ws.close(None).await;
    Ok(())
}
