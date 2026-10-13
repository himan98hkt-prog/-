//! PC 고유 키쌍 보관.
//!
//! 비밀키는 Windows DPAPI(현재 사용자 계정에 묶인 암호화)로 보호해서 저장한다.
//! 다른 사용자 계정이나 다른 PC 로 파일을 복사해도 풀 수 없다.

use crate::config::{write_atomic, Paths};
use crate::platform;
use anyhow::{bail, Context, Result};
use homepilot_protocol::secure::StaticKeypair;

const MAGIC_PROTECTED: &[u8; 4] = b"HPK1";

pub fn load_or_create(paths: &Paths) -> Result<StaticKeypair> {
    let file = paths.key_file();
    match std::fs::read(&file) {
        Ok(raw) => {
            if raw.len() < 4 || &raw[..4] != MAGIC_PROTECTED {
                bail!("{} 형식이 올바르지 않습니다", file.display());
            }
            let plain = platform::unprotect(&raw[4..]).context("키 복호화 실패 (다른 계정/PC 에서 복사된 파일일 수 있음)")?;
            if plain.len() != 64 {
                bail!("키 길이가 올바르지 않습니다");
            }
            Ok(StaticKeypair::from_bytes(&plain[..32], &plain[32..])?)
        }
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            let kp = StaticKeypair::generate()?;
            let mut plain = Vec::with_capacity(64);
            plain.extend_from_slice(&kp.private);
            plain.extend_from_slice(&kp.public);
            let mut out = MAGIC_PROTECTED.to_vec();
            out.extend(platform::protect(&plain)?);
            write_atomic(&file, &out)?;
            tracing::info!("새 장치 키를 만들었습니다");
            Ok(kp)
        }
        Err(e) => Err(e).with_context(|| format!("{} 읽기 실패", file.display())),
    }
}
