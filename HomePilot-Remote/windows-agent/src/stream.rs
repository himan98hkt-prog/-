//! 화면 전송 스레드: 캡처 → 축소 → 압축 → 세션으로 전달.
//!
//! 두 가지 방식
//! - JPEG: 프레임마다 독립 이미지. 변화 없으면 건너뛰고, 멈춘 화면은 원본 고화질로 다듬는다.
//!   채널 용량 1 + 세션이 "가장 최신 프레임만" 보관 → 네트워크가 느리면 오래된 프레임은 버려진다.
//! - H.264: 프레임끼리 이어져 있어 중간 프레임을 버리면 화면이 깨진다. 대신 네트워크가 밀리면
//!   세션이 `congested` 를 켜고, 이 스레드는 그동안 압축 자체를 건너뛴다(다음 프레임이 최신 화면을 담음).

use crate::encode;
use crate::platform::{Capturer, H264Encoder, RawFrame};
use homepilot_protocol::app::{encode_frame, encode_video, FrameHeader, MonitorInfo};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::mpsc;

#[derive(Debug, Clone, Copy)]
pub struct StreamParams {
    pub quality: u8,
    pub scale_pct: u8,
    pub max_fps: u8,
    /// true 면 H.264 를 시도한다 (실패하면 JPEG)
    pub h264: bool,
    /// H.264 목표 비트레이트(kbps), 0 = 자동
    pub bitrate_kbps: u32,
}

pub struct StreamHandle {
    stop: Arc<AtomicBool>,
    pub frames: mpsc::Receiver<Vec<u8>>,
    /// 실제 전송 방식이 H.264 인지
    pub h264: bool,
    /// 세션 → 스레드: 네트워크가 밀리니 압축을 잠시 쉬어라 (H.264)
    pub congested: Arc<AtomicBool>,
    /// 세션 → 스레드: 다음 프레임을 키프레임으로 (H.264)
    pub want_key: Arc<AtomicBool>,
}

impl Drop for StreamHandle {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
    }
}

fn now_ms() -> u64 {
    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_millis() as u64).unwrap_or(0)
}

/// 화면 변화가 멈춘 뒤 고화질 프레임을 보낼 때까지 기다리는 시간.
const REFINE_AFTER: Duration = Duration::from_millis(300);
/// 멈춘 화면을 다듬을 때의 JPEG 화질 (원본 해상도, 색 정보 유지).
const REFINE_QUALITY: u8 = 90;
/// 이 화질 이상을 요청하면 움직이는 동안에도 색 정보를 줄이지 않는다.
const SHARP_QUALITY: u8 = 75;

fn header(frame_id: &mut u32, mon: &MonitorInfo, img: &RawFrame, raw: &RawFrame) -> FrameHeader {
    *frame_id = frame_id.wrapping_add(1);
    FrameHeader {
        frame_id: *frame_id,
        monitor: mon.index as u8,
        width: img.width,
        height: img.height,
        src_width: raw.width,
        src_height: raw.height,
        captured_ms: now_ms(),
    }
}

/// H.264 자동 비트레이트: 화질에 따라 픽셀당 비트를 정하고 1~12 Mbps 로 제한.
pub fn auto_bitrate(width: u32, height: u32, fps: u32, quality: u8) -> u32 {
    let bpp = 0.04 + quality.clamp(10, 95) as f64 / 100.0 * 0.08;
    ((width as f64 * height as f64 * fps as f64 * bpp) as u32).clamp(1_000_000, 12_000_000)
}

/// 짝수 크기로 맞춘 축소 크기 (H.264 는 짝수만 가능)
fn even_size(raw: &RawFrame, scale_pct: u8) -> (u32, u32) {
    let pct = scale_pct.clamp(10, 100) as u32;
    (((raw.width * pct / 100).max(2)) & !1, ((raw.height * pct / 100).max(2)) & !1)
}

/// 이미 축소된 이미지를 짝수 크기로 자른다 (맨 오른쪽·아래 한 줄).
fn crop_even(img: &mut RawFrame) {
    let (w, h) = (img.width & !1, img.height & !1);
    if w == img.width && h == img.height {
        return;
    }
    let mut out = Vec::with_capacity((w * h * 4) as usize);
    for y in 0..h as usize {
        let s = y * img.width as usize * 4;
        out.extend_from_slice(&img.bgra[s..s + w as usize * 4]);
    }
    img.bgra = out;
    img.width = w;
    img.height = h;
}

