//! 주소 안내판(directory): PC 의 현재 접속 주소를 무료 공개 게시판(기본 ntfy.sh)에 암호화해 올려 두고,
//! 등록된 휴대폰이 주소가 바뀌어도 스스로 찾아가게 한다. 계정·서버 비용이 들지 않는다.
//!
//! - 주제(topic)와 암호 키는 PC 공개키에서 만든다. PC 공개키는 등록(페어링)된 휴대폰만 알고 있으므로
//!   장치 ID 만 아는 사람은 주제를 찾을 수 없다.
//! - 게시판 운영자는 암호문만 본다.
//! - 위조 기록으로 가짜 주소를 알려 줘도, 휴대폰은 Noise 핸드셰이크에서 장치 ID(=PC 공개키 해시)를
//!   확인하므로 가짜 PC 에 연결되지 않는다 (최악은 연결 실패).
//!
//! 기록: `base64url(nonce 12B || ChaCha20-Poly1305(key, nonce, json, aad=topic))`

use base64::Engine;
use chacha20poly1305::aead::{Aead, KeyInit, Payload};
use chacha20poly1305::{ChaCha20Poly1305, Nonce};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// 기본 게시판 (ntfy.sh: 계정 없이 쓰는 공개 알림 서비스, 메시지 12시간 보관)
pub const DEFAULT_DIRECTORY: &str = "https://ntfy.sh";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DirectoryRecord {
    pub v: u32,
    /// 장치 ID (확인용)
    pub id: String,
    /// 외부 접속 주소 (터널). 없으면 빈 문자열
    #[serde(default)]
    pub url: String,
    /// 같은 Wi-Fi 에서 바로 접속할 주소 목록 ("192.168.0.5:8443")
    #[serde(default)]
    pub lan: Vec<String>,
    /// 올린 시각(유닉스 초). 휴대폰은 더 최신 기록만 받아들인다.
    pub ts: u64,
}

fn hash(label: &[u8], pc_public: &[u8]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(label);
    h.update(pc_public);
    h.finalize().into()
}

/// 게시판 주제 이름: "hp" + 해시 앞 15바이트(16진수 30자)
pub fn topic(pc_public: &[u8]) -> String {
    let h = hash(b"homepilot-dir-topic-v1", pc_public);
    let hex: String = h[..15].iter().map(|b| format!("{b:02x}")).collect();
    format!("hp{hex}")
}

fn key(pc_public: &[u8]) -> [u8; 32] {
    hash(b"homepilot-dir-key-v1", pc_public)
}

pub fn seal(pc_public: &[u8], rec: &DirectoryRecord, nonce: [u8; 12]) -> String {
    let json = serde_json::to_vec(rec).expect("직렬화");
    let t = topic(pc_public);
    let cipher = ChaCha20Poly1305::new(&key(pc_public).into());
    let ct = cipher.encrypt(Nonce::from_slice(&nonce), Payload { msg: &json, aad: t.as_bytes() }).expect("암호화");
    let mut out = nonce.to_vec();
    out.extend_from_slice(&ct);
    base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(out)
}

pub fn open(pc_public: &[u8], text: &str) -> Option<DirectoryRecord> {
    let raw = base64::engine::general_purpose::URL_SAFE_NO_PAD.decode(text.trim()).ok()?;
    if raw.len() < 12 + 16 {
        return None;
    }
    let t = topic(pc_public);
    let cipher = ChaCha20Poly1305::new(&key(pc_public).into());
    let pt = cipher.decrypt(Nonce::from_slice(&raw[..12]), Payload { msg: &raw[12..], aad: t.as_bytes() }).ok()?;
    serde_json::from_slice(&pt).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 휴대폰 앱(Dart) 테스트와 같은 값. 바꾸면 android-app/test/directory_test.dart 도 바꿀 것.
    pub const VECTOR_PK: [u8; 32] = [7u8; 32];

    fn rec() -> DirectoryRecord {
        DirectoryRecord {
            v: 1,
            id: "f685fa3773a954e5b5a1".into(),
            url: "https://a-b.trycloudflare.com".into(),
            lan: vec!["192.168.0.5:8443".into()],
            ts: 1_700_000_000,
        }
    }

    #[test]
    fn roundtrip_and_tamper() {
        let s = seal(&VECTOR_PK, &rec(), [1u8; 12]);
        assert_eq!(open(&VECTOR_PK, &s), Some(rec()));
        // 다른 PC 키로는 열 수 없다
        assert_eq!(open(&[8u8; 32], &s), None);
        // 한 글자라도 바뀌면 거부
        let mut bad = s.clone().into_bytes();
        let i = bad.len() - 3;
        bad[i] = if bad[i] == b'A' { b'B' } else { b'A' };
        assert_eq!(open(&VECTOR_PK, &String::from_utf8(bad).unwrap()), None);
    }

    #[test]
    fn cross_language_vector() {
        // Dart 쪽 테스트가 이 값을 그대로 복호화한다.
        assert_eq!(topic(&VECTOR_PK), "hp2d1b264484501029dce89e607a5056");
        let s = seal(&VECTOR_PK, &rec(), [1u8; 12]);
        println!("VECTOR {s}");
        assert!(open(&VECTOR_PK, &s).is_some());
    }
}
