//! homepilot-cli.exe — 명령 프롬프트/PowerShell 용 (결과가 화면에 바로 출력되고 끝날 때까지 기다림).
//! 예: homepilot-cli info, homepilot-cli setup-home
fn main() {
    homepilot_agent::run_main();
}
