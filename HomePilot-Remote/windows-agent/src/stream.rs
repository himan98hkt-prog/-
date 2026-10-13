//! 화면 전송 스레드: 캡처 → 축소 → 변화 없으면 건너뜀 → JPEG → 세션으로 전달.
//!
//! 채널 용량이 1 이고 세션 쪽이 "가장 최신 프레임만" 보관하므로,
//! 네트워크가 느리면 오래된 프레임은 버려지고 지연이 쌓이지 않는다.

use crate::encode;
use crate::platform::{Capturer, RawFrame};
use homepilot_protocol::app::{encode_frame, FrameHeader, MonitorInfo};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::mpsc;

#[derive(Debug, Clone, Copy)]
pub struct StreamParams {
    pub quality: u8,
    pub scale_pct: u8,
    pub max_fps: u8,
}

pub struct StreamHandle {
    stop: Arc<AtomicBool>,
    pub frames: mpsc::Receiver<Vec<u8>>,
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

/// 프레임 머리말을 붙여 세션으로 보낸다. 세션이 끝났으면 false.
fn send(tx: &mpsc::Sender<Vec<u8>>, frame_id: &mut u32, mon: &MonitorInfo, img: &RawFrame, raw: &RawFrame, jpeg: &[u8]) -> bool {
    *frame_id = frame_id.wrapping_add(1);
    let h = FrameHeader {
        frame_id: *frame_id,
        monitor: mon.index as u8,
        width: img.width,
        height: img.height,
        src_width: raw.width,
        src_height: raw.height,
        captured_ms: now_ms(),
    };
    tx.blocking_send(encode_frame(&h, jpeg)).is_ok()
}

pub fn start(mon: MonitorInfo, p: StreamParams) -> StreamHandle {
    let stop = Arc::new(AtomicBool::new(false));
    let (tx, rx) = mpsc::channel(1);
    let stop2 = stop.clone();
    std::thread::Builder::new()
        .name(format!("stream-{}", mon.index))
        .spawn(move || {
            let interval = Duration::from_millis(1000 / p.max_fps.clamp(1, 30) as u64);
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
            while !stop2.load(Ordering::Relaxed) {
                let t0 = Instant::now();
                if cap.is_none() {
                    match Capturer::new(&mon) {
                        Ok(c) => cap = Some(c),
                        Err(e) => {
                            tracing::warn!("캡처 준비 실패: {e:#}");
                            std::thread::sleep(Duration::from_secs(1));
                            continue;
                        }
                    }
                }
                if let Err(e) = cap.as_mut().unwrap().capture(&mut raw) {
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
                encode::downscale(&raw, p.scale_pct, &mut scaled);
                if scaled.bgra != prev {
                    // 화면이 바뀌는 동안: 설정한 크기·화질로 부드럽게
                    let sharp = p.quality >= SHARP_QUALITY;
                    match encode::jpeg(&scaled, p.quality, sharp) {
                        Ok(j) => {
                            if !send(&tx, &mut frame_id, &mon, &scaled, &raw, &j) {
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
                            if !send(&tx, &mut frame_id, &mon, &raw, &raw, &j) {
                                break;
                            }
                        }
                        Err(e) => tracing::warn!("{e:#}"),
                    }
                }
                if let Some(rest) = interval.checked_sub(t0.elapsed()) {
                    std::thread::sleep(rest);
                }
            }
            tracing::debug!("화면 전송 스레드 종료");
        })
        .expect("화면 전송 스레드 시작 실패");
    StreamHandle { stop, frames: rx }
}
