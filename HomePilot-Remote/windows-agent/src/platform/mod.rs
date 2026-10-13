//! 운영체제별 기능. 실제 제품 대상은 Windows 이며,
//! 그 외 OS 에서는 개발·자동 테스트용 대체 구현(테스트 화면, 입력 기록)이 쓰인다.

use homepilot_protocol::app::MouseButton;

/// 캡처된 화면. BGRA 8비트, 줄 간격 = width * 4.
#[derive(Default)]
pub struct RawFrame {
    pub bgra: Vec<u8>,
    pub width: u32,
    pub height: u32,
}

/// 입력 장치 동작 (테스트에서 검증할 수 있도록 공통 형태로 둔다).
#[derive(Debug, Clone, PartialEq)]
pub enum InputAction {
    MoveAbs { x: i32, y: i32 },
    MoveRel { dx: i32, dy: i32 },
    Button { button: MouseButton, down: bool },
    Wheel { dx: i32, dy: i32 },
    Text(String),
    Key { key: String, down: bool },
}

#[cfg(windows)]
mod win;
#[cfg(windows)]
pub use self::win::*;

#[cfg(not(windows))]
mod fallback;
#[cfg(not(windows))]
pub use self::fallback::*;
