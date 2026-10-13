//! 트레이 아이콘, 긴급 차단 단축키(Ctrl+Alt+F12), 원격 제어 중 표시줄.
//!
//! Win32 메시지 루프는 메인 스레드에서 돈다. 네트워크 쪽은 `Shared::refresh_ui`
//! 로 WM_APP_REFRESH 를 보내 화면 갱신을 요청한다.

use super::sys::{autostart_get, autostart_set, confirm, open_folder, show_message};
use super::wide;
use crate::app::{Shared, MENU_PAIRING};
use anyhow::{Context, Result};
use std::sync::atomic::{AtomicIsize, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use windows::core::{w, PCWSTR};
use windows::Win32::Foundation::*;
use windows::Win32::Graphics::Gdi::*;
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::HiDpi::GetDpiForSystem;
use windows::Win32::UI::Input::KeyboardAndMouse::{RegisterHotKey, UnregisterHotKey, MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, VK_F12};
use windows::Win32::UI::Shell::*;
use windows::Win32::UI::WindowsAndMessaging::*;

const WM_APP_TRAY: u32 = WM_APP + 1;
const WM_APP_REFRESH: u32 = WM_APP + 2;
const HOTKEY_ID: i32 = 1;
const TIMER_ID: usize = 1;

const ID_PAIR: usize = 10;
const ID_BLOCK: usize = 11;
const ID_UNBLOCK: usize = 12;
const ID_AUTOSTART: usize = 13;
const ID_INFO: usize = 14;
const ID_LOGS: usize = 15;
const ID_REVOKE_ALL: usize = 16;
const ID_END_SESSIONS: usize = 17;
const ID_QUIT: usize = 19;

struct Globals {
    shared: Arc<Shared>,
    overlay_text: Mutex<String>,
}

static G: OnceLock<Globals> = OnceLock::new();
static MAIN_HWND: AtomicIsize = AtomicIsize::new(0);
static OVERLAY_HWND: AtomicIsize = AtomicIsize::new(0);
static TASKBAR_CREATED: AtomicUsize = AtomicUsize::new(0);
static LAST_SESSION_COUNT: AtomicUsize = AtomicUsize::new(0);
static HOTKEY_OK: AtomicUsize = AtomicUsize::new(0);
static LAST_PUBLIC_URL: Mutex<Option<String>> = Mutex::new(None);

fn hwnd_from(v: isize) -> HWND {
    HWND(v as *mut core::ffi::c_void)
}

fn g() -> &'static Globals {
    G.get().expect("UI 초기화 전")
}

