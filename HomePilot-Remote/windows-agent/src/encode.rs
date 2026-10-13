//! 화면 축소 + JPEG 인코딩.
//!
//! MVP 는 프레임마다 JPEG 를 보낸다(구현 단순·디코딩 호환성 높음).
//! 대역폭/지연 개선을 위한 H.264 하드웨어 인코딩은 후속 단계 과제로 문서화되어 있다.

use crate::platform::RawFrame;
use anyhow::{Context, Result};

/// 축소 비율(%)을 적용한 BGRA 이미지를 만든다. 2x2 평균으로 글자가 덜 깨지게 한다.
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
    let sw = src.width as usize;
    let sh = src.height as usize;
    for y in 0..dh as usize {
        let sy = (y * sh / dh as usize).min(sh - 1);
        let sy2 = (sy + 1).min(sh - 1);
        for x in 0..dw as usize {
            let sx = (x * sw / dw as usize).min(sw - 1);
            let sx2 = (sx + 1).min(sw - 1);
            let o = (y * dw as usize + x) * 4;
            for c in 0..3 {
                let p = |xx: usize, yy: usize| src.bgra[(yy * sw + xx) * 4 + c] as u32;
                out.bgra[o + c] = ((p(sx, sy) + p(sx2, sy) + p(sx, sy2) + p(sx2, sy2) + 2) / 4) as u8;
            }
            out.bgra[o + 3] = 255;
        }
    }
}

pub fn jpeg(img: &RawFrame, quality: u8) -> Result<Vec<u8>> {
    let w: u16 = img.width.try_into().context("이미지 폭이 너무 큼")?;
    let h: u16 = img.height.try_into().context("이미지 높이가 너무 큼")?;
    let mut out = Vec::with_capacity(img.bgra.len() / 8);
    let enc = jpeg_encoder::Encoder::new(&mut out, quality.clamp(10, 95));
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
        let j = jpeg(&dst, 70).unwrap();
        assert_eq!(&j[..2], &[0xFF, 0xD8], "JPEG SOI 마커");
        downscale(&src, 100, &mut dst);
        assert_eq!(dst.bgra.len(), src.bgra.len());
    }
}
