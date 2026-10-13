//! 설정과 데이터 폴더.
//!
//! Windows: 설정·키 = %APPDATA%\HomePilot\Agent, 로그 = %LOCALAPPDATA%\HomePilot\Agent\logs
//! 테스트/개발 시 `HOMEPILOT_AGENT_HOME` 환경변수로 폴더를 바꿀 수 있다.

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone)]
pub struct Paths {
    pub data_dir: PathBuf,
    pub log_dir: PathBuf,
}

impl Paths {
    pub fn resolve() -> Result<Self> {
        if let Some(home) = std::env::var_os("HOMEPILOT_AGENT_HOME") {
            let base = PathBuf::from(home);
            return Ok(Self { log_dir: base.join("logs"), data_dir: base });
        }
        let data = dirs::config_dir().context("설정 폴더를 찾을 수 없습니다")?;
        let local = dirs::data_local_dir().unwrap_or_else(|| data.clone());
        Ok(Self { data_dir: data.join("HomePilot").join("Agent"), log_dir: local.join("HomePilot").join("Agent").join("logs") })
    }

    pub fn ensure(&self) -> Result<()> {
        std::fs::create_dir_all(&self.data_dir).with_context(|| format!("{} 생성 실패", self.data_dir.display()))?;
        std::fs::create_dir_all(&self.log_dir).with_context(|| format!("{} 생성 실패", self.log_dir.display()))?;
        Ok(())
    }

    pub fn config_file(&self) -> PathBuf {
        self.data_dir.join("config.json")
    }
    pub fn key_file(&self) -> PathBuf {
        self.data_dir.join("device.key")
    }
    pub fn trust_file(&self) -> PathBuf {
        self.data_dir.join("trusted_clients.json")
    }
    pub fn audit_file(&self) -> PathBuf {
        self.log_dir.join("connections.jsonl")
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct Config {
    /// 중계 서버 주소. 예: wss://relay.example.com  (로컬 개발: ws://127.0.0.1:8443)
    pub relay_url: String,
    /// 휴대폰에 표시될 PC 이름. 비어 있으면 컴퓨터 이름.
    pub device_name: String,
    /// 긴급 차단 상태. true 이면 PC 에서 다시 허용하기 전까지 모든 원격 접속을 거부한다.
    pub remote_blocked: bool,
    /// 원격 제어 중 화면 상단 표시줄을 띄운다 (끄는 것을 권장하지 않음).
    pub show_overlay: bool,
    /// 동시에 허용할 원격 세션 수.
    pub max_sessions: u32,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            relay_url: "ws://127.0.0.1:8443".into(),
            device_name: String::new(),
            remote_blocked: false,
            show_overlay: true,
            max_sessions: 2,
        }
    }
}

impl Config {
    pub fn load(path: &Path) -> Result<Self> {
        match std::fs::read(path) {
            Ok(b) => serde_json::from_slice(&b).with_context(|| format!("{} 형식 오류", path.display())),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(Self::default()),
            Err(e) => Err(e).with_context(|| format!("{} 읽기 실패", path.display())),
        }
    }

    pub fn save(&self, path: &Path) -> Result<()> {
        write_atomic(path, &serde_json::to_vec_pretty(self)?)
    }

    pub fn display_name(&self) -> String {
        if !self.device_name.trim().is_empty() {
            return self.device_name.trim().to_string();
        }
        sysinfo::System::host_name().unwrap_or_else(|| "Windows PC".into())
    }
}

/// 임시 파일에 쓴 뒤 교체해서, 쓰는 도중 꺼져도 파일이 깨지지 않게 한다.
pub fn write_atomic(path: &Path, data: &[u8]) -> Result<()> {
    let tmp = path.with_extension("tmp");
    std::fs::write(&tmp, data).with_context(|| format!("{} 쓰기 실패", tmp.display()))?;
    std::fs::rename(&tmp, path).with_context(|| format!("{} 저장 실패", path.display()))?;
    Ok(())
}
