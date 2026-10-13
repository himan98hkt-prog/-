//! 등록(신뢰)된 휴대폰 목록과 기기별 권한.

use crate::config::{write_atomic, Paths};
use anyhow::{Context, Result};
use base64::engine::general_purpose::STANDARD as B64;
use base64::Engine;
use homepilot_protocol::app::Permissions;
use homepilot_protocol::secure::fingerprint;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct TrustedClient {
    pub name: String,
    /// X25519 공개키 (base64)
    pub public_key: String,
    pub fingerprint: String,
    pub permissions: Permissions,
    pub added_at: u64,
    #[serde(default)]
    pub last_seen: Option<u64>,
}

pub struct TrustStore {
    path: PathBuf,
    pub clients: Vec<TrustedClient>,
}

pub fn now_unix() -> u64 {
    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

impl TrustStore {
    pub fn load(paths: &Paths) -> Result<Self> {
        let path = paths.trust_file();
        let clients = match std::fs::read(&path) {
            Ok(b) => serde_json::from_slice(&b).with_context(|| format!("{} 형식 오류", path.display()))?,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Vec::new(),
            Err(e) => return Err(e).with_context(|| format!("{} 읽기 실패", path.display())),
        };
        Ok(Self { path, clients })
    }

    pub fn save(&self) -> Result<()> {
        write_atomic(&self.path, &serde_json::to_vec_pretty(&self.clients)?)
    }

    pub fn find(&self, public: &[u8; 32]) -> Option<&TrustedClient> {
        let b = B64.encode(public);
        self.clients.iter().find(|c| c.public_key == b)
    }

    /// 등록 또는 갱신. 같은 키가 이미 있으면 이름·권한만 바꾼다.
    pub fn add(&mut self, name: &str, public: &[u8; 32], permissions: Permissions) -> TrustedClient {
        let b = B64.encode(public);
        let name: String = name.chars().filter(|c| !c.is_control()).take(64).collect();
        if let Some(c) = self.clients.iter_mut().find(|c| c.public_key == b) {
            c.name = name;
            c.permissions = permissions;
            return c.clone();
        }
        let c = TrustedClient { name, public_key: b, fingerprint: fingerprint(public), permissions, added_at: now_unix(), last_seen: None };
        self.clients.push(c.clone());
        c
    }

    pub fn touch(&mut self, public: &[u8; 32]) {
        let b = B64.encode(public);
        if let Some(c) = self.clients.iter_mut().find(|c| c.public_key == b) {
            c.last_seen = Some(now_unix());
        }
    }

    /// 지문 또는 이름으로 등록 해제. 해제된 개수를 돌려준다.
    pub fn revoke(&mut self, who: &str) -> usize {
        let before = self.clients.len();
        self.clients.retain(|c| c.fingerprint != who && c.name != who);
        before - self.clients.len()
    }
}

pub fn parse_public_key(b64: &str) -> Result<[u8; 32]> {
    let v = B64.decode(b64.trim()).context("base64 형식이 아닙니다")?;
    v.try_into().map_err(|_| anyhow::anyhow!("공개키는 32바이트여야 합니다"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_find_revoke() {
        let dir = std::env::temp_dir().join(format!("hp-trust-{}", rand::random::<u64>()));
        std::fs::create_dir_all(&dir).unwrap();
        let paths = Paths { data_dir: dir.clone(), log_dir: dir.clone() };
        let mut s = TrustStore::load(&paths).unwrap();
        let k = [7u8; 32];
        assert!(s.find(&k).is_none());
        let c = s.add("내 폰\u{7}", &k, Permissions::default_for_new_device());
        assert_eq!(c.name, "내 폰");
        s.save().unwrap();
        let mut s2 = TrustStore::load(&paths).unwrap();
        assert!(s2.find(&k).unwrap().permissions.control);
        assert!(!s2.find(&k).unwrap().permissions.files, "파일 권한은 기본으로 꺼져 있어야 함");
        assert_eq!(s2.revoke(&c.fingerprint), 1);
        assert!(s2.find(&k).is_none());
        std::fs::remove_dir_all(dir).ok();
    }
}
