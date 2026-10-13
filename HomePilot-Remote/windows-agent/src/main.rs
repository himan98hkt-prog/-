//! homepilot-agent.exe — 트레이 프로그램. 릴리스 빌드는 콘솔 창 없이 실행된다.
#![cfg_attr(all(windows, not(debug_assertions)), windows_subsystem = "windows")]

fn main() {
    homepilot_agent::run_main();
}
