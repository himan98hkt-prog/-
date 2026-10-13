use super::wide;
use crate::input::{is_extended_vk, key_name_to_vk};
use crate::platform::InputAction;
use anyhow::{bail, Context, Result};
use homepilot_protocol::app::MouseButton;
use windows::core::PCWSTR;
use windows::Win32::Foundation::{LocalFree, HLOCAL, HWND};
use windows::Win32::Security::Cryptography::{CryptProtectData, CryptUnprotectData, CRYPTPROTECT_UI_FORBIDDEN, CRYPT_INTEGER_BLOB};
use windows::Win32::System::Console::{AttachConsole, ATTACH_PARENT_PROCESS};
use windows::Win32::System::Performance::*;
use windows::Win32::UI::HiDpi::{SetProcessDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2};
use windows::Win32::UI::Input::KeyboardAndMouse::*;
use windows::Win32::UI::Shell::ShellExecuteW;
use windows::Win32::UI::WindowsAndMessaging::*;

/// 화면 좌표를 실제 픽셀로 다루기 위해 모니터별 DPI 인식을 켠다.
pub fn init_process() {
    unsafe {
        let _ = SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    }
}

pub fn attach_parent_console() {
    unsafe {
        let _ = AttachConsole(ATTACH_PARENT_PROCESS);
    }
}

// ---------- 중복 실행 방지 ----------

/// 이 사용자 세션에서 처음 실행된 경우에만 Some. 반환값을 들고 있는 동안 잠금 유지.
pub struct InstanceGuard(windows::Win32::Foundation::HANDLE);

impl Drop for InstanceGuard {
    fn drop(&mut self) {
        unsafe {
            let _ = windows::Win32::Foundation::CloseHandle(self.0);
        }
    }
}

pub fn single_instance() -> Option<InstanceGuard> {
    use windows::Win32::Foundation::{GetLastError, ERROR_ALREADY_EXISTS};
    use windows::Win32::System::Threading::CreateMutexW;
    unsafe {
        let h = CreateMutexW(None, true, windows::core::w!("Local\\HomePilotRemoteAgent")).ok()?;
        if GetLastError() == ERROR_ALREADY_EXISTS {
            let _ = windows::Win32::Foundation::CloseHandle(h);
            return None;
        }
        Some(InstanceGuard(h))
    }
}

// ---------- 하위 프로세스 수명 ----------

/// cloudflared 같은 하위 프로세스를 에이전트와 같은 작업 개체에 넣는다.
/// kill_on_drop 은 정상 종료 때만 동작하므로, 에이전트가 비정상 종료·taskkill 로 꺼지면
/// cloudflared 가 혼자 남아 있었다 (사용자 PC 에서 실제 발생). 작업 개체 핸들은 프로세스가
/// 끝날 때 운영체제가 닫고, KILL_ON_JOB_CLOSE 로 묶인 프로세스도 함께 끝난다.
pub fn bind_child_to_agent(child: &tokio::process::Child) {
    use std::sync::OnceLock;
    use windows::Win32::Foundation::HANDLE;
    use windows::Win32::System::JobObjects::*;
    static JOB: OnceLock<Option<isize>> = OnceLock::new();
    let job = JOB.get_or_init(|| unsafe {
        let job = CreateJobObjectW(None, None).ok()?;
        let mut info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            &info as *const _ as *const core::ffi::c_void,
            std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
        )
        .ok()?;
        Some(job.0 as isize)
    });
    let (Some(job), Some(h)) = (job, child.raw_handle()) else {
        tracing::warn!("하위 프로세스를 작업 개체에 넣지 못했습니다 (에이전트 비정상 종료 시 남을 수 있음)");
        return;
    };
    unsafe {
        if let Err(e) = AssignProcessToJobObject(HANDLE(*job as *mut core::ffi::c_void), HANDLE(h)) {
            tracing::warn!("작업 개체 등록 실패: {e}");
        }
    }
}

// ---------- DPAPI ----------

fn blob(data: &[u8]) -> CRYPT_INTEGER_BLOB {
    CRYPT_INTEGER_BLOB { cbData: data.len() as u32, pbData: data.as_ptr() as *mut u8 }
}

