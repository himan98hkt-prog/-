//! DXGI Desktop Duplication 화면 캡처 (GPU, 60fps 가능).
//!
//! - GDI BitBlt 보다 훨씬 빠르고(1080p 몇 ms), 화면이 바뀌었을 때만 새 이미지를 준다.
//! - 커서는 화면 이미지에 들어 있지 않으므로 직접 그린다 (흰 화살표 + 검은 테두리).
//! - 잠금 화면·UAC·전체 화면 전환 시 ACCESS_LOST → 다시 만든다. 실패하면 호출 쪽이 GDI 로 대체.

use crate::platform::RawFrame;
use anyhow::{bail, Context, Result};
use homepilot_protocol::app::MonitorInfo;
use windows::core::Interface;
use windows::Win32::Foundation::HMODULE;
use windows::Win32::Graphics::Direct3D::D3D_DRIVER_TYPE_UNKNOWN;
use windows::Win32::Graphics::Direct3D11::*;
use windows::Win32::Graphics::Dxgi::Common::*;
use windows::Win32::Graphics::Dxgi::*;
use windows::Win32::UI::WindowsAndMessaging::{GetCursorInfo, CURSORINFO, CURSOR_SHOWING};

pub struct DxgiCapturer {
    mon: MonitorInfo,
    _device: ID3D11Device,
    ctx: ID3D11DeviceContext,
    dup: IDXGIOutputDuplication,
    staging: ID3D11Texture2D,
    width: u32,
    height: u32,
    /// 마지막 화면 (변화가 없을 때 다시 쓴다)
    last: Vec<u8>,
    has_frame: bool,
}

unsafe impl Send for DxgiCapturer {}

impl DxgiCapturer {
    pub fn new(mon: &MonitorInfo) -> Result<Self> {
        unsafe {
            let factory: IDXGIFactory1 = CreateDXGIFactory1().context("DXGI 팩토리 생성 실패")?;
            // 이 모니터에 연결된 출력(그래픽 카드)을 찾는다 (노트북은 내장/외장 GPU 가 다를 수 있음)
            let mut found = None;
            let mut ai = 0;
            while let Ok(adapter) = factory.EnumAdapters1(ai) {
                let mut oi = 0;
                while let Ok(output) = adapter.EnumOutputs(oi) {
                    let d = output.GetDesc()?;
                    let r = d.DesktopCoordinates;
                    if r.left == mon.x
                        && r.top == mon.y
                        && (r.right - r.left) as u32 == mon.width
                        && (r.bottom - r.top) as u32 == mon.height
                    {
                        found = Some((adapter.clone(), output));
                        break;
                    }
                    oi += 1;
                }
                if found.is_some() {
                    break;
                }
                ai += 1;
            }
            let (adapter, output) = found.context("이 모니터의 DXGI 출력을 찾지 못함")?;
            let mut device = None;
            let mut ctx = None;
            D3D11CreateDevice(
                &adapter,
                D3D_DRIVER_TYPE_UNKNOWN,
                HMODULE::default(),
                D3D11_CREATE_DEVICE_BGRA_SUPPORT,
                None,
                D3D11_SDK_VERSION,
                Some(&mut device),
                None,
                Some(&mut ctx),
            )
            .context("Direct3D 장치 생성 실패")?;
            let (device, ctx) = (device.context("장치 없음")?, ctx.context("장치 문맥 없음")?);
            let out1: IDXGIOutput1 = output.cast()?;
            let dup = out1.DuplicateOutput(&device).context("화면 복제 시작 실패 (다른 프로그램이 사용 중이거나 지원 안 함)")?;
            let dd = dup.GetDesc();
            if dd.ModeDesc.Format != DXGI_FORMAT_B8G8R8A8_UNORM {
                bail!("지원하지 않는 화면 형식 {:?} (HDR 등)", dd.ModeDesc.Format);
            }
            let (width, height) = (dd.ModeDesc.Width, dd.ModeDesc.Height);
            let desc = D3D11_TEXTURE2D_DESC {
                Width: width,
                Height: height,
                MipLevels: 1,
                ArraySize: 1,
                Format: DXGI_FORMAT_B8G8R8A8_UNORM,
                SampleDesc: DXGI_SAMPLE_DESC { Count: 1, Quality: 0 },
                Usage: D3D11_USAGE_STAGING,
                BindFlags: 0,
                CPUAccessFlags: D3D11_CPU_ACCESS_READ.0 as u32,
                MiscFlags: 0,
            };
            let mut staging = None;
            device.CreateTexture2D(&desc, None, Some(&mut staging))?;
            Ok(Self {
                mon: mon.clone(),
                _device: device,
                ctx,
                dup,
                staging: staging.context("스테이징 텍스처 없음")?,
                width,
                height,
                last: vec![0; (width * height * 4) as usize],
                has_frame: false,
            })
        }
    }

    /// 아직 받은 화면이 없는지 (정지된 화면에서는 DXGI 가 변화가 있을 때까지 첫 이미지를 안 줄 수 있다)
    pub fn needs_seed(&self) -> bool {
        !self.has_frame
    }

    /// 첫 화면을 GDI 로 찍어 채워 둔다 (크기가 같을 때만)
    pub fn seed(&mut self, frame: &RawFrame) {
        if frame.width == self.width && frame.height == self.height && frame.bgra.len() == self.last.len() {
            self.last.copy_from_slice(&frame.bgra);
            self.has_frame = true;
        }
    }

