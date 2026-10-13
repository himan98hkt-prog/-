//! PC 소리 전송: 지금 스피커로 나오는 소리를 캡처(WASAPI 루프백) → AAC(ADTS) 압축.
//!
//! - Windows 기본 기능만 사용 (Media Foundation 내장 AAC 인코더): 설치·라이선스 비용 없음.
//! - 소리가 나지 않을 때는 Windows 가 데이터를 주지 않으므로 아무것도 보내지 않는다.
//! - 출력은 48kHz 스테레오 16비트 → AAC-LC 128kbps, 프레임마다 ADTS 헤더 (휴대폰이 바로 디코딩).

use anyhow::{bail, Context, Result};
use std::mem::ManuallyDrop;
use windows::core::GUID;
use windows::Win32::Media::Audio::*;
use windows::Win32::Media::MediaFoundation::*;
use windows::Win32::System::Com::{
    CoCreateInstance, CoInitializeEx, CoTaskMemFree, CLSCTX_ALL, CLSCTX_INPROC_SERVER, COINIT_MULTITHREADED,
};

pub const SAMPLE_RATE: u32 = 48_000;
pub const CHANNELS: u32 = 2;
const BITRATE_BYTES: u32 = 16_000; // 128kbps

/// Microsoft AAC 인코더 MFT (Windows SDK wmcodecdsp.h 의 CLSID_AACMFTEncoder)
const CLSID_AAC_ENCODER: GUID = GUID::from_u128(0x93AF0C51_2275_45D2_A35B_F2BA21CAED00);

// WAVEFORMATEXTENSIBLE 의 SubFormat
const SUB_PCM: GUID = GUID::from_u128(0x00000001_0000_0010_8000_00aa00389b71);
const SUB_FLOAT: GUID = GUID::from_u128(0x00000003_0000_0010_8000_00aa00389b71);

#[derive(Clone, Copy, Debug, PartialEq)]
enum SampleKind {
    F32,
    I16,
    I24,
    I32,
}

/// 기본 스피커의 소리를 가로채는 캡처기
pub struct LoopbackCapture {
    client: IAudioClient,
    capture: IAudioCaptureClient,
    rate: u32,
    channels: usize,
    kind: SampleKind,
    block_align: usize,
}

unsafe impl Send for LoopbackCapture {}

impl LoopbackCapture {
    pub fn new() -> Result<Self> {
        unsafe {
            let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
            let en: IMMDeviceEnumerator = CoCreateInstance(&MMDeviceEnumerator, None, CLSCTX_ALL).context("오디오 장치 목록 실패")?;
            let dev = en.GetDefaultAudioEndpoint(eRender, eConsole).context("기본 스피커 없음")?;
            let client: IAudioClient = dev.Activate(CLSCTX_ALL, None).context("오디오 장치 열기 실패")?;
            let fmt = client.GetMixFormat()?;
            let f = *fmt;
            let tag = f.wFormatTag as u32;
            let bits = f.wBitsPerSample;
            let kind = if tag == 0xFFFE {
                let ext = *(fmt as *const WAVEFORMATEXTENSIBLE);
                let sub = ext.SubFormat;
                if sub == SUB_FLOAT {
                    SampleKind::F32
                } else if sub == SUB_PCM {
                    match bits {
                        16 => SampleKind::I16,
                        24 => SampleKind::I24,
                        _ => SampleKind::I32,
                    }
                } else {
                    CoTaskMemFree(Some(fmt as *const _));
                    bail!("지원하지 않는 소리 형식");
                }
            } else if tag == 3 {
                SampleKind::F32
            } else if tag == 1 && bits == 16 {
                SampleKind::I16
            } else {
                CoTaskMemFree(Some(fmt as *const _));
                bail!("지원하지 않는 소리 형식 (tag {tag}, {bits}비트)");
            };
            let (rate, channels, block_align) = (f.nSamplesPerSec, f.nChannels as usize, f.nBlockAlign as usize);
            // 버퍼 200ms, 루프백 모드
            let r = client.Initialize(AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, 2_000_000, 0, fmt, None);
            CoTaskMemFree(Some(fmt as *const _));
            r.context("소리 캡처 초기화 실패")?;
            let capture: IAudioCaptureClient = client.GetService()?;
            client.Start()?;
            Ok(Self { client, capture, rate, channels, kind, block_align })
        }
    }

