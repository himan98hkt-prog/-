//! H.264 동영상 압축 (Windows Media Foundation 내장 인코더).
//!
//! - Windows 에 포함된 Microsoft H.264 인코더를 쓴다: 별도 설치·라이선스 비용 없음.
//! - 지연을 줄이려고 Baseline 프로필(B 프레임 없음) + 저지연 모드 + 고정 비트레이트.
//! - 출력은 Annex-B (00 00 00 01 시작 코드). 키프레임 앞에는 SPS/PPS 를 붙여
//!   휴대폰 디코더가 어느 키프레임에서든 시작할 수 있게 한다.

use crate::platform::RawFrame;
use anyhow::{bail, Context, Result};
use std::mem::ManuallyDrop;
use windows::core::{Interface, GUID, VARIANT};
use windows::Win32::Media::MediaFoundation::*;
use windows::Win32::System::Com::{CoCreateInstance, CoInitializeEx, CLSCTX_INPROC_SERVER, COINIT_MULTITHREADED};

pub struct H264Encoder {
    mft: IMFTransform,
    codec: Option<ICodecAPI>,
    width: u32,
    height: u32,
    fps: u32,
    frame_no: i64,
    nv12: Vec<u8>,
    out_size: u32,
    provides_samples: bool,
    /// SPS/PPS (Annex-B). 키프레임에 없으면 앞에 붙인다.
    seq_header: Vec<u8>,
}

// IMFTransform 은 한 스레드(화면 전송 스레드)에서만 만들고 쓴다.
unsafe impl Send for H264Encoder {}

fn set_size(t: &IMFMediaType, key: &GUID, a: u32, b: u32) -> windows::core::Result<()> {
    unsafe { t.SetUINT64(key, ((a as u64) << 32) | b as u64) }
}

impl H264Encoder {
    /// width/height 는 짝수여야 한다. fps 1~60, bitrate 는 bps.
    pub fn new(width: u32, height: u32, fps: u32, bitrate: u32) -> Result<Self> {
        if !width.is_multiple_of(2) || !height.is_multiple_of(2) || width == 0 || height == 0 {
            bail!("H.264 크기는 짝수여야 합니다 ({width}x{height})");
        }
        unsafe {
            // 이 스레드에서 COM·MF 사용 준비 (이미 되어 있으면 무시)
            let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
            MFStartup(MF_VERSION, MFSTARTUP_NOSOCKET).context("Media Foundation 시작 실패")?;
            let mft: IMFTransform =
                CoCreateInstance(&CLSID_MSH264EncoderMFT, None, CLSCTX_INPROC_SERVER).context("H.264 인코더 생성 실패")?;

            // 출력 형식을 먼저 정해야 한다 (MS H.264 인코더 규칙)
            let out = MFCreateMediaType()?;
            out.SetGUID(&MF_MT_MAJOR_TYPE, &MFMediaType_Video)?;
            out.SetGUID(&MF_MT_SUBTYPE, &MFVideoFormat_H264)?;
            out.SetUINT32(&MF_MT_AVG_BITRATE, bitrate)?;
            set_size(&out, &MF_MT_FRAME_SIZE, width, height)?;
            set_size(&out, &MF_MT_FRAME_RATE, fps, 1)?;
            set_size(&out, &MF_MT_PIXEL_ASPECT_RATIO, 1, 1)?;
            out.SetUINT32(&MF_MT_INTERLACE_MODE, MFVideoInterlace_Progressive.0 as u32)?;
            out.SetUINT32(&MF_MT_MPEG2_PROFILE, eAVEncH264VProfile_Base.0 as u32)?;
            mft.SetOutputType(0, &out, 0).context("H.264 출력 형식 설정 실패")?;

            let inp = MFCreateMediaType()?;
            inp.SetGUID(&MF_MT_MAJOR_TYPE, &MFMediaType_Video)?;
            inp.SetGUID(&MF_MT_SUBTYPE, &MFVideoFormat_NV12)?;
            set_size(&inp, &MF_MT_FRAME_SIZE, width, height)?;
            set_size(&inp, &MF_MT_FRAME_RATE, fps, 1)?;
            set_size(&inp, &MF_MT_PIXEL_ASPECT_RATIO, 1, 1)?;
            inp.SetUINT32(&MF_MT_INTERLACE_MODE, MFVideoInterlace_Progressive.0 as u32)?;
            mft.SetInputType(0, &inp, 0).context("H.264 입력 형식 설정 실패")?;

            let codec = mft.cast::<ICodecAPI>().ok();
            if let Some(c) = &codec {
                let _ = c.SetValue(&CODECAPI_AVLowLatencyMode, &VARIANT::from(true));
                let _ = c.SetValue(&CODECAPI_AVEncCommonRateControlMode, &VARIANT::from(eAVEncCommonRateControlMode_CBR.0 as u32));
                let _ = c.SetValue(&CODECAPI_AVEncCommonMeanBitRate, &VARIANT::from(bitrate));
                // 2초마다 키프레임 (네트워크 손실 후 빨리 회복)
                let _ = c.SetValue(&CODECAPI_AVEncMPVGOPSize, &VARIANT::from(fps * 2));
            }

            let info = mft.GetOutputStreamInfo(0)?;
            let provides_samples = info.dwFlags & (MFT_OUTPUT_STREAM_PROVIDES_SAMPLES.0 as u32) != 0;
            mft.ProcessMessage(MFT_MESSAGE_NOTIFY_BEGIN_STREAMING, 0)?;
            mft.ProcessMessage(MFT_MESSAGE_NOTIFY_START_OF_STREAM, 0)?;

            let mut e = Self {
                mft,
                codec,
                width,
                height,
                fps: fps.max(1),
                frame_no: 0,
                nv12: vec![0; (width * height * 3 / 2) as usize],
                out_size: info.cbSize.max(width * height),
                provides_samples,
                seq_header: Vec::new(),
            };
            e.read_seq_header();
            Ok(e)
        }
    }