/// 시험 화면: 회색 바탕 위를 주황 사각형이 가로로 움직인다 (매 프레임 바뀜)
fn fill_test_pattern(out: &mut RawFrame, w: u32, h: u32, n: u32) {
    out.width = w;
    out.height = h;
    out.bgra.resize((w * h * 4) as usize, 0);
    out.bgra.fill(60);
    let size = (h / 6).max(8);
    let x0 = (n * 12) % w.saturating_sub(size).max(1);
    let y0 = h / 2 - size / 2;
    for y in y0..y0 + size {
        let row = ((y * w + x0) * 4) as usize;
        for px in out.bgra[row..row + (size * 4) as usize].as_chunks_mut::<4>().0 {
            *px = [0, 140, 255, 255];
        }
    }
}

pub fn start(mon: MonitorInfo, p: StreamParams) -> StreamHandle {
    let stop = Arc::new(AtomicBool::new(false));
    let congested = Arc::new(AtomicBool::new(false));
    let want_key = Arc::new(AtomicBool::new(true));
    let (tx, rx) = mpsc::channel(1);
    // 인코더는 전송 스레드에서 만들어야 하므로(COM), 성공 여부를 기다렸다가 알려 준다.
    let (ready_tx, ready_rx) = std::sync::mpsc::channel::<bool>();
    let (stop2, congested2, want_key2) = (stop.clone(), congested.clone(), want_key.clone());
    std::thread::Builder::new()
        .name(format!("stream-{}", mon.index))
        .spawn(move || {
            // 성능 측정·자동 테스트용: 화면 대신 움직이는 시험 화면 (HOMEPILOT_TEST_PATTERN=1)
            let test_pattern = std::env::var_os("HOMEPILOT_TEST_PATTERN").is_some_and(|v| v == "1");
            let fps = p.max_fps.clamp(1, 60) as u32;
            let mut interval = Duration::from_micros(1_000_000 / fps as u64);
            let mut cap: Option<Capturer> = None;
            let mut raw = RawFrame::default();
            let mut scaled = RawFrame::default();
            let mut prev: Vec<u8> = Vec::new();
            let mut frame_id: u32 = 0;
            let mut failures = 0u32;
            let mut last_change = Instant::now();
            let mut refined = true;
            // 이미 원본 크기·고화질로 보내고 있으면 다듬을 필요가 없다.
            let needs_refine = p.scale_pct < 100 || p.quality < REFINE_QUALITY;
            // H.264: 화면이 멈춘 뒤에도 몇 장 더 넣어 화질이 또렷해지게 한다
            let mut idle_feed = 0u32;
            let mut enc: Option<H264Encoder> = None;
            let mut ready_tx = Some(ready_tx);

            while !stop2.load(Ordering::Relaxed) {
                let t0 = Instant::now();
                if cap.is_none() {
                    match Capturer::new(&mon) {
                        Ok(c) => cap = Some(c),
                        Err(e) => {
                            tracing::warn!("캡처 준비 실패: {e:#}");
                            if let Some(r) = ready_tx.take() {
                                let _ = r.send(false);
                            }
                            std::thread::sleep(Duration::from_secs(1));
                            continue;
                        }
                    }
                }
                let shot = if test_pattern {
                    fill_test_pattern(&mut raw, mon.width, mon.height, frame_id);
                    Ok(())
                } else {
                    cap.as_mut().unwrap().capture(&mut raw)
                };
                if let Err(e) = shot {
                    // 잠금 화면/UAC 보안 데스크톱 전환 시 일시적으로 실패한다.
                    failures += 1;
                    if failures % 20 == 1 {
                        tracing::warn!("화면 캡처 실패({failures}회): {e:#}");
                    }
                    if failures.is_multiple_of(5) {
                        cap = None; // 캡처 자원을 새로 만든다
                    }
                    std::thread::sleep(Duration::from_millis(300));
                    continue;
                }
                failures = 0;
                // 첫 화면 크기를 알면 H.264 인코더를 준비하고 결과를 알린다
                if let Some(r) = ready_tx.take() {
                    if p.h264 {
                        let (w, h) = even_size(&raw, p.scale_pct);
                        let br = if p.bitrate_kbps > 0 { p.bitrate_kbps * 1000 } else { auto_bitrate(w, h, fps, p.quality) };
                        match H264Encoder::new(w, h, fps, br) {
                            Ok(e) => {
                                tracing::info!("H.264 전송 {w}x{h} {fps}fps {}kbps", br / 1000);
                                enc = Some(e);
                            }
                            Err(e) => tracing::warn!("H.264 사용 불가 → JPEG 로 전송: {e:#}"),
                        }
                    }
                    let _ = r.send(enc.is_some());
                    if enc.is_none() {
                        // JPEG 는 프레임마다 수십 KB 라 30fps 까지만
                        interval = interval.max(Duration::from_micros(33_333));
                    }
                }
                encode::downscale(&raw, p.scale_pct, &mut scaled);

                if let Some(e) = enc.as_mut() {
                    // ---------- H.264 ----------
                    crop_even(&mut scaled);
                    let changed = scaled.bgra != prev;
                    let force = want_key2.swap(false, Ordering::Relaxed);
                    if changed {
                        idle_feed = fps / 2;
                    }
                    let feed = changed || force || idle_feed > 0;
                    if feed && !congested2.load(Ordering::Relaxed) {
                        if !changed && idle_feed > 0 {
                            idle_feed -= 1;
                        }
                        if force {
                            e.force_keyframe();
                        }
                        match e.encode(&scaled) {
                            Ok(Some((data, key))) => {
                                let h = header(&mut frame_id, &mon, &scaled, &raw);
                                if tx.blocking_send(encode_video(&h, key, &data)).is_err() {
                                    break;
                                }
                            }
                            Ok(None) => {}
                            Err(err) => {
                                tracing::warn!("H.264 압축 오류: {err:#}");
                                want_key2.store(true, Ordering::Relaxed);
                            }
                        }
                        std::mem::swap(&mut prev, &mut scaled.bgra);
                    } else if force {
                        // 밀리는 중에 온 키프레임 요청은 다음 기회로
                        want_key2.store(true, Ordering::Relaxed);
                    }
                } else {
                    // ---------- JPEG ----------
                    if scaled.bgra != prev {
                        // 화면이 바뀌는 동안: 설정한 크기·화질로 부드럽게
                        let sharp = p.quality >= SHARP_QUALITY;
                        match encode::jpeg(&scaled, p.quality, sharp) {
                            Ok(j) => {
                                let h = header(&mut frame_id, &mon, &scaled, &raw);
                                if tx.blocking_send(encode_frame(&h, &j)).is_err() {
                                    break; // 세션 종료
                                }
                                std::mem::swap(&mut prev, &mut scaled.bgra);
                                last_change = Instant::now();
                                refined = false;
                            }
                            Err(e) => tracing::warn!("{e:#}"),
                        }
                    } else if !refined && needs_refine && last_change.elapsed() >= REFINE_AFTER {
                        // 화면이 멈추면 원본 해상도·고화질 한 장으로 글씨를 또렷하게 바꾼다.
                        refined = true;
                        match encode::jpeg(&raw, REFINE_QUALITY, true) {
                            Ok(j) => {
                                let h = header(&mut frame_id, &mon, &raw, &raw);
                                if tx.blocking_send(encode_frame(&h, &j)).is_err() {
                                    break;
                                }
                            }
                            Err(e) => tracing::warn!("{e:#}"),
                        }
                    }
                }
                if let Some(rest) = interval.checked_sub(t0.elapsed()) {
                    std::thread::sleep(rest);
                }
            }
            tracing::debug!("화면 전송 스레드 종료");
        })
        .expect("화면 전송 스레드 시작 실패");
    // 캡처·인코더 준비를 최대 3초 기다린다 (실패하면 JPEG)
    let h264 = ready_rx.recv_timeout(Duration::from_secs(3)).unwrap_or(false);
    StreamHandle { stop, frames: rx, h264, congested, want_key }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bitrate_is_bounded() {
        assert_eq!(auto_bitrate(320, 180, 10, 50), 1_000_000);
        assert_eq!(auto_bitrate(3840, 2160, 30, 95), 12_000_000);
        let b = auto_bitrate(1344, 756, 20, 65);
        assert!((1_500_000..3_000_000).contains(&b), "{b}");
    }

    #[test]
    fn crops_to_even() {
        let mut img = RawFrame { bgra: (0..3 * 3 * 4).map(|i| i as u8).collect(), width: 3, height: 3 };
        crop_even(&mut img);
        assert_eq!((img.width, img.height), (2, 2));
        assert_eq!(&img.bgra[..8], &[0, 1, 2, 3, 4, 5, 6, 7]);
        assert_eq!(&img.bgra[8..16], &[12, 13, 14, 15, 16, 17, 18, 19]);
    }
}
