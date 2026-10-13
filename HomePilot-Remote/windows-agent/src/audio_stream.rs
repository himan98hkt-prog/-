//! PC 소리 전송 스레드: 20ms 마다 스피커 소리를 모아 AAC 로 압축해 세션으로 보낸다.
//! 네트워크가 밀려 채널이 차 있으면 그 조각은 버린다 (소리는 늦게 오는 것보다 건너뛰는 편이 낫다).

use crate::platform::{AacEncoder, LoopbackCapture};
use anyhow::Result;
use homepilot_protocol::app::encode_audio;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::mpsc;

pub struct AudioHandle {
    stop: Arc<AtomicBool>,
    pub packets: mpsc::Receiver<Vec<u8>>,
}

impl Drop for AudioHandle {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
    }
}

fn now_ms() -> u64 {
    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_millis() as u64).unwrap_or(0)
}

/// 캡처·인코더를 준비해 시작한다. 준비에 실패하면 오류 (스피커 없음 등).
pub fn start() -> Result<AudioHandle> {
    let stop = Arc::new(AtomicBool::new(false));
    let (tx, rx) = mpsc::channel(16);
    let (ready_tx, ready_rx) = std::sync::mpsc::channel::<Result<(), String>>();
    let stop2 = stop.clone();
    std::thread::Builder::new().name("audio".into()).spawn(move || {
        // COM 개체는 이 스레드에서 만들고 쓴다
        let (mut cap, mut enc) = match LoopbackCapture::new().and_then(|c| Ok((c, AacEncoder::new()?))) {
            Ok(x) => {
                let _ = ready_tx.send(Ok(()));
                x
            }
            Err(e) => {
                let _ = ready_tx.send(Err(format!("{e:#}")));
                return;
            }
        };
        let mut pcm = Vec::with_capacity(48_000);
        let (mut sent, mut captured) = (0u64, 0u64);
        while !stop2.load(Ordering::Relaxed) {
            std::thread::sleep(Duration::from_millis(20));
            pcm.clear();
            if let Err(e) = cap.read(&mut pcm) {
                tracing::warn!("소리 캡처 오류: {e:#}");
                break;
            }
            if pcm.is_empty() {
                continue; // 소리가 나지 않음
            }
            captured += pcm.len() as u64;
            match enc.encode(&pcm) {
                Ok(aac) if !aac.is_empty() => {
                    if sent == 0 {
                        tracing::info!("소리 전송: 첫 묶음 {} 바이트 (캡처 {captured} 샘플)", aac.len());
                    }
                    sent += 1;
                    match tx.try_send(encode_audio(now_ms(), &aac)) {
                        Ok(()) | Err(mpsc::error::TrySendError::Full(_)) => {}
                        Err(mpsc::error::TrySendError::Closed(_)) => break,
                    }
                }
                Ok(_) => {}
                Err(e) => {
                    tracing::warn!("소리 압축 오류: {e:#}");
                    break;
                }
            }
        }
        tracing::info!("소리 전송 종료 (캡처 {captured} 샘플, 보낸 묶음 {sent})");
    })?;
    match ready_rx.recv_timeout(Duration::from_secs(3)) {
        Ok(Ok(())) => Ok(AudioHandle { stop, packets: rx }),
        Ok(Err(e)) => anyhow::bail!("PC 소리를 가져올 수 없습니다: {e}"),
        Err(_) => anyhow::bail!("PC 소리 준비 시간 초과"),
    }
}