    /// 지금까지 쌓인 소리를 48kHz 스테레오 i16 (좌우 번갈아) 로 out 에 덧붙인다.
    pub fn read(&mut self, out: &mut Vec<i16>) -> Result<()> {
        let mut raw: Vec<f32> = Vec::new(); // 원래 채널 수, 원래 속도
        unsafe {
            loop {
                let n = self.capture.GetNextPacketSize()?;
                if n == 0 {
                    break;
                }
                let mut data = std::ptr::null_mut();
                let mut frames = 0u32;
                let mut flags = 0u32;
                self.capture.GetBuffer(&mut data, &mut frames, &mut flags, None, None)?;
                let count = frames as usize * self.channels;
                if flags & (AUDCLNT_BUFFERFLAGS_SILENT.0 as u32) != 0 || data.is_null() {
                    raw.extend(std::iter::repeat_n(0.0, count));
                } else {
                    let bytes = std::slice::from_raw_parts(data, frames as usize * self.block_align);
                    let width = self.block_align / self.channels;
                    for s in bytes.chunks_exact(width).take(count) {
                        raw.push(match self.kind {
                            SampleKind::F32 => f32::from_le_bytes([s[0], s[1], s[2], s[3]]),
                            SampleKind::I16 => i16::from_le_bytes([s[0], s[1]]) as f32 / 32768.0,
                            SampleKind::I24 => (i32::from_le_bytes([0, s[0], s[1], s[2]]) >> 8) as f32 / 8_388_608.0,
                            SampleKind::I32 => i32::from_le_bytes([s[0], s[1], s[2], s[3]]) as f32 / 2_147_483_648.0,
                        });
                    }
                }
                self.capture.ReleaseBuffer(frames)?;
            }
        }
        to_stereo_48k(&raw, self.channels, self.rate, out);
        Ok(())
    }
}

impl Drop for LoopbackCapture {
    fn drop(&mut self) {
        unsafe {
            let _ = self.client.Stop();
        }
    }
}

/// 여러 채널 → 스테레오(앞 두 채널), 다른 속도 → 48kHz (선형 보간), f32 → i16
pub fn to_stereo_48k(raw: &[f32], channels: usize, rate: u32, out: &mut Vec<i16>) {
    if channels == 0 || raw.is_empty() {
        return;
    }
    let frames = raw.len() / channels;
    let lr = |i: usize| -> (f32, f32) {
        let b = i * channels;
        if channels == 1 {
            (raw[b], raw[b])
        } else {
            (raw[b], raw[b + 1])
        }
    };
    let cvt = |v: f32| (v.clamp(-1.0, 1.0) * 32767.0) as i16;
    if rate == SAMPLE_RATE {
        for i in 0..frames {
            let (l, r) = lr(i);
            out.push(cvt(l));
            out.push(cvt(r));
        }
        return;
    }
    let n_out = (frames as u64 * SAMPLE_RATE as u64 / rate as u64) as usize;
    for j in 0..n_out {
        let pos = j as f64 * rate as f64 / SAMPLE_RATE as f64;
        let i = pos as usize;
        let t = (pos - i as f64) as f32;
        let (l0, r0) = lr(i.min(frames - 1));
        let (l1, r1) = lr((i + 1).min(frames - 1));
        out.push(cvt(l0 + (l1 - l0) * t));
        out.push(cvt(r0 + (r1 - r0) * t));
    }
}

/// Windows 내장 AAC 인코더 (48kHz 스테레오 → AAC-LC ADTS)
pub struct AacEncoder {
    mft: IMFTransform,
    time: i64,
    out_size: u32,
}

