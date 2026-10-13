//! Windows 가 아닌 환경용 대체 구현 (개발·CI 테스트 전용).
//! - 화면: 움직이는 테스트 패턴
//! - 입력: 실제로 보내지 않고 기록만 남김 (테스트에서 확인)
//! - 키 보호: DPAPI 가 없으므로 평문 + 경고 (제품 배포 대상 아님)

use super::{InputAction, RawFrame};
use crate::app::Shared;
use anyhow::{bail, Result};
use homepilot_protocol::app::MonitorInfo;
use std::sync::{Arc, Mutex};

pub fn init_process() {}

pub fn protect(data: &[u8]) -> Result<Vec<u8>> {
    tracing::warn!("이 OS 에는 DPAPI 가 없어 장치 키를 보호 없이 저장합니다 (개발용)");
    Ok(data.to_vec())
}

pub fn unprotect(data: &[u8]) -> Result<Vec<u8>> {
    Ok(data.to_vec())
}

pub fn list_monitors() -> Result<Vec<MonitorInfo>> {
    Ok(vec![
        MonitorInfo { index: 0, name: "TEST-1".into(), x: 0, y: 0, width: 1280, height: 720, primary: true },
        MonitorInfo { index: 1, name: "TEST-2".into(), x: 1280, y: 0, width: 800, height: 600, primary: false },
    ])
}

pub struct Capturer {
    mon: MonitorInfo,
    tick: u32,
}

impl Capturer {
    pub fn new(mon: &MonitorInfo) -> Result<Self> {
        Ok(Self { mon: mon.clone(), tick: 0 })
    }

    pub fn capture(&mut self, out: &mut RawFrame) -> Result<()> {
        let (w, h) = (self.mon.width, self.mon.height);
        out.width = w;
        out.height = h;
        out.bgra.resize((w * h * 4) as usize, 0);
        self.tick = self.tick.wrapping_add(1);
        let t = self.tick;
        for y in 0..h {
            for x in 0..w {
                let i = ((y * w + x) * 4) as usize;
                let bar = ((x + t * 8) / 64).is_multiple_of(2);
                out.bgra[i] = (x * 255 / w) as u8;
                out.bgra[i + 1] = (y * 255 / h) as u8;
                out.bgra[i + 2] = if bar { 200 } else { 40 };
                out.bgra[i + 3] = 255;
            }
        }
        Ok(())
    }
}

pub static INPUT_LOG: Mutex<Vec<InputAction>> = Mutex::new(Vec::new());

pub struct Input;

impl Input {
    pub fn new() -> Self {
        Input
    }
    pub fn apply(&mut self, a: InputAction) -> Result<()> {
        if let InputAction::Key { key, .. } = &a {
            if key_to_code(key).is_none() {
                bail!("알 수 없는 키: {key}");
            }
        }
        tracing::debug!(?a, "입력(기록만)");
        INPUT_LOG.lock().unwrap().push(a);
        Ok(())
    }
}

/// 지원 키 이름 확인 (Windows 쪽과 같은 이름 집합).
pub fn key_to_code(key: &str) -> Option<u16> {
    crate::input::key_name_to_vk(key)
}

pub struct GpuSampler;
impl GpuSampler {
    pub fn new() -> Self {
        GpuSampler
    }
    pub fn sample(&mut self) -> Option<f32> {
        None
    }
}

pub fn autostart_get() -> Result<bool> {
    Ok(false)
}

pub fn autostart_set(_on: bool) -> Result<()> {
    bail!("자동 실행 설정은 Windows 에서만 지원합니다")
}

pub fn open_folder(path: &std::path::Path) {
    println!("폴더: {}", path.display());
}

/// 화면이 없는 환경: 승인할 사람이 없으므로 거부 (`--console` 사용 시 콘솔 승인으로 대체됨).
pub fn ask_pairing_approval(_client_name: &str, _fingerprint: &str, _sas: &str) -> bool {
    false
}

pub fn show_message(title: &str, text: &str) {
    println!("[{title}] {text}");
}

/// 콘솔 모드: UI 없음. Ctrl+C 로 종료.
pub fn run_ui(_shared: Arc<Shared>, rt: &tokio::runtime::Runtime) -> Result<()> {
    rt.block_on(async {
        tokio::signal::ctrl_c().await.ok();
    });
    Ok(())
}

pub fn attach_parent_console() {}

/// 중복 실행 방지 (개발 환경에서는 검사하지 않음).
pub struct InstanceGuard;

pub fn single_instance() -> Option<InstanceGuard> {
    Some(InstanceGuard)
}

/// H.264 압축은 Windows Media Foundation 전용. 다른 OS(개발·CI)에서는 JPEG 로 대체된다.
pub struct H264Encoder;

impl H264Encoder {
    pub fn new(_w: u32, _h: u32, _fps: u32, _bitrate: u32) -> Result<Self> {
        anyhow::bail!("이 OS 에서는 H.264 를 지원하지 않음")
    }
    pub fn force_keyframe(&self) {}
    pub fn encode(&mut self, _frame: &RawFrame) -> Result<Option<(Vec<u8>, bool)>> {
        Ok(None)
    }
}

/// 하위 프로세스를 에이전트 수명에 묶기 (Windows 전용, 여기서는 아무것도 하지 않음).
pub fn bind_child_to_agent(_child: &tokio::process::Child) {}
