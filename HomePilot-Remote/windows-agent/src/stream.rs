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
                    match encode::jpeg(&scaled, p.quality) {
                        Ok(j) => {
                            frame_id = frame_id.wrapping_add(1);
                            let h = FrameHeader {
                                frame_id,
                                monitor: mon.index as u8,
                                width: scaled.width,
                                height: scaled.height,
                                src_width: raw.width,
                                src_height: raw.height,
                                captured_ms: now_ms(),
                            };
                            if tx.blocking_send(encode_frame(&h, &j)).is_err() {
                                break; // 세션 종료
                            }
                            std::mem::swap(&mut prev, &mut scaled.bgra);
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
