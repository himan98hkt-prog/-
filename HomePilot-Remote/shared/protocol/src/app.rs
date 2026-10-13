//! 응용 계층 메시지 (암호화 채널 안에서 오가는 내용).
//!
//! 평문 첫 바이트: 0x01 = 제어 JSON, 0x02 = 화면 프레임(바이너리 헤더 + JPEG),
//! 0x03 = 동영상 프레임(같은 헤더 + 플래그 1바이트 + H.264 Annex-B).

use serde::{Deserialize, Serialize};

pub const KIND_CONTROL: u8 = 0x01;
pub const KIND_FRAME: u8 = 0x02;
pub const KIND_VIDEO: u8 = 0x03;
/// PC 소리: [0x04][캡처 시각 u64 LE][AAC-LC ADTS 프레임들] (48kHz 스테레오)
pub const KIND_AUDIO: u8 = 0x04;
/// 동영상 프레임 플래그: 키프레임(IDR, SPS/PPS 포함) — 디코더는 여기서부터 시작할 수 있다.
pub const VIDEO_FLAG_KEY: u8 = 0x01;

/// 화면 전송 방식
pub const CODEC_JPEG: &str = "jpeg";
pub const CODEC_H264: &str = "h264";

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
        /// "h264" 이면 동영상 압축(대역폭 1/5~1/10). 비우거나 "jpeg" 이면 예전 방식.
        /// PC 가 H.264 를 못 쓰면 jpeg 로 시작하고 StreamStarted.codec 으로 알려 준다.
        #[serde(default)]
        codec: String,
        /// H.264 목표 비트레이트(kbps). 0 이면 화질·크기에 맞춰 자동.
        #[serde(default)]
        bitrate_kbps: u32,
    },
    StopStream,
    /// 동영상 디코더가 처음 시작하거나 오류가 나면 키프레임을 요청한다.
    RequestKeyframe,
    /// PC 소리 듣기 시작/중지 → AudioStarted / Error
    StartAudio,
    StopAudio,
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

    // ---------- 클립보드 (조작 권한 필요) ----------
    /// 휴대폰 → PC 클립보드. paste 면 이어서 Ctrl+V 를 누른다.
    ClipboardSet {
        text: String,
        #[serde(default)]
        paste: bool,
    },
    /// PC 클립보드 내용 요청 → Clipboard
    ClipboardGet,

    // ---------- 파일 (파일 권한 필요, 처음 한 번 PC 에서 승인) ----------
    /// 폴더 목록. path 가 비어 있으면 자주 쓰는 폴더 + 드라이브 목록 → FsListing
    FsList {
        path: String,
    },
    /// PC → 휴대폰 파일 받기 → FileChunk 들 (휴대폰은 FileAck 로 확인)
    FileDownload {
        id: u32,
        path: String,
    },
    /// 휴대폰 → PC 파일 보내기 시작 (PC 의 다운로드\HomePilot 에 저장)
    FileUploadStart {
        id: u32,
        name: String,
        size: u64,
    },
    FileUploadChunk {
        id: u32,
        offset: u64,
        /// base64
        data: String,
    },
    FileUploadEnd {
        id: u32,
    },
    /// 받은 파일 조각 확인 (다음 조각을 보내도 된다)
    FileAck {
        id: u32,
        offset: u64,
    },
    /// 진행 중인 파일 전송 취소
    FileCancel {
        id: u32,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct FsEntry {
    pub name: String,
    /// 전체 경로
    pub path: String,
    pub is_dir: bool,
    pub size: u64,
    /// 수정 시각 (유닉스 초)
    pub modified: u64,
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
        /// 실제로 쓰는 전송 방식 ("jpeg" | "h264")
        #[serde(default)]
        codec: String,
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
    Clipboard {
        text: String,
    },
    /// 소리 전송 시작 (codec "aac", ADTS)
    AudioStarted {
        codec: String,
        sample_rate: u32,
        channels: u32,
    },
    FsListing {
        path: String,
        /// 상위 폴더 (없으면 빈 문자열 = 처음 목록)
        parent: String,
        entries: Vec<FsEntry>,
    },
    /// PC → 휴대폰 파일 조각
    FileChunk {
        id: u32,
        offset: u64,
        total: u64,
        /// base64
        data: String,
        eof: bool,
    },
    /// 휴대폰이 보낸 조각을 받아 저장함
    FileAck {
        id: u32,
        offset: u64,
    },
    /// 휴대폰이 보낸 파일 저장 완료 (PC 의 저장 경로)
    FileSaved {
        id: u32,
        path: String,
    },
    /// 파일 전송 실패
    FileError {
        id: u32,
        message: String,
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

/// 동영상 프레임: 화면 프레임과 같은 헤더 뒤에 플래그 1바이트 + H.264 Annex-B 데이터.
pub fn encode_video(h: &FrameHeader, key: bool, h264: &[u8]) -> Vec<u8> {
    let mut v = encode_frame(h, &[]);
    v[0] = KIND_VIDEO;
    v.push(if key { VIDEO_FLAG_KEY } else { 0 });
    v.extend_from_slice(h264);
    v
}

pub fn encode_audio(captured_ms: u64, aac: &[u8]) -> Vec<u8> {
    let mut v = Vec::with_capacity(9 + aac.len());
    v.push(KIND_AUDIO);
    v.extend_from_slice(&captured_ms.to_le_bytes());
    v.extend_from_slice(aac);
    v
}

/// 복호화된 응용 메시지.
#[derive(Debug)]
pub enum Decoded<'a, T> {
    Control(T),
    Frame(FrameHeader, &'a [u8]),
    /// (헤더, 키프레임 여부, H.264 데이터)
    Video(FrameHeader, bool, &'a [u8]),
    /// (캡처 시각, AAC ADTS)
    Audio(u64, &'a [u8]),
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
        Some(&k @ (KIND_FRAME | KIND_VIDEO)) => {
            let need = FRAME_HEADER_LEN + usize::from(k == KIND_VIDEO);
            if buf.len() < need {
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
            if k == KIND_VIDEO {
                Ok(Decoded::Video(h, buf[FRAME_HEADER_LEN] & VIDEO_FLAG_KEY != 0, &buf[need..]))
            } else {
                Ok(Decoded::Frame(h, &buf[FRAME_HEADER_LEN..]))
            }
        }
        Some(&KIND_AUDIO) => {
            if buf.len() < 9 {
                return Err(DecodeError::Truncated);
            }
            Ok(Decoded::Audio(u64::from_le_bytes(buf[1..9].try_into().unwrap()), &buf[9..]))
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

    #[test]
    fn video_roundtrip() {
        let h = FrameHeader { frame_id: 3, monitor: 0, width: 1280, height: 720, src_width: 1920, src_height: 1080, captured_ms: 99 };
        let nal = [0u8, 0, 0, 1, 0x67, 0x42];
        let b = encode_video(&h, true, &nal);
        assert_eq!(b[0], KIND_VIDEO);
        assert_eq!(b.len(), FRAME_HEADER_LEN + 1 + nal.len());
        match decode::<AgentMsg>(&b).unwrap() {
            Decoded::Video(h2, key, data) => {
                assert_eq!(h2, h);
                assert!(key);
                assert_eq!(data, nal);
            }
            _ => panic!(),
        }
        let b = encode_video(&h, false, &nal);
        assert!(matches!(decode::<AgentMsg>(&b).unwrap(), Decoded::Video(_, false, _)));
    }

    #[test]
    fn audio_roundtrip() {
        let b = encode_audio(42, &[0xFF, 0xF1, 1, 2]);
        match decode::<AgentMsg>(&b).unwrap() {
            Decoded::Audio(t, d) => {
                assert_eq!(t, 42);
                assert_eq!(d, &[0xFF, 0xF1, 1, 2]);
            }
            _ => panic!(),
        }
        assert!(matches!(decode::<AgentMsg>(&b[..5]), Err(DecodeError::Truncated)));
    }

    #[test]
    fn old_start_stream_defaults_to_jpeg() {
        // 예전 앱은 codec 을 보내지 않는다 → 빈 문자열(= jpeg)
        let m: ClientMsg = serde_json::from_str(r#"{"type":"start_stream","monitor":0,"quality":60,"scale_pct":50,"max_fps":15}"#).unwrap();
        assert!(matches!(m, ClientMsg::StartStream { ref codec, bitrate_kbps: 0, .. } if codec.is_empty()));
    }
}