    /// 다음 프레임을 키프레임으로 만든다 (휴대폰 디코더 시작·오류 복구).
    pub fn force_keyframe(&self) {
        if let Some(c) = &self.codec {
            unsafe {
                let _ = c.SetValue(&CODECAPI_AVEncVideoForceKeyFrame, &VARIANT::from(1u32));
            }
        }
    }

    fn read_seq_header(&mut self) {
        unsafe {
            if let Ok(t) = self.mft.GetOutputCurrentType(0) {
                if let Ok(n) = t.GetBlobSize(&MF_MT_MPEG_SEQUENCE_HEADER) {
                    let mut buf = vec![0u8; n as usize];
                    if t.GetBlob(&MF_MT_MPEG_SEQUENCE_HEADER, &mut buf, None).is_ok() {
                        self.seq_header = buf;
                    }
                }
            }
        }
    }

    /// BGRA 화면(이미 width x height 로 맞춘 것) → H.264. 압축된 출력이 아직 없으면 빈 Vec.
    /// 돌려주는 bool 은 키프레임 여부.
    pub fn encode(&mut self, frame: &RawFrame) -> Result<Option<(Vec<u8>, bool)>> {
        if frame.width != self.width || frame.height != self.height {
            bail!("프레임 크기가 인코더와 다름");
        }
        bgra_to_nv12(&frame.bgra, self.width as usize, self.height as usize, &mut self.nv12);
        unsafe {
            let buf = MFCreateMemoryBuffer(self.nv12.len() as u32)?;
            let mut p = std::ptr::null_mut();
            buf.Lock(&mut p, None, None)?;
            std::ptr::copy_nonoverlapping(self.nv12.as_ptr(), p, self.nv12.len());
            buf.Unlock()?;
            buf.SetCurrentLength(self.nv12.len() as u32)?;
            let sample = MFCreateSample()?;
            sample.AddBuffer(&buf)?;
            let dur = 10_000_000 / self.fps as i64; // 100ns 단위
            sample.SetSampleTime(self.frame_no * dur)?;
            sample.SetSampleDuration(dur)?;
            self.frame_no += 1;
            self.mft.ProcessInput(0, &sample, 0).context("H.264 입력 실패")?;
            self.drain()
        }
    }

