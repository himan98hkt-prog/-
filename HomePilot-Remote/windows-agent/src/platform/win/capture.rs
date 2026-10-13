use crate::platform::RawFrame;
use anyhow::{anyhow, bail, Result};
use homepilot_protocol::app::MonitorInfo;
use windows::Win32::Foundation::{BOOL, LPARAM, RECT, TRUE};
use windows::Win32::Graphics::Gdi::*;
use windows::Win32::UI::WindowsAndMessaging::{DrawIconEx, GetCursorInfo, GetIconInfo, CURSORINFO, CURSOR_SHOWING, DI_NORMAL, ICONINFO};

const MONITORINFOF_PRIMARY: u32 = 1;

unsafe extern "system" fn enum_proc(hmon: HMONITOR, _: HDC, _: *mut RECT, data: LPARAM) -> BOOL {
    let list = &mut *(data.0 as *mut Vec<MonitorInfo>);
    let mut mi = MONITORINFOEXW::default();
    mi.monitorInfo.cbSize = std::mem::size_of::<MONITORINFOEXW>() as u32;
    if GetMonitorInfoW(hmon, &mut mi as *mut MONITORINFOEXW as *mut MONITORINFO).as_bool() {
        let r = mi.monitorInfo.rcMonitor;
        let len = mi.szDevice.iter().position(|&c| c == 0).unwrap_or(mi.szDevice.len());
        list.push(MonitorInfo {
            index: 0,
            name: String::from_utf16_lossy(&mi.szDevice[..len]).trim_start_matches(r"\\.\").to_string(),
            x: r.left,
            y: r.top,
            width: (r.right - r.left) as u32,
            height: (r.bottom - r.top) as u32,
            primary: mi.monitorInfo.dwFlags & MONITORINFOF_PRIMARY != 0,
        });
    }
    TRUE
}

/// 모니터 목록. 주 모니터가 0번, 나머지는 왼쪽→오른쪽 순서로 번호를 매긴다.
pub fn list_monitors() -> Result<Vec<MonitorInfo>> {
    let mut list: Vec<MonitorInfo> = Vec::new();
    unsafe {
        if !EnumDisplayMonitors(HDC::default(), None, Some(enum_proc), LPARAM(&mut list as *mut _ as isize)).as_bool() {
            bail!("모니터 목록을 가져오지 못했습니다");
        }
    }
    list.sort_by_key(|m| (!m.primary, m.x, m.y));
    for (i, m) in list.iter_mut().enumerate() {
        m.index = i as u32;
    }
    Ok(list)
}

/// GDI 화면 캡처. 같은 스레드에서만 사용한다 (HDC 는 스레드 간 이동 불가).
pub struct Capturer {
    mon: MonitorInfo,
    screen: HDC,
    mem: HDC,
    bmp: HBITMAP,
    old: HGDIOBJ,
}

impl Capturer {
    pub fn new(mon: &MonitorInfo) -> Result<Self> {
        unsafe {
            let screen = GetDC(None);
            if screen.is_invalid() {
                bail!("화면 DC 를 얻지 못했습니다");
            }
            let mem = CreateCompatibleDC(screen);
            let bmp = CreateCompatibleBitmap(screen, mon.width as i32, mon.height as i32);
            if mem.is_invalid() || bmp.is_invalid() {
                ReleaseDC(None, screen);
                bail!("캡처용 비트맵 생성 실패");
            }
            let old = SelectObject(mem, bmp);
            Ok(Self { mon: mon.clone(), screen, mem, bmp, old })
        }
    }

    pub fn capture(&mut self, out: &mut RawFrame) -> Result<()> {
        let (w, h) = (self.mon.width as i32, self.mon.height as i32);
        unsafe {
            BitBlt(self.mem, 0, 0, w, h, self.screen, self.mon.x, self.mon.y, SRCCOPY | CAPTUREBLT)
                .map_err(|e| anyhow!("BitBlt 실패 (잠금 화면/UAC 창일 수 있음): {e}"))?;
            self.draw_cursor();
            let mut bmi = BITMAPINFO::default();
            bmi.bmiHeader.biSize = std::mem::size_of::<BITMAPINFOHEADER>() as u32;
            bmi.bmiHeader.biWidth = w;
            bmi.bmiHeader.biHeight = -h; // 위에서 아래 순서
            bmi.bmiHeader.biPlanes = 1;
            bmi.bmiHeader.biBitCount = 32;
            bmi.bmiHeader.biCompression = BI_RGB.0;
            out.width = w as u32;
            out.height = h as u32;
            out.bgra.resize((w * h * 4) as usize, 0);
            let lines = GetDIBits(self.mem, self.bmp, 0, h as u32, Some(out.bgra.as_mut_ptr().cast()), &mut bmi, DIB_RGB_COLORS);
            if lines != h {
                bail!("GetDIBits 실패 ({lines}/{h})");
            }
        }
        Ok(())
    }

    unsafe fn draw_cursor(&self) {
        let mut ci = CURSORINFO { cbSize: std::mem::size_of::<CURSORINFO>() as u32, ..Default::default() };
        if GetCursorInfo(&mut ci).is_err() || ci.flags.0 & CURSOR_SHOWING.0 == 0 {
            return;
        }
        let mut ii = ICONINFO::default();
        let (hx, hy) = if GetIconInfo(ci.hCursor, &mut ii).is_ok() {
            if !ii.hbmMask.is_invalid() {
                let _ = DeleteObject(ii.hbmMask);
            }
            if !ii.hbmColor.is_invalid() {
                let _ = DeleteObject(ii.hbmColor);
            }
            (ii.xHotspot as i32, ii.yHotspot as i32)
        } else {
            (0, 0)
        };
        let x = ci.ptScreenPos.x - self.mon.x - hx;
        let y = ci.ptScreenPos.y - self.mon.y - hy;
        let _ = DrawIconEx(self.mem, x, y, ci.hCursor, 0, 0, 0, None, DI_NORMAL);
    }
}

impl Drop for Capturer {
    fn drop(&mut self) {
        unsafe {
            SelectObject(self.mem, self.old);
            let _ = DeleteObject(self.bmp);
            let _ = DeleteDC(self.mem);
            ReleaseDC(None, self.screen);
        }
    }
}