    /// 최신 화면 (+커서) 을 out 에 담는다. 화면 복제가 끊기면 오류 → 호출 쪽이 다시 만든다.
    pub fn capture(&mut self, out: &mut RawFrame) -> Result<()> {
        unsafe {
            let mut info = DXGI_OUTDUPL_FRAME_INFO::default();
            let mut res: Option<IDXGIResource> = None;
            // 첫 화면은 조금 기다리고, 그다음부터는 기다리지 않는다 (속도는 호출 쪽이 조절)
            let wait = if self.has_frame { 0 } else { 100 };
            match self.dup.AcquireNextFrame(wait, &mut info, &mut res) {
                Ok(()) => {
                    // 마우스만 움직이면 LastPresentTime 이 0 (새 이미지 없음)
                    if info.LastPresentTime != 0 {
                        if let Some(r) = &res {
                            let tex: ID3D11Texture2D = r.cast()?;
                            self.ctx.CopyResource(&self.staging, &tex);
                            let mut m = D3D11_MAPPED_SUBRESOURCE::default();
                            self.ctx.Map(&self.staging, 0, D3D11_MAP_READ, 0, Some(&mut m))?;
                            let row = (self.width * 4) as usize;
                            let src = m.pData as *const u8;
                            for y in 0..self.height as usize {
                                std::ptr::copy_nonoverlapping(src.add(y * m.RowPitch as usize), self.last.as_mut_ptr().add(y * row), row);
                            }
                            self.ctx.Unmap(&self.staging, 0);
                            self.has_frame = true;
                        }
                    }
                    let _ = self.dup.ReleaseFrame();
                }
                Err(e) if e.code() == DXGI_ERROR_WAIT_TIMEOUT => {}
                Err(e) => return Err(e).context("화면 복제 끊김 (잠금 화면·UAC·해상도 변경)"),
            }
        }
        if !self.has_frame {
            bail!("아직 화면을 받지 못함");
        }
        out.width = self.width;
        out.height = self.height;
        out.bgra.clear();
        out.bgra.extend_from_slice(&self.last);
        self.draw_cursor(out);
        Ok(())
    }

    fn draw_cursor(&self, out: &mut RawFrame) {
        let mut ci = CURSORINFO { cbSize: std::mem::size_of::<CURSORINFO>() as u32, ..Default::default() };
        if unsafe { GetCursorInfo(&mut ci) }.is_err() || ci.flags.0 & CURSOR_SHOWING.0 == 0 {
            return;
        }
        draw_arrow(out, ci.ptScreenPos.x - self.mon.x, ci.ptScreenPos.y - self.mon.y);
    }
}

/// 커서 모양 (1 = 검은 테두리, 2 = 흰 안쪽, 공백 = 투명). 표준 화살표.
const ARROW: [&str; 17] = [
    "1",
    "11",
    "121",
    "1221",
    "12221",
    "122221",
    "1222221",
    "12222221",
    "122222221",
    "1222222221",
    "12222211111",
    "1221221",
    "121 1221",
    "11  1221",
    "1    1221",
    "     1221",
    "      11",
];

pub fn draw_arrow(out: &mut RawFrame, x0: i32, y0: i32) {
    let (w, h) = (out.width as i32, out.height as i32);
    for (dy, row) in ARROW.iter().enumerate() {
        for (dx, c) in row.bytes().enumerate() {
            let color = match c {
                b'1' => [0u8, 0, 0, 255],
                b'2' => [255u8, 255, 255, 255],
                _ => continue,
            };
            let (x, y) = (x0 + dx as i32, y0 + dy as i32);
            if x >= 0 && y >= 0 && x < w && y < h {
                let o = ((y * w + x) * 4) as usize;
                out.bgra[o..o + 4].copy_from_slice(&color);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn arrow_clips_at_edges() {
        let mut f = RawFrame { bgra: vec![7; 8 * 8 * 4], width: 8, height: 8 };
        draw_arrow(&mut f, 6, 6); // 일부만 화면 안
        draw_arrow(&mut f, -20, -20); // 완전히 밖
        assert_eq!(&f.bgra[(6 * 8 + 6) * 4..(6 * 8 + 6) * 4 + 4], &[0, 0, 0, 255]);
    }

    /// 성능 측정 (모니터 필요): cargo test --release -p homepilot-agent bench_capture -- --ignored --nocapture
    #[test]
    #[ignore]
    fn bench_capture() {
        let mon = crate::platform::list_monitors().unwrap().into_iter().next().unwrap();
        let mut out = RawFrame::default();
        let mut d = DxgiCapturer::new(&mon).expect("DXGI");
        let mut g0 = crate::platform::win::capture::GdiCapturer::new(&mon).unwrap();
        g0.capture_raw(&mut out).unwrap();
        d.seed(&out);
        let t = std::time::Instant::now();
        for _ in 0..120 {
            d.capture(&mut out).unwrap();
        }
        println!("DXGI {}x{}: {:.2}ms/프레임", out.width, out.height, t.elapsed().as_secs_f64() * 1000.0 / 120.0);
        let mut g = crate::platform::win::capture::GdiCapturer::new(&mon).unwrap();
        let t = std::time::Instant::now();
        for _ in 0..30 {
            g.capture(&mut out).unwrap();
        }
        println!("GDI  {}x{}: {:.2}ms/프레임", out.width, out.height, t.elapsed().as_secs_f64() * 1000.0 / 30.0);
    }
}