    unsafe fn drain(&mut self) -> Result<Option<(Vec<u8>, bool)>> {
        let mut out_all = Vec::new();
        let mut key = false;
        loop {
            let sample = if self.provides_samples {
                None
            } else {
                let s = MFCreateSample()?;
                s.AddBuffer(&MFCreateMemoryBuffer(self.out_size)?)?;
                Some(s)
            };
            let mut db = [MFT_OUTPUT_DATA_BUFFER {
                dwStreamID: 0,
                pSample: ManuallyDrop::new(sample),
                dwStatus: 0,
                pEvents: ManuallyDrop::new(None),
            }];
            let mut status = 0u32;
            let r = self.mft.ProcessOutput(0, &mut db, &mut status);
            let s = ManuallyDrop::take(&mut db[0].pSample);
            drop(ManuallyDrop::take(&mut db[0].pEvents));
            match r {
                Ok(()) => {
                    let Some(s) = s else { break };
                    let clean = s.GetUINT32(&MFSampleExtension_CleanPoint).unwrap_or(0) != 0;
                    let b = s.ConvertToContiguousBuffer()?;
                    let mut p = std::ptr::null_mut();
                    let mut len = 0u32;
                    b.Lock(&mut p, None, Some(&mut len))?;
                    let data = std::slice::from_raw_parts(p, len as usize);
                    if clean {
                        key = true;
                        if !contains_nal(data, 7) {
                            if self.seq_header.is_empty() {
                                self.read_seq_header();
                            }
                            out_all.extend_from_slice(&self.seq_header);
                        }
                    }
                    out_all.extend_from_slice(data);
                    b.Unlock()?;
                }
                Err(e) if e.code() == MF_E_TRANSFORM_NEED_MORE_INPUT => break,
                Err(e) if e.code() == MF_E_TRANSFORM_STREAM_CHANGE => {
                    // 출력 형식이 바뀌었다고 알림 → 현재 형식을 다시 지정하고 계속
                    let t = self.mft.GetOutputAvailableType(0, 0)?;
                    self.mft.SetOutputType(0, &t, 0)?;
                    self.read_seq_header();
                }
                Err(e) => return Err(e).context("H.264 출력 실패"),
            }
        }
        Ok(if out_all.is_empty() { None } else { Some((out_all, key)) })
    }
}

impl Drop for H264Encoder {
    fn drop(&mut self) {
        unsafe {
            let _ = self.mft.ProcessMessage(MFT_MESSAGE_NOTIFY_END_OF_STREAM, 0);
            let _ = MFShutdown();
        }
    }
}

/// Annex-B 안에 해당 종류의 NAL 이 있는지 (7 = SPS)
pub fn contains_nal(data: &[u8], nal_type: u8) -> bool {
    let mut i = 0;
    while i + 4 < data.len() {
        if data[i] == 0 && data[i + 1] == 0 && (data[i + 2] == 1 || (data[i + 2] == 0 && data[i + 3] == 1)) {
            let start = if data[i + 2] == 1 { i + 3 } else { i + 4 };
            if start < data.len() && data[start] & 0x1f == nal_type {
                return true;
            }
            i = start;
        } else {
            i += 1;
        }
    }
    false
}