pub fn run_ui(shared: Arc<Shared>, _rt: &tokio::runtime::Runtime) -> Result<()> {
    let _ = G.set(Globals { shared: shared.clone(), overlay_text: Mutex::new(String::new()) });
    unsafe {
        let hinst: HINSTANCE = GetModuleHandleW(None).context("GetModuleHandle 실패")?.into();
        let wc =
            WNDCLASSW { lpfnWndProc: Some(main_proc), hInstance: hinst, lpszClassName: w!("HomePilotAgentMain"), ..Default::default() };
        RegisterClassW(&wc);
        let oc = WNDCLASSW {
            lpfnWndProc: Some(overlay_proc),
            hInstance: hinst,
            lpszClassName: w!("HomePilotAgentOverlay"),
            hCursor: LoadCursorW(None, IDC_ARROW).unwrap_or_default(),
            ..Default::default()
        };
        RegisterClassW(&oc);

        let hwnd = CreateWindowExW(
            WINDOW_EX_STYLE(0),
            w!("HomePilotAgentMain"),
            w!("HomePilot Remote Agent"),
            WS_OVERLAPPED,
            0,
            0,
            0,
            0,
            None,
            None,
            hinst,
            None,
        )
        .context("창 생성 실패")?;
        MAIN_HWND.store(hwnd.0 as isize, Ordering::SeqCst);
        TASKBAR_CREATED.store(RegisterWindowMessageW(w!("TaskbarCreated")) as usize, Ordering::SeqCst);

        // 표시줄: 클릭이 통과되는 반투명 최상위 창
        let dpi = GetDpiForSystem().max(96) as i32;
        let (bw, bh) = (560 * dpi / 96, 34 * dpi / 96);
        let sw = GetSystemMetrics(SM_CXSCREEN);
        let ov = CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_LAYERED | WS_EX_TRANSPARENT,
            w!("HomePilotAgentOverlay"),
            w!("HomePilot 원격 제어 중"),
            WS_POPUP,
            (sw - bw) / 2,
            0,
            bw,
            bh,
            None,
            None,
            hinst,
            None,
        )
        .context("표시줄 생성 실패")?;
        let _ = SetLayeredWindowAttributes(ov, COLORREF(0), 225, LWA_ALPHA);
        OVERLAY_HWND.store(ov.0 as isize, Ordering::SeqCst);

        if RegisterHotKey(hwnd, HOTKEY_ID, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_F12.0 as u32).is_ok() {
            HOTKEY_OK.store(1, Ordering::SeqCst);
        } else {
            tracing::warn!("Ctrl+Alt+F12 단축키 등록 실패 (다른 프로그램이 사용 중). 트레이 메뉴로 차단하세요.");
        }
        add_tray(hwnd, NIM_ADD);
        SetTimer(hwnd, TIMER_ID, 5_000, None);

        let main_raw = hwnd.0 as isize;
        *shared.ui_refresh.lock().unwrap() = Some(Box::new(move || {
            let _ = PostMessageW(hwnd_from(main_raw), WM_APP_REFRESH, WPARAM(0), LPARAM(0));
        }));
        refresh(hwnd);
        if shared.pairing_remaining().is_some() && shared.trust.lock().unwrap().clients.is_empty() {
            balloon(
                hwnd,
                "HomePilot 설치 완료",
                "잠시 후 '휴대폰 연결 주소' 알림이 뜹니다. 트레이 아이콘 우클릭 → '휴대폰 연결 정보' 에서 주소·장치 ID 를 확인해 앱에 입력하세요. (10분간 등록 허용)",
            );
        }

        let mut msg = MSG::default();
        while GetMessageW(&mut msg, None, 0, 0).0 > 0 {
            let _ = TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
        *shared.ui_refresh.lock().unwrap() = None;
    }
    Ok(())
}

fn fill_wide<const N: usize>(dst: &mut [u16; N], s: &str) {
    let v: Vec<u16> = s.encode_utf16().take(N - 1).collect();
    dst[..v.len()].copy_from_slice(&v);
    dst[v.len()] = 0;
}

unsafe fn tray_icon() -> HICON {
    let s = &g().shared;
    let id = if s.is_blocked() {
        IDI_ERROR
    } else if !s.active_sessions().is_empty() {
        IDI_WARNING
    } else if s.relay_online.load(Ordering::Relaxed) {
        IDI_SHIELD
    } else {
        IDI_APPLICATION
    };
    LoadIconW(None, id).unwrap_or_default()
}

fn tooltip() -> String {
    let s = &g().shared;
    let sessions = s.active_sessions();
    let state = if s.is_blocked() {
        "원격 제어 차단됨".to_string()
    } else if !sessions.is_empty() {
        format!("원격 접속 중: {}", sessions.iter().map(|v| v.client_name.as_str()).collect::<Vec<_>>().join(", "))
    } else if s.relay_online.load(Ordering::Relaxed) {
        "대기 중 (온라인)".to_string()
    } else {
        "서버 연결 중… (오프라인)".to_string()
    };
    let pairing = s.pairing_remaining().map(|d| format!("\n새 기기 등록 대기 {}분", d.as_secs() / 60 + 1)).unwrap_or_default();
    format!("HomePilot - {state}{pairing}")
}

unsafe fn add_tray(hwnd: HWND, op: NOTIFY_ICON_MESSAGE) {
    let mut nid = NOTIFYICONDATAW {
        cbSize: std::mem::size_of::<NOTIFYICONDATAW>() as u32,
        hWnd: hwnd,
        uID: 1,
        uFlags: NIF_ICON | NIF_MESSAGE | NIF_TIP,
        uCallbackMessage: WM_APP_TRAY,
        hIcon: tray_icon(),
        ..Default::default()
    };
    fill_wide(&mut nid.szTip, &tooltip());
    let _ = Shell_NotifyIconW(op, &nid);
}

