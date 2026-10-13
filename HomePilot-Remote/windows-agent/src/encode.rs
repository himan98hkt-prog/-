//! 화면 축소 + JPEG 인코딩.
//!
//! MVP 는 프레임마다 JPEG 를 보낸다(구현 단순·디코딩 호환성 높음).
//! 대역폭/지연 개선을 위한 H.264 하드웨어 인코딩은 후속 단계 과제로 문서화되어 있다.

use crate::platform::RawFrame;
use anyhow::{Context, Result};

/// 축소 비율(%)을 적용한 BGRA 이미지를 만든다.
/// 원본에서 대상 픽셀 하나가 덮는 영역 전체를 평균(면적 평균)한다. 예전의 2x2 표본 방식은
/// 70% 같은 비율에서 픽셀을 건너뛰어 글자가 뭉개졌다 (실기에서 확인).
pub fn downscale(src: &RawFrame, scale_pct: u8, out: &mut RawFrame) {
    let pct = scale_pct.clamp(10, 100) as u32;
    let dw = (src.width * pct / 100).max(1);
    let dh = (src.height * pct / 100).max(1);
    out.width = dw;
    out.height = dh;
    out.bgra.resize((dw * dh * 4) as usize, 0);
    if pct == 100 {
        out.bgra.copy_from_slice(&src.bgra[..(dw * dh * 4) as usize]);
        return;
    }
    let (sw, sh, dw, dh) = (src.width as usize, src.height as usize, dw as usize, dh as usize);
    // 열마다 원본 x 범위를 미리 계산
    let xr: Vec<(usize, usize)> = (0..dw).map(|x| (x * sw / dw, ((x + 1) * sw / dw).max(x * sw / dw + 1).min(sw))).collect();
    for y in 0..dh {
        let y0 = y * sh / dh;
        let y1 = ((y + 1) * sh / dh).max(y0 + 1).min(sh);
        for (x, &(x0, x1)) in xr.iter().enumerate() {
            let mut acc = [0u32; 3];
            for yy in y0..y1 {
                let row = &src.bgra[(yy * sw + x0) * 4..(yy * sw + x1) * 4];
                for px in row.as_chunks::<4>().0 {
                    acc[0] += px[0] as u32;
                    acc[1] += px[1] as u32;
                    acc[2] += px[2] as u32;
                }
            }
            let n = ((y1 - y0) * (x1 - x0)) as u32;
            let o = (y * dw + x) * 4;
            for (dst, sum) in out.bgra[o..o + 3].iter_mut().zip(acc) {
                *dst = ((sum + n / 2) / n) as u8;
            }
            out.bgra[o + 3] = 255;
        }
    }
}

/// `sharp` 이면 색 정보를 줄이지 않는다(4:4:4). 기본(4:2:0)은 색을 1/4 로 줄여
/// 컬러 글자·아이콘 가장자리가 번진다. 용량은 30~50% 늘어난다.
pub fn jpeg(img: &RawFrame, quality: u8, sharp: bool) -> Result<Vec<u8>> {
    let w: u16 = img.width.try_into().context("이미지 폭이 너무 큼")?;
    let h: u16 = img.height.try_into().context("이미지 높이가 너무 큼")?;
    let mut out = Vec::with_capacity(img.bgra.len() / 8);
    let mut enc = jpeg_encoder::Encoder::new(&mut out, quality.clamp(10, 95));
    if sharp {
        enc.set_sampling_factor(jpeg_encoder::SamplingFactor::R_4_4_4);
    }
    enc.encode(&img.bgra, w, h, jpeg_encoder::ColorType::Bgra).context("JPEG 인코딩 실패")?;
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scale_and_encode() {
        let src = RawFrame { bgra: vec![128; 400 * 300 * 4], width: 400, height: 300 };
        let mut dst = RawFrame::default();
        downscale(&src, 50, &mut dst);
        assert_eq!((dst.width, dst.height), (200, 150));
        let j = jpeg(&dst, 70, false).unwrap();
        assert_eq!(&j[..2], &[0xFF, 0xD8], "JPEG SOI 마커");
        let j = jpeg(&dst, 90, true).unwrap();
        assert_eq!(&j[..2], &[0xFF, 0xD8], "JPEG SOI 마커 (4:4:4)");
        downscale(&src, 100, &mut dst);
        assert_eq!(dst.bgra.len(), src.bgra.len());
    }

    #[test]
    fn downscale_averages_area() {
        // 3x1 원본 [0, 90, 180] 을 1x1 로 줄이면 세 픽셀의 평균(90)이어야 한다.
        let mut bgra = Vec::new();
        for v in [0u8, 90, 180] {
            bgra.extend_from_slice(&[v, v, v, 255]);
        }
        let src = RawFrame { bgra, width: 3, height: 1 };
        let mut dst = RawFrame::default();
        downscale(&src, 34, &mut dst);
        assert_eq!((dst.width, dst.height), (1, 1));
        assert_eq!(&dst.bgra[..3], &[90, 90, 90]);
    }
}