/// BGRA → NV12 (BT.601 제한 범위, 2x2 색 평균). width·height 는 짝수.
pub fn bgra_to_nv12(bgra: &[u8], w: usize, h: usize, out: &mut [u8]) {
    let (y_plane, uv_plane) = out.split_at_mut(w * h);
    for y in 0..h {
        let row = &bgra[y * w * 4..(y + 1) * w * 4];
        let yrow = &mut y_plane[y * w..(y + 1) * w];
        for (x, px) in row.as_chunks::<4>().0.iter().enumerate() {
            let (b, g, r) = (px[0] as i32, px[1] as i32, px[2] as i32);
            yrow[x] = (((66 * r + 129 * g + 25 * b + 128) >> 8) + 16) as u8;
        }
    }
    for y in (0..h).step_by(2) {
        for x in (0..w).step_by(2) {
            let mut sb = 0;
            let mut sg = 0;
            let mut sr = 0;
            for (dx, dy) in [(0, 0), (1, 0), (0, 1), (1, 1)] {
                let o = ((y + dy) * w + x + dx) * 4;
                sb += bgra[o] as i32;
                sg += bgra[o + 1] as i32;
                sr += bgra[o + 2] as i32;
            }
            let (b, g, r) = (sb / 4, sg / 4, sr / 4);
            let u = ((-38 * r - 74 * g + 112 * b + 128) >> 8) + 128;
            let v = ((112 * r - 94 * g - 18 * b + 128) >> 8) + 128;
            let o = (y / 2) * w + x;
            uv_plane[o] = u.clamp(0, 255) as u8;
            uv_plane[o + 1] = v.clamp(0, 255) as u8;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nv12_white_and_black() {
        let mut bgra = vec![255u8; 4 * 4 * 4];
        bgra[..16].fill(0); // 첫 줄 앞 4픽셀 검정
        let mut out = vec![0u8; 4 * 4 * 3 / 2];
        bgra_to_nv12(&bgra, 4, 4, &mut out);
        assert_eq!(out[0], 16); // 검정 Y
        assert_eq!(out[4], 235); // 흰색 Y
        assert!((out[16] as i32 - 128).abs() <= 1); // 무채색 U
    }

    #[test]
    fn finds_sps() {
        assert!(contains_nal(&[0, 0, 0, 1, 0x67, 1, 2, 3], 7));
        assert!(contains_nal(&[0, 0, 1, 0x68, 9, 0, 0, 1, 0x67, 1], 7));
        assert!(!contains_nal(&[0, 0, 0, 1, 0x65, 1, 2, 3], 7));
    }

    /// 성능 측정: cargo test --release -p homepilot-agent bench_pipeline -- --ignored --nocapture
    #[test]
    #[ignore]
    fn bench_pipeline() {
        for (sw, sh, pct) in [(1920u32, 1080u32, 70u8), (1920, 1080, 100)] {
            let src = RawFrame { bgra: (0..sw * sh * 4).map(|i| (i % 251) as u8).collect(), width: sw, height: sh };
            let mut scaled = RawFrame::default();
            let t = std::time::Instant::now();
            for _ in 0..30 {
                crate::encode::downscale(&src, pct, &mut scaled);
            }
            let ds = t.elapsed().as_secs_f64() * 1000.0 / 30.0;
            let (w, h) = (scaled.width & !1, scaled.height & !1);
            let mut img = RawFrame { bgra: vec![0; (w * h * 4) as usize], width: w, height: h };
            let mut enc = H264Encoder::new(w, h, 60, 6_000_000).unwrap();
            let t = std::time::Instant::now();
            for i in 0..120u32 {
                // 매 프레임 조금씩 바뀌는 화면
                for (j, px) in img.bgra.as_chunks_mut::<4>().0.iter_mut().enumerate().step_by(97) {
                    *px = [(i + j as u32) as u8, 80, 200, 255];
                }
                enc.encode(&img).unwrap();
            }
            let en = t.elapsed().as_secs_f64() * 1000.0 / 120.0;
            println!("{sw}x{sh} {pct}% → {w}x{h}: 축소 {ds:.1}ms, NV12+H.264 {en:.1}ms /프레임");
        }
    }

    /// 실제 Windows 인코더로 화면 몇 장을 압축해 본다 (Windows 에서만).
    #[test]
    fn encodes_real_frames() {
        let (w, h) = (640u32, 360u32);
        let mut enc = H264Encoder::new(w, h, 30, 2_000_000).expect("인코더");
        let mut got_key = false;
        let mut total = 0usize;
        for i in 0..30u32 {
            let mut bgra = vec![0u8; (w * h * 4) as usize];
            for (j, px) in bgra.as_chunks_mut::<4>().0.iter_mut().enumerate() {
                let x = (j as u32 % w + i * 8) % 255;
                px.copy_from_slice(&[x as u8, (x / 2) as u8, 200, 255]);
            }
            if let Some((data, key)) = enc.encode(&RawFrame { bgra, width: w, height: h }).unwrap() {
                assert_eq!(&data[..3], &[0, 0, 0], "Annex-B 시작 코드");
                if key {
                    assert!(contains_nal(&data, 7), "키프레임에 SPS 포함");
                    got_key = true;
                }
                total += data.len();
            }
        }
        assert!(got_key, "첫 키프레임");
        assert!(total > 0 && total < (w * h * 4 * 30) as usize / 20, "압축됨: {total} bytes");
    }
}