unsafe fn balloon(hwnd: HWND, title: &str, text: &str) {
    let mut nid = NOTIFYICONDATAW {
        cbSize: std::mem::size_of::<NOTIFYICONDATAW>() as u32,
        hWnd: hwnd,
        uID: 1,
        uFlags: NIF_INFO,
        dwInfoFlags: NIIF_WARNING,
        ..Default::default()
    };
    fill_wide(&mut nid.szInfoTitle, title);
    fill_wide(&mut nid.szInfo, text);
    let _ = Shell_NotifyIconW(NIM_MODIFY, &nid);
}

/// 트레이·표시줄 상태를 현재 상태에 맞춘다.
unsafe fn refresh(hwnd: HWND) {
    add_tray(hwnd, NIM_MODIFY);
    let s = &g().shared;
    let sessions = s.active_sessions();
    let prev = LAST_SESSION_COUNT.swap(sessions.len(), Ordering::SeqCst);
    if sessions.len() > prev {
        let names = sessions.iter().map(|v| v.client_name.as_str()).collect::<Vec<_>>().join(", ");
        balloon(hwnd, "원격 접속 시작", &format!("{names} 이(가) 이 PC 에 접속했습니다.\n즉시 차단: Ctrl+Alt+F12"));
    } else if sessions.len() < prev && sessions.is_empty() {
        balloon(hwnd, "원격 접속 종료", "모든 원격 연결이 끝났습니다.");
    }
    // 터널 주소가 새로 생기거나 바뀌면 알려 준다 (빠른 터널은 재시작마다 주소가 바뀜)
    let url = s.public_url.lock().unwrap().0.clone();
    {
        let mut last = LAST_PUBLIC_URL.lock().unwrap();
        if url.is_some() && *last != url {
            balloon(
                hwnd,
                "휴대폰 연결 주소",
                &format!("{}\n휴대폰 앱의 PC 주소가 다르면 이 주소로 수정하세요. (트레이 → PC 정보)", url.as_deref().unwrap_or("")),
            );
        }
        *last = url;
    }
    let ov = hwnd_from(OVERLAY_HWND.load(Ordering::SeqCst));
    let show = !sessions.is_empty() && s.config.lock().unwrap().show_overlay;
    if show {
        let names = sessions
            .iter()
            .map(|v| if v.controlling { v.client_name.clone() } else { format!("{} (보기만)", v.client_name) })
            .collect::<Vec<_>>()
            .join(", ");
        let hk = if HOTKEY_OK.load(Ordering::SeqCst) == 1 { "  ·  차단: Ctrl+Alt+F12" } else { "  ·  차단: 트레이 메뉴" };
        *g().overlay_text.lock().unwrap() = format!("● 원격 제어 중 — {names}{hk}");
        let _ = InvalidateRect(ov, None, TRUE);
        let _ = SetWindowPos(ov, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW);
    } else {
        let _ = ShowWindow(ov, SW_HIDE);
    }
}

