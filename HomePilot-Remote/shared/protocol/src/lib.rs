//! HomePilot Remote 공용 프로토콜.
//!
//! 계층 구조
//! 1. 중계 계층(relay): WebSocket. 텍스트 프레임 = 중계 제어(JSON), 바이너리 프레임 = `[세션ID u32 BE][암호문]`.
//!    중계 서버는 암호문만 전달하며 내용을 볼 수 없다.
//! 2. 보안 계층(secure): Noise XX 핸드셰이크(X25519 / ChaCha20-Poly1305 / BLAKE2s) 후
//!    양방향 키로 메시지 단위 AEAD 암호화. 상대 공개키는 기기 등록(페어링) 시 고정(pin)한다.
//! 3. 응용 계층(app): 첫 바이트가 종류. 0x01 = 제어 JSON, 0x02 = 화면 프레임.

pub mod app;
pub mod relay;
pub mod secure;

/// 프로토콜 버전. 호환되지 않는 변경 시 올린다.
pub const PROTOCOL_VERSION: u32 = 1;
