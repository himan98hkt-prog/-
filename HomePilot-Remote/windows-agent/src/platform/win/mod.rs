//! Windows 구현.
//!
//! - 화면 캡처: GDI BitBlt (모든 Windows 10/11 에서 동작, 커서 포함)
//! - 입력: SendInput (유니코드 입력으로 한글 직접 전달)
//! - 키 보호: DPAPI (현재 사용자 계정 범위)
//! - GPU 사용률: 성능 카운터(PDH) "GPU Engine"
//! - 자동 실행: HKCU\...\Run (관리자 권한 불필요, 사용자 동의 시에만)
//!
//! 운영체제 보안 정책을 우회하지 않는다:
//! UAC 확인창·잠금 화면(보안 데스크톱)은 캡처/입력되지 않으며,
//! 관리자 권한으로 실행된 창에는 일반 권한 에이전트가 입력할 수 없다(UIPI).

mod capture;
mod sys;
mod ui;

pub use capture::{list_monitors, Capturer};
pub use sys::*;
pub use ui::run_ui;

pub(crate) fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}