unsafe fn show_menu(hwnd: HWND) {
    let s = &g().shared;
    let Ok(menu) = CreatePopupMenu() else { return };
    let add = |flags: MENU_ITEM_FLAGS, id: usize, text: &str| {
        let t = wide(text);
        let _ = AppendMenuW(menu, flags, id, PCWSTR(t.as_ptr()));
    };
    add(MF_STRING | MF_GRAYED, 0, &tooltip().replace('\n', " · "));
    add(MF_STRING | MF_DEFAULT, ID_INFO, "휴대폰 연결 정보 (주소·장치 ID) 보기");
    add(MF_SEPARATOR, 0, "");
    let sessions = s.active_sessions();
    if !sessions.is_empty() {
        add(MF_STRING, ID_END_SESSIONS, "현재 원격 연결 끊기");
    }
    if s.is_blocked() {
        add(MF_STRING, ID_UNBLOCK, "원격 제어 다시 허용");
    } else {
        add(MF_STRING, ID_BLOCK, "원격 제어 즉시 차단 (Ctrl+Alt+F12)");
        add(MF_STRING, ID_PAIR, "새 휴대폰 등록 (5분간 허용)");
    }
    add(MF_SEPARATOR, 0, "");
    let auto = autostart_get().unwrap_or(false);
    add(MF_STRING | if auto { MF_CHECKED } else { MF_UNCHECKED }, ID_AUTOSTART, "Windows 시작 시 자동 실행");
    add(MF_STRING, ID_LOGS, "로그·접속 기록 폴더 열기");
    add(MF_STRING, ID_REVOKE_ALL, "모든 휴대폰 등록 해제…");
    add(MF_SEPARATOR, 0, "");
    add(MF_STRING, ID_QUIT, "HomePilot 종료");

    let mut pt = POINT::default();
    let _ = GetCursorPos(&mut pt);
    let _ = SetForegroundWindow(hwnd);
    let cmd = TrackPopupMenu(menu, TPM_RETURNCMD | TPM_RIGHTBUTTON | TPM_NONOTIFY, pt.x, pt.y, 0, hwnd, None).0 as usize;
    let _ = PostMessageW(hwnd, WM_NULL, WPARAM(0), LPARAM(0));
    let _ = DestroyMenu(menu);
    handle_command(hwnd, cmd);
}

unsafe fn handle_command(hwnd: HWND, cmd: usize) {
    let s = g().shared.clone();
    match cmd {
        ID_PAIR => {
            s.open_pairing(MENU_PAIRING);
            balloon(hwnd, "새 휴대폰 등록", "5분 동안 등록 요청을 받습니다. 휴대폰 앱에서 이 PC 를 추가하세요.");
        }
        ID_BLOCK => {
            s.emergency_block();
            balloon(hwnd, "원격 제어 차단", "모든 원격 연결을 끊고 새 접속을 거부합니다.");
        }
        ID_UNBLOCK => s.unblock(),
        ID_END_SESSIONS => s.end_all_sessions("PC 사용자가 연결을 끊었습니다"),
        ID_AUTOSTART => {
            let on = !autostart_get().unwrap_or(false);
            if let Err(e) = autostart_set(on) {
                show_message("HomePilot", &format!("자동 실행 설정 실패: {e:#}"));
            }
        }
        ID_INFO => {
            let clients = s.trust.lock().unwrap().clients.clone();
            let list = if clients.is_empty() {
                "  (없음)".to_string()
            } else {
                clients
                    .iter()
                    .map(|c| {
                        format!(
                            "  • {} [{}]  조작:{} 파일:{}",
                            c.name,
                            c.fingerprint,
                            if c.permissions.control { "O" } else { "X" },
                            if c.permissions.files { "O" } else { "X" }
                        )
                    })
                    .collect::<Vec<_>>()
                    .join("\n")
            };
            show_message(
                "HomePilot - PC 정보",
                &format!(
                    "【휴대폰 앱에 입력할 정보】\n중계 서버 주소: {}\n장치 ID: {}\n\nPC 이름: {}\nPC 지문: {}\n\n등록된 휴대폰:\n{}\n\n이 창에서 Ctrl+C 를 누르면 내용이 복사됩니다.",
                    s.phone_relay_text(),
                    s.device_id,
                    s.display_name(),
                    s.fingerprint(),
                    list
                ),
            );
        }
        ID_LOGS => open_folder(&s.paths.log_dir),
        ID_REVOKE_ALL
            if confirm("HomePilot", "등록된 모든 휴대폰의 접근 권한을 삭제할까요?\n다시 쓰려면 휴대폰을 새로 등록해야 합니다.") =>
        {
            s.revoke_all()
        }
        ID_QUIT if s.active_sessions().is_empty() || confirm("HomePilot", "원격 연결 중입니다. 연결을 끊고 종료할까요?") =>
        {
            let _ = DestroyWindow(hwnd);
            return; // 창이 사라졌으므로 갱신하지 않는다
        }
        _ => {}
    }
    refresh(hwnd);
}

