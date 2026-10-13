//! 중계 서버 ↔ 에이전트/클라이언트 사이의 제어 메시지 (WebSocket 텍스트 프레임).

use serde::{Deserialize, Serialize};

/// 중계 서버가 에이전트에게 보내는 제어 메시지.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "t", rename_all = "snake_case")]
pub enum RelayToAgent {
    /// 등록 완료.
    Registered { device_id: String },
    /// 새 클라이언트가 연결됨. 이후 이 sid 로 바이너리 프레임이 온다.
    Open { sid: u32 },
    /// 클라이언트 연결이 끊김.
    Close { sid: u32 },
    /// 연결 유지 확인.
    Ping,
}

/// 에이전트가 중계 서버에 보내는 제어 메시지.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "t", rename_all = "snake_case")]
pub enum AgentToRelay {
    /// 해당 세션을 끊어 달라 (인증 실패, 긴급 차단 등).
    Kick {
        sid: u32,
    },
    Pong,
}

/// 중계 서버가 클라이언트에게 보내는 제어 메시지.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "t", rename_all = "snake_case")]
pub enum RelayToClient {
    /// PC(에이전트)와 연결됨. 이제 핸드셰이크를 시작하면 된다.
    Connected,
    /// PC 가 오프라인.
    Offline,
    /// PC 연결이 끊김.
    AgentGone,
}

/// 바이너리 중계 프레임: 에이전트 쪽에서는 `[sid u32 BE][payload]`, 클라이언트 쪽에서는 payload 그대로.
pub fn encode_agent_frame(sid: u32, payload: &[u8]) -> Vec<u8> {
    let mut v = Vec::with_capacity(4 + payload.len());
    v.extend_from_slice(&sid.to_be_bytes());
    v.extend_from_slice(payload);
    v
}

pub fn decode_agent_frame(frame: &[u8]) -> Option<(u32, &[u8])> {
    if frame.len() < 4 {
        return None;
    }
    let sid = u32::from_be_bytes([frame[0], frame[1], frame[2], frame[3]]);
    Some((sid, &frame[4..]))
}

/// 장치 ID 형식 검사: 소문자 16진수 20자 (공개키 SHA-256 앞 10바이트).
pub fn is_valid_device_id(id: &str) -> bool {
    id.len() == 20 && id.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn agent_frame_roundtrip() {
        let f = encode_agent_frame(7, b"abc");
        assert_eq!(decode_agent_frame(&f), Some((7, &b"abc"[..])));
        assert_eq!(decode_agent_frame(&[1, 2]), None);
    }

    #[test]
    fn relay_json_shape() {
        let s = serde_json::to_string(&RelayToAgent::Open { sid: 3 }).unwrap();
        assert_eq!(s, r#"{"t":"open","sid":3}"#);
    }

    #[test]
    fn device_id_validation() {
        assert!(is_valid_device_id("0123456789abcdef0123"));
        assert!(!is_valid_device_id("0123456789ABCDEF0123"));
        assert!(!is_valid_device_id("../etc"));
    }
}