unsafe fn take_blob(b: CRYPT_INTEGER_BLOB) -> Vec<u8> {
    let v = std::slice::from_raw_parts(b.pbData, b.cbData as usize).to_vec();
    let _ = LocalFree(HLOCAL(b.pbData.cast()));
    v
}

pub fn protect(data: &[u8]) -> Result<Vec<u8>> {
    let input = blob(data);
    let mut out = CRYPT_INTEGER_BLOB::default();
    unsafe {
        CryptProtectData(&input, PCWSTR::null(), None, None, None, CRYPTPROTECT_UI_FORBIDDEN, &mut out).context("DPAPI 암호화 실패")?;
        Ok(take_blob(out))
    }
}

pub fn unprotect(data: &[u8]) -> Result<Vec<u8>> {
    let input = blob(data);
    let mut out = CRYPT_INTEGER_BLOB::default();
    unsafe {
        CryptUnprotectData(&input, None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, &mut out).context("DPAPI 복호화 실패")?;
        Ok(take_blob(out))
    }
}

// ---------- 입력 ----------

pub struct Input {
    /// 진단·자동 테스트용: 입력을 실제로 보내지 않고 기록만 한다 (HOMEPILOT_INPUT_DRY_RUN=1).
    /// 사람이 없는 CI 서버에서 Ctrl+C 등을 실제로 보내면 서버 프로그램 자체가 멈출 수 있다.
    dry_run: bool,
}

impl Input {
    pub fn new() -> Self {
        Input { dry_run: std::env::var_os("HOMEPILOT_INPUT_DRY_RUN").is_some_and(|v| v == "1") }
    }

    pub fn apply(&mut self, a: InputAction) -> Result<()> {
        if self.dry_run {
            if let InputAction::Key { key, .. } = &a {
                if key_name_to_vk(key).is_none() {
                    bail!("알 수 없는 키: {key}");
                }
            }
            tracing::debug!(?a, "입력(기록만)");
            return Ok(());
        }
        let inputs: Vec<INPUT> = match a {
            InputAction::MoveAbs { x, y } => {
                let (vx, vy, vw, vh) = unsafe {
                    (
                        GetSystemMetrics(SM_XVIRTUALSCREEN),
                        GetSystemMetrics(SM_YVIRTUALSCREEN),
                        GetSystemMetrics(SM_CXVIRTUALSCREEN).max(2),
                        GetSystemMetrics(SM_CYVIRTUALSCREEN).max(2),
                    )
                };
                let nx = (((x - vx) as i64 * 65535) / (vw as i64 - 1)) as i32;
                let ny = (((y - vy) as i64 * 65535) / (vh as i64 - 1)) as i32;
                vec![mouse(nx, ny, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK)]
            }
            InputAction::Button { button, down } => {
                let f = match (button, down) {
                    (MouseButton::Left, true) => MOUSEEVENTF_LEFTDOWN,
                    (MouseButton::Left, false) => MOUSEEVENTF_LEFTUP,
                    (MouseButton::Right, true) => MOUSEEVENTF_RIGHTDOWN,
                    (MouseButton::Right, false) => MOUSEEVENTF_RIGHTUP,
                    (MouseButton::Middle, true) => MOUSEEVENTF_MIDDLEDOWN,
                    (MouseButton::Middle, false) => MOUSEEVENTF_MIDDLEUP,
                };
                vec![mouse(0, 0, 0, f)]
            }
            InputAction::Wheel { dx, dy } => {
                let mut v = Vec::new();
                if dy != 0 {
                    v.push(mouse(0, 0, dy, MOUSEEVENTF_WHEEL));
                }
                if dx != 0 {
                    v.push(mouse(0, 0, dx, MOUSEEVENTF_HWHEEL));
                }
                v
            }
            InputAction::Text(t) => {
                let mut v = Vec::new();
                for ch in t.chars() {
                    if ch == '\n' {
                        v.push(key(VK_RETURN.0, false));
                        v.push(key(VK_RETURN.0, true));
                        continue;
                    }
                    let mut buf = [0u16; 2];
                    for unit in ch.encode_utf16(&mut buf).iter() {
                        v.push(unicode(*unit, false));
                        v.push(unicode(*unit, true));
                    }
                }
                v
            }
            InputAction::Key { key: name, down } => {
                let Some(vk) = key_name_to_vk(&name) else { bail!("알 수 없는 키: {name}") };
                vec![key(vk, !down)]
            }
        };
        if inputs.is_empty() {
            return Ok(());
        }
        let sent = unsafe { SendInput(&inputs, std::mem::size_of::<INPUT>() as i32) };
        if sent as usize != inputs.len() {
            bail!("입력이 차단되었습니다 (관리자 권한 창이나 잠금 화면에는 입력할 수 없습니다)");
        }
        Ok(())
    }
}