unsafe extern "system" fn main_proc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    match msg {
        WM_APP_TRAY => {
            let ev = (lp.0 & 0xFFFF) as u32;
            if ev == WM_RBUTTONUP || ev == WM_LBUTTONUP || ev == WM_CONTEXTMENU {
                show_menu(hwnd);
            }
            LRESULT(0)
        }
        WM_APP_REFRESH => {
            refresh(hwnd);
            LRESULT(0)
        }
        WM_HOTKEY if wp.0 as i32 == HOTKEY_ID => {
            g().shared.emergency_block();
            balloon(hwnd, "원격 제어 차단", "Ctrl+Alt+F12: 모든 원격 연결을 끊었습니다. 트레이 메뉴에서 다시 허용할 수 있습니다.");
            refresh(hwnd);
            LRESULT(0)
        }
        WM_TIMER => {
            // 등록 대기 남은 시간 갱신 + 표시줄을 계속 맨 위로
            refresh(hwnd);
            LRESULT(0)
        }
        WM_DESTROY => {
            let _ = KillTimer(hwnd, TIMER_ID);
            let _ = UnregisterHotKey(hwnd, HOTKEY_ID);
            let nid = NOTIFYICONDATAW { cbSize: std::mem::size_of::<NOTIFYICONDATAW>() as u32, hWnd: hwnd, uID: 1, ..Default::default() };
            let _ = Shell_NotifyIconW(NIM_DELETE, &nid);
            let _ = DestroyWindow(hwnd_from(OVERLAY_HWND.load(Ordering::SeqCst)));
            PostQuitMessage(0);
            LRESULT(0)
        }
        _ if msg != 0 && msg as usize == TASKBAR_CREATED.load(Ordering::SeqCst) => {
            // 탐색기가 다시 시작되면 트레이 아이콘을 다시 등록
            add_tray(hwnd, NIM_ADD);
            LRESULT(0)
        }
        _ => DefWindowProcW(hwnd, msg, wp, lp),
    }
}

unsafe extern "system" fn overlay_proc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    match msg {
        WM_PAINT => {
            let mut ps = PAINTSTRUCT::default();
            let hdc = BeginPaint(hwnd, &mut ps);
            let mut rc = RECT::default();
            let _ = GetClientRect(hwnd, &mut rc);
            let brush = CreateSolidBrush(COLORREF(0x001E1EC8)); // 빨강 (BGR)
            FillRect(hdc, &rc, brush);
            let _ = DeleteObject(brush);
            let dpi = GetDpiForSystem().max(96) as i32;
            let font = CreateFontW(
                -15 * dpi / 96,
                0,
                0,
                0,
                FW_BOLD.0 as i32,
                0,
                0,
                0,
                DEFAULT_CHARSET.0 as u32,
                0,
                0,
                CLEARTYPE_QUALITY.0 as u32,
                0,
                w!("Malgun Gothic"),
            );
            let old = SelectObject(hdc, font);
            SetBkMode(hdc, TRANSPARENT);
            SetTextColor(hdc, COLORREF(0x00FFFFFF));
            let mut text: Vec<u16> = g().overlay_text.lock().unwrap().encode_utf16().collect();
            // 빈 Vec 의 포인터는 가짜 주소(0x2)라 DrawTextW 가 USER32 안에서 접근 위반으로 죽는다.
            // (창이 숨겨져 있어도 생성 직후 WM_PAINT 가 온다 — 사용자 PC 에서 실제 발생)
            if !text.is_empty() {
                DrawTextW(hdc, &mut text, &mut rc, DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_END_ELLIPSIS);
            }
            SelectObject(hdc, old);
            let _ = DeleteObject(font);
            let _ = EndPaint(hwnd, &ps);
            LRESULT(0)
        }
        WM_NCHITTEST => LRESULT(-1), // HTTRANSPARENT: 클릭 통과
        _ => DefWindowProcW(hwnd, msg, wp, lp),
    }
}