unsafe impl Send for AacEncoder {}

impl AacEncoder {
    pub fn new() -> Result<Self> {
        unsafe {
            let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
            MFStartup(MF_VERSION, MFSTARTUP_NOSOCKET)?;
            let mft: IMFTransform = CoCreateInstance(&CLSID_AAC_ENCODER, None, CLSCTX_INPROC_SERVER).context("AAC 인코더 생성 실패")?;
            let inp = MFCreateMediaType()?;
            inp.SetGUID(&MF_MT_MAJOR_TYPE, &MFMediaType_Audio)?;
            inp.SetGUID(&MF_MT_SUBTYPE, &MFAudioFormat_PCM)?;
            inp.SetUINT32(&MF_MT_AUDIO_BITS_PER_SAMPLE, 16)?;
            inp.SetUINT32(&MF_MT_AUDIO_SAMPLES_PER_SECOND, SAMPLE_RATE)?;
            inp.SetUINT32(&MF_MT_AUDIO_NUM_CHANNELS, CHANNELS)?;
            mft.SetInputType(0, &inp, 0).context("AAC 입력 형식 설정 실패")?;
            let out = MFCreateMediaType()?;
            out.SetGUID(&MF_MT_MAJOR_TYPE, &MFMediaType_Audio)?;
            out.SetGUID(&MF_MT_SUBTYPE, &MFAudioFormat_AAC)?;
            out.SetUINT32(&MF_MT_AUDIO_BITS_PER_SAMPLE, 16)?;
            out.SetUINT32(&MF_MT_AUDIO_SAMPLES_PER_SECOND, SAMPLE_RATE)?;
            out.SetUINT32(&MF_MT_AUDIO_NUM_CHANNELS, CHANNELS)?;
            out.SetUINT32(&MF_MT_AUDIO_AVG_BYTES_PER_SECOND, BITRATE_BYTES)?;
            out.SetUINT32(&MF_MT_AAC_PAYLOAD_TYPE, 1)?; // ADTS
            mft.SetOutputType(0, &out, 0).context("AAC 출력 형식 설정 실패")?;
            let info = mft.GetOutputStreamInfo(0)?;
            mft.ProcessMessage(MFT_MESSAGE_NOTIFY_BEGIN_STREAMING, 0)?;
            mft.ProcessMessage(MFT_MESSAGE_NOTIFY_START_OF_STREAM, 0)?;
            Ok(Self { mft, time: 0, out_size: info.cbSize.max(8192) })
        }
    }

    /// 16비트 스테레오 샘플 → AAC 프레임들 (ADTS 헤더 포함, 이어 붙인 것)
    pub fn encode(&mut self, pcm: &[i16]) -> Result<Vec<u8>> {
        if pcm.is_empty() {
            return Ok(Vec::new());
        }
        unsafe {
            let bytes = std::slice::from_raw_parts(pcm.as_ptr() as *const u8, pcm.len() * 2);
            let buf = MFCreateMemoryBuffer(bytes.len() as u32)?;
            let mut p = std::ptr::null_mut();
            buf.Lock(&mut p, None, None)?;
            std::ptr::copy_nonoverlapping(bytes.as_ptr(), p, bytes.len());
            buf.Unlock()?;
            buf.SetCurrentLength(bytes.len() as u32)?;
            let s = MFCreateSample()?;
            s.AddBuffer(&buf)?;
            let frames = (pcm.len() / CHANNELS as usize) as i64;
            let dur = frames * 10_000_000 / SAMPLE_RATE as i64;
            s.SetSampleTime(self.time)?;
            s.SetSampleDuration(dur)?;
            self.time += dur;
            self.mft.ProcessInput(0, &s, 0).context("AAC 입력 실패")?;
            let mut out = Vec::new();
            loop {
                let os = MFCreateSample()?;
                os.AddBuffer(&MFCreateMemoryBuffer(self.out_size)?)?;
                let mut db = [MFT_OUTPUT_DATA_BUFFER {
                    dwStreamID: 0,
                    pSample: ManuallyDrop::new(Some(os)),
                    dwStatus: 0,
                    pEvents: ManuallyDrop::new(None),
                }];
                let mut status = 0u32;
                let r = self.mft.ProcessOutput(0, &mut db, &mut status);
                let sample = ManuallyDrop::take(&mut db[0].pSample);
                drop(ManuallyDrop::take(&mut db[0].pEvents));
                match r {
                    Ok(()) => {
                        let Some(sample) = sample else { break };
                        let b = sample.ConvertToContiguousBuffer()?;
                        let mut p = std::ptr::null_mut();
                        let mut len = 0u32;
                        b.Lock(&mut p, None, Some(&mut len))?;
                        out.extend_from_slice(std::slice::from_raw_parts(p, len as usize));
                        b.Unlock()?;
                    }
                    Err(e) if e.code() == MF_E_TRANSFORM_NEED_MORE_INPUT => break,
                    Err(e) => return Err(e).context("AAC 출력 실패"),
                }
            }
            Ok(out)
        }
    }
}