fn mouse(dx: i32, dy: i32, data: i32, flags: MOUSE_EVENT_FLAGS) -> INPUT {
    INPUT {
        r#type: INPUT_MOUSE,
        Anonymous: INPUT_0 { mi: MOUSEINPUT { dx, dy, mouseData: data as u32, dwFlags: flags, time: 0, dwExtraInfo: 0 } },
    }
}

fn key(vk: u16, up: bool) -> INPUT {
    let scan = unsafe { MapVirtualKeyW(vk as u32, MAPVK_VK_TO_VSC) } as u16;
    let mut flags = KEYBD_EVENT_FLAGS(0);
    if up {
        flags |= KEYEVENTF_KEYUP;
    }
    if is_extended_vk(vk) {
        flags |= KEYEVENTF_EXTENDEDKEY;
    }
    INPUT {
        r#type: INPUT_KEYBOARD,
        Anonymous: INPUT_0 { ki: KEYBDINPUT { wVk: VIRTUAL_KEY(vk), wScan: scan, dwFlags: flags, time: 0, dwExtraInfo: 0 } },
    }
}

fn unicode(unit: u16, up: bool) -> INPUT {
    let mut flags = KEYEVENTF_UNICODE;
    if up {
        flags |= KEYEVENTF_KEYUP;
    }
    INPUT {
        r#type: INPUT_KEYBOARD,
        Anonymous: INPUT_0 { ki: KEYBDINPUT { wVk: VIRTUAL_KEY(0), wScan: unit, dwFlags: flags, time: 0, dwExtraInfo: 0 } },
    }
}

// ---------- GPU ----------

/// 성능 카운터로 3D 엔진 사용률을 합산한다. 드라이버/OS 가 카운터를 제공하지 않으면 None.
pub struct GpuSampler {
    query: isize,
    counter: isize,
    ok: bool,
}

impl GpuSampler {
    pub fn new() -> Self {
        let mut s = GpuSampler { query: 0, counter: 0, ok: false };
        unsafe {
            if PdhOpenQueryW(PCWSTR::null(), 0, &mut s.query) != 0 {
                return s;
            }
            let path = wide(r"\GPU Engine(*engtype_3D)\Utilization Percentage");
            if PdhAddEnglishCounterW(s.query, PCWSTR(path.as_ptr()), 0, &mut s.counter) != 0 {
                return s;
            }
            PdhCollectQueryData(s.query);
            s.ok = true;
        }
        s
    }

    pub fn sample(&mut self) -> Option<f32> {
        if !self.ok {
            return None;
        }
        unsafe {
            if PdhCollectQueryData(self.query) != 0 {
                return None;
            }
            let mut size = 0u32;
            let mut count = 0u32;
            let _ = PdhGetFormattedCounterArrayW(self.counter, PDH_FMT_DOUBLE, &mut size, &mut count, None);
            if size == 0 {
                return Some(0.0); // GPU 를 쓰는 프로세스가 없음
            }
            let n = (size as usize).div_ceil(std::mem::size_of::<PDH_FMT_COUNTERVALUE_ITEM_W>());
            let mut buf: Vec<PDH_FMT_COUNTERVALUE_ITEM_W> = vec![std::mem::zeroed(); n];
            if PdhGetFormattedCounterArrayW(self.counter, PDH_FMT_DOUBLE, &mut size, &mut count, Some(buf.as_mut_ptr())) != 0 {
                return None;
            }
            let total: f64 =
                buf[..count as usize].iter().filter(|i| i.FmtValue.CStatus == 0).map(|i| i.FmtValue.Anonymous.doubleValue).sum();
            Some(total.clamp(0.0, 100.0) as f32)
        }
    }
}

