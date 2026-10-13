//! 응용 계층 메시지 (암호화 채널 안에서 오가는 내용).
//!
//! 평문 첫 바이트: 0x01 = 제어 JSON, 0x02 = 화면 프레임(바이너리 헤더 + JPEG).

use serde::{Deserialize, Serialize};

pub const KIND_CONTROL: u8 = 0x01;
pub const KIND_FRAME: u8 = 0x02;

/// 기기별 권한. 원격 화면/조작과 파일 전송 권한을 분리한다.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Default)]
pub struct Permissions {
    /// 화면 보기 + 상태 조회
    pub view: bool,
    /// 마우스·키보드 조작
    pub control: bool,
    /// 파일 전송 (Phase 2 이후)
    pub files: bool,
    /// 등록된 AI 프로그램 관리 (Phase 4)
    pub apps: bool,
}

impl Permissions {
    /// 신규 등록 기기의 기본 권한: 보기 + 조작. 파일·앱 관리는 PC 에서 별도로 허용해야 한다.
    pub fn default_for_new_device() -> Self {
        Self { view: true, control: true, files: false, apps: false }
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MouseButton {
    Left,
    Right,
    Middle,
}

/// 클라이언트(휴대폰) → PC 에이전트.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ClientMsg {
    /// 핸드셰이크 직후 첫 메시지.
    Hello {
        client_name: String,
        app_version: String,
        protocol: u32,
    },
    GetStatus,
    ListMonitors,
    /// 화면 전송 시작. quality 10~95, scale_pct 10~100, max_fps 1~30.
    StartStream {
        monitor: u32,
        quality: u8,
        scale_pct: u8,
        max_fps: u8,
    },
    StopStream,
    /// 프레임 수신 확인 (흐름 제어 + 지연 측정).
    FrameAck {
        frame_id: u32,
    },
    /// 좌표는 현재 모니터 기준 0.0~1.0 비율.
    MouseMove {
        x: f32,
        y: f32,
    },
    MouseButton {
        button: MouseButton,
        down: bool,
    },
    MouseClick {
        button: MouseButton,
        double: bool,
    },
    /// 휠: 한 칸 = 1.0 (양수 dy = 위로).
    Wheel {
        dx: f32,
        dy: f32,
    },
    /// 완성된 문자열 입력 (한글 포함). IME 조합은 휴대폰에서 끝낸 뒤 보낸다.
    KeyText {
        text: String,
    },
    /// 특수키 (예: "enter", "backspace", "ctrl", "a", "f5").
    Key {
        key: String,
        down: bool,
    },
    /// 조합키 한 번 누르기 (예: ["ctrl","c"]).
    KeyCombo {
        keys: Vec<String>,
    },
    Ping {
        t: u64,
    },
    /// 세션 종료.
    Bye,
}

/// PC 에이전트 → 클라이언트.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum AgentMsg {
    Welcome {
        device_name: String,
        agent_version: String,
        protocol: u32,
        permissions: Permissions,
        /// 같은 Wi-Fi 바로 접속 주소 ("192.168.0.5:8443"). 휴대폰이 다음부터 먼저 시도한다.
        #[serde(default)]
        lan: Vec<String>,
        /// 현재 외부 접속 주소 (터널). 휴대폰이 저장해 둔 주소를 갱신한다.
        #[serde(default)]
        public_url: String,
    },
    /// 미등록 기기: PC 화면에 확인창이 떴으니 같은 코드인지 확인하라는 안내.
    PairingPending {
        sas: String,
    },
    /// 등록 거부/미허용으로 연결 종료.
    Denied {
        reason: String,
    },
    Status(SystemStatus),
    Monitors {
        monitors: Vec<MonitorInfo>,
    },
    StreamStarted {
        monitor: u32,
        width: u32,
        height: u32,
    },
    StreamStopped,
    Pong {
        t: u64,
    },
    Error {
        code: String,
        message: String,
    },
    /// PC 쪽에서 세션 종료 (긴급 차단 등).
    SessionEnded {
        reason: String,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct MonitorInfo {
    pub index: u32,
    pub name: String,
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
    pub primary: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct DiskStatus {
    pub mount: String,
    pub total_bytes: u64,
    pub available_bytes: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct SystemStatus {
    pub hostname: String,
    pub os: String,
    pub uptime_secs: u64,
    pub cpu_percent: f32,
    pub mem_total_bytes: u64,
    pub mem_used_bytes: u64,
    /// GPU 사용률. 측정 불가 시 None (지원하지 않는 기능을 0% 로 속이지 않는다).
    pub gpu_percent: Option<f32>,
    pub disks: Vec<DiskStatus>,
    pub active_sessions: u32,
}

/// 화면 프레임 헤더 (리틀 엔디언, 고정 29바이트) + JPEG.
#[derive(Debug, Clone, PartialEq)]
pub struct FrameHeader {
    pub frame_id: u32,
    pub monitor: u8,
    /// 인코딩된 이미지 크기
    pub width: u32,
    pub height: u32,
    /// 원본 모니터 해상도
    pub src_width: u32,
    pub src_height: u32,
    /// 캡처 시각 (에이전트 기준 Unix ms)
    pub captured_ms: u64,
}

const FRAME_HEADER_LEN: usize = 1 + 4 + 1 + 4 * 4 + 8;

pub fn encode_control<T: Serialize>(msg: &T) -> Vec<u8> {
    let mut v = vec![KIND_CONTROL];
    serde_json::to_writer(&mut v, msg).expect("직렬화는 실패하지 않음");
    v
}

pub fn encode_frame(h: &FrameHeader, jpeg: &[u8]) -> Vec<u8> {
    let mut v = Vec::with_capacity(FRAME_HEADER_LEN + jpeg.len());
    v.push(KIND_FRAME);
    v.extend_from_slice(&h.frame_id.to_le_bytes());
    v.push(h.monitor);
    v.extend_from_slice(&h.width.to_le_bytes());
    v.extend_from_slice(&h.height.to_le_bytes());
    v.extend_from_slice(&h.src_width.to_le_bytes());
    v.extend_from_slice(&h.src_height.to_le_bytes());
    v.extend_from_slice(&h.captured_ms.to_le_bytes());
    v.extend_from_slice(jpeg);
    v
}

/// 복호화된 응용 메시지.
#[derive(Debug)]
pub enum Decoded<'a, T> {
    Control(T),
    Frame(FrameHeader, &'a [u8]),
}

#[derive(Debug, thiserror::Error)]
pub enum DecodeError {
    #[error("빈 메시지")]
    Empty,
    #[error("알 수 없는 종류: {0}")]
    UnknownKind(u8),
    #[error("JSON 오류: {0}")]
    Json(#[from] serde_json::Error),
    #[error("프레임 헤더가 잘림")]
    Truncated,
}

pub fn decode<'a, T: for<'de> Deserialize<'de>>(buf: &'a [u8]) -> Result<Decoded<'a, T>, DecodeError> {
    match buf.first() {
        None => Err(DecodeError::Empty),
        Some(&KIND_CONTROL) => Ok(Decoded::Control(serde_json::from_slice(&buf[1..])?)),
        Some(&KIND_FRAME) => {
            if buf.len() < FRAME_HEADER_LEN {
                return Err(DecodeError::Truncated);
            }
            let u32_at = |i: usize| u32::from_le_bytes(buf[i..i + 4].try_into().unwrap());
            let h = FrameHeader {
                frame_id: u32_at(1),
                monitor: buf[5],
                width: u32_at(6),
                height: u32_at(10),
                src_width: u32_at(14),
                src_height: u32_at(18),
                captured_ms: u64::from_le_bytes(buf[22..30].try_into().unwrap()),
            };
            Ok(Decoded::Frame(h, &buf[FRAME_HEADER_LEN..]))
        }
        Some(&k) => Err(DecodeError::UnknownKind(k)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn control_roundtrip_korean() {
        let m = ClientMsg::KeyText { text: "안녕하세요 HomePilot".into() };
        let b = encode_control(&m);
        match decode::<ClientMsg>(&b).unwrap() {
            Decoded::Control(x) => assert_eq!(x, m),
            _ => panic!(),
        }
    }

    #[test]
    fn control_json_shape_is_stable() {
        // Android 앱(Dart)과 맞춰야 하는 형식이므로 고정한다.
        let s = serde_json::to_string(&ClientMsg::MouseClick { button: MouseButton::Right, double: false }).unwrap();
        assert_eq!(s, r#"{"type":"mouse_click","button":"right","double":false}"#);
    }

    #[test]
    fn frame_roundtrip() {
        let h = FrameHeader { frame_id: 9, monitor: 1, width: 960, height: 540, src_width: 1920, src_height: 1080, captured_ms: 1234567 };
        let b = encode_frame(&h, b"\xff\xd8jpeg");
        assert_eq!(b.len(), FRAME_HEADER_LEN + 6);
        match decode::<AgentMsg>(&b).unwrap() {
            Decoded::Frame(h2, data) => {
                assert_eq!(h2, h);
                assert_eq!(data, b"\xff\xd8jpeg");
            }
            _ => panic!(),
        }
        assert!(matches!(decode::<AgentMsg>(&b[..10]), Err(DecodeError::Truncated)));
    }
}