impl Drop for AacEncoder {
    fn drop(&mut self) {
        unsafe {
            let _ = MFShutdown();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mono_44k_to_stereo_48k() {
        let raw = vec![0.5f32; 441]; // 10ms
        let mut out = Vec::new();
        to_stereo_48k(&raw, 1, 44_100, &mut out);
        assert_eq!(out.len(), 480 * 2);
        assert!(out.iter().all(|&v| (v - 16383).abs() <= 1));
    }

    #[test]
    fn surround_takes_front_pair() {
        let raw = vec![0.25, -0.25, 1.0, 1.0, 1.0, 1.0]; // 6채널 한 프레임
        let mut out = Vec::new();
        to_stereo_48k(&raw, 6, 48_000, &mut out);
        assert_eq!(out, vec![8191, -8191]);
    }

    /// 진단용 (소리 장치 필요): 3초 동안 스피커 소리를 캡처해 몇 샘플이 왔는지 출력
    /// cargo test -p homepilot-agent loopback_probe -- --ignored --nocapture
    #[test]
    #[ignore]
    fn loopback_probe() {
        let mut cap = LoopbackCapture::new().expect("캡처");
        println!("장치 형식: {}Hz {}ch {:?} block {}", cap.rate, cap.channels, cap.kind, cap.block_align);
        let mut total = 0usize;
        let mut peak = 0i16;
        for _ in 0..150 {
            std::thread::sleep(std::time::Duration::from_millis(20));
            let mut v = Vec::new();
            cap.read(&mut v).unwrap();
            total += v.len();
            peak = peak.max(v.iter().map(|x| x.saturating_abs()).max().unwrap_or(0));
        }
        println!("받은 샘플 {total}, 최대 크기 {peak}");
    }

    /// 실제 Windows AAC 인코더로 1초 압축 (ADTS 동기 신호 확인)
    #[test]
    fn encodes_aac_adts() {
        let mut enc = AacEncoder::new().expect("AAC 인코더");
        let mut all = Vec::new();
        for k in 0..50 {
            // 20ms 씩, 440Hz
            let pcm: Vec<i16> = (0..960)
                .flat_map(|i| {
                    let t = (k * 960 + i) as f32 / 48_000.0;
                    let v = ((t * 440.0 * std::f32::consts::TAU).sin() * 8000.0) as i16;
                    [v, v]
                })
                .collect();
            all.extend(enc.encode(&pcm).unwrap());
        }
        assert!(all.len() > 1000, "출력 {} 바이트", all.len());
        assert_eq!(all[0], 0xFF);
        assert_eq!(all[1] & 0xF0, 0xF0, "ADTS 동기 신호");
        // 1초 128kbps ≈ 16KB
        assert!(all.len() < 40_000, "{}", all.len());
    }
}