impl Drop for GpuSampler {
    fn drop(&mut self) {
        if self.query != 0 {
            unsafe {
                PdhCloseQuery(self.query);
            }
        }
    }
}

// ---------- 자동 실행 ----------

const RUN_KEY: &str = r"Software\Microsoft\Windows\CurrentVersion\Run";
const RUN_VALUE: &str = "HomePilotRemoteAgent";

pub fn autostart_get() -> Result<bool> {
    let hkcu = winreg::RegKey::predef(winreg::enums::HKEY_CURRENT_USER);
    let Ok(k) = hkcu.open_subkey(RUN_KEY) else { return Ok(false) };
    Ok(k.get_value::<String, _>(RUN_VALUE).is_ok())
}

/// 현재 사용자 로그인 시 자동 실행. 반드시 사용자가 직접 켠 경우에만 호출한다.
pub fn autostart_set(on: bool) -> Result<()> {
    let hkcu = winreg::RegKey::predef(winreg::enums::HKEY_CURRENT_USER);
    let (k, _) = hkcu.create_subkey(RUN_KEY).context("레지스트리 열기 실패")?;
    if on {
        let exe = std::env::current_exe()?;
        k.set_value(RUN_VALUE, &format!("\"{}\"", exe.display())).context("자동 실행 등록 실패")?;
    } else {
        match k.delete_value(RUN_VALUE) {
            Ok(()) => {}
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(e).context("자동 실행 해제 실패"),
        }
    }
    Ok(())
}

// ---------- 대화상자 ----------

pub fn open_folder(path: &std::path::Path) {
    let p = wide(&path.display().to_string());
    unsafe {
        ShellExecuteW(HWND::default(), windows::core::w!("open"), PCWSTR(p.as_ptr()), PCWSTR::null(), PCWSTR::null(), SW_SHOWNORMAL);
    }
}

pub fn show_message(title: &str, text: &str) {
    let (t, x) = (wide(title), wide(text));
    unsafe {
        MessageBoxW(HWND::default(), PCWSTR(x.as_ptr()), PCWSTR(t.as_ptr()), MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    }
}

pub fn confirm(title: &str, text: &str) -> bool {
    let (t, x) = (wide(title), wide(text));
    unsafe {
        MessageBoxW(
            HWND::default(),
            PCWSTR(x.as_ptr()),
            PCWSTR(t.as_ptr()),
            MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2 | MB_TOPMOST | MB_SETFOREGROUND,
        ) == IDYES
    }
}

/// 새 휴대폰 등록 승인 창. 기본 버튼은 "아니요" — 실수로 Enter 를 눌러도 승인되지 않는다.
pub fn ask_pairing_approval(client_name: &str, fingerprint: &str, sas: &str) -> bool {
    let text = format!(
        "휴대폰 \"{client_name}\" 이(가) 이 PC 의 원격 제어 등록을 요청합니다.\n\n\
         확인 코드:  {sas}\n기기 지문:  {fingerprint}\n\n\
         휴대폰 화면의 확인 코드가 위 숫자와 정확히 같고,\n본인이 직접 요청한 경우에만 [예] 를 누르세요.\n\n\
         모르는 요청이면 [아니요] 를 누르세요."
    );
    let (t, x) = (wide("HomePilot - 새 기기 등록 요청"), wide(&text));
    unsafe {
        MessageBoxW(
            HWND::default(),
            PCWSTR(x.as_ptr()),
            PCWSTR(t.as_ptr()),
            MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2 | MB_TOPMOST | MB_SETFOREGROUND | MB_SYSTEMMODAL,
        ) == IDYES
    }
}
