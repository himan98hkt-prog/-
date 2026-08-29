import { encode } from 'jpeg-js';
import { describe, expect, it } from 'vitest';
import {
  judgeJpegBase64,
  BRIGHT_LUMA,
  DARK_LUMA,
  judgePhoto,
  MIN_CONTRAST,
  MIN_SHARPNESS,
  PHOTO_PROBE_WIDTH,
  statsFromRgba,
} from '../src/core/photo';

/**
 * 합성 이미지로 임계값을 확인한다.
 *
 * 진짜 반려동물 사진이 아니라는 건 분명히 해 둔다 — 이 테스트가 보장하는 건
 * "명백한 실패는 걸리고, 질감이 있는 화면은 통과한다"까지다.
 * 진짜 사진에서의 오탐률은 실기기 테스트에서 재야 한다.
 */

const W = PHOTO_PROBE_WIDTH;
const H = 400;

function image(fn: (x: number, y: number) => number): Uint8Array {
  const buf = new Uint8Array(W * H * 4);
  for (let y = 0; y < H; y += 1) {
    for (let x = 0; x < W; x += 1) {
      const v = Math.max(0, Math.min(255, fn(x, y)));
      const o = (y * W + x) * 4;
      buf[o] = v;
      buf[o + 1] = v;
      buf[o + 2] = v;
      buf[o + 3] = 255;
    }
  }
  return buf;
}

function blur(src: Uint8Array, radius: number): Uint8Array {
  const out = new Uint8Array(src.length);
  for (let y = 0; y < H; y += 1) {
    for (let x = 0; x < W; x += 1) {
      let sum = 0;
      let n = 0;
      for (let dy = -radius; dy <= radius; dy += 1) {
        for (let dx = -radius; dx <= radius; dx += 1) {
          const nx = x + dx;
          const ny = y + dy;
          if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
          sum += src[(ny * W + nx) * 4];
          n += 1;
        }
      }
      const o = (y * W + x) * 4;
      const v = sum / n;
      out[o] = v;
      out[o + 1] = v;
      out[o + 2] = v;
      out[o + 3] = 255;
    }
  }
  return out;
}

let seed = 42;
function rnd(): number {
  seed = (seed * 1103515245 + 12345) % 2147483648;
  return seed / 2147483648;
}

/** 저주파 무늬 + 잔노이즈 — 실제 사진의 질감에 가장 가까운 합성 */
const textured = () => image((x, y) => 120 + 50 * Math.sin(x / 30) * Math.cos(y / 40) + rnd() * 18 - 9);

const verdict = (buf: Uint8Array) => judgePhoto(statsFromRgba(buf, W, H));

describe('명백한 실패를 되돌린다', () => {
  it('캄캄한 사진', () => {
    expect(verdict(image(() => 10 + rnd() * 6))).toEqual({ ok: false, reason: 'tooDark' });
  });

  it('하얗게 날아간 사진', () => {
    expect(verdict(image(() => 250 + rnd() * 5))).toEqual({ ok: false, reason: 'tooBright' });
  });

  it('아무것도 없는 벽', () => {
    expect(verdict(image(() => 128 + rnd() * 4 - 2))).toEqual({ ok: false, reason: 'featureless' });
  });

  it('심하게 흔들린 사진', () => {
    expect(verdict(blur(textured(), 4))).toEqual({ ok: false, reason: 'blurry' });
  });
});

describe('멀쩡한 사진은 통과시킨다', () => {
  it('질감이 있는 화면', () => {
    expect(verdict(textured())).toEqual({ ok: true });
  });

  it('어두운 실내라도 형체가 보이면 보낸다', () => {
    // 밤에 찍은 사진을 막으면 정작 쓰고 싶을 때 못 쓴다
    expect(verdict(image((x) => 45 + 18 * Math.sin(x / 25) + rnd() * 12 - 6))).toEqual({ ok: true });
  });

  it('살짝 초점이 나간 정도는 통과한다', () => {
    const soft = blur(
      image((x, y) => ((Math.floor(x / 16) + Math.floor(y / 16)) % 2 ? 210 : 40)),
      3,
    );
    expect(verdict(soft)).toEqual({ ok: true });
  });
});

describe('경계와 방어', () => {
  it('밝기 경계 바로 위아래', () => {
    const base = { contrast: 30, sharpness: 30 };
    expect(judgePhoto({ ...base, meanLuma: DARK_LUMA })).toEqual({ ok: true });
    expect(judgePhoto({ ...base, meanLuma: DARK_LUMA - 0.1 })).toEqual({
      ok: false,
      reason: 'tooDark',
    });
    expect(judgePhoto({ ...base, meanLuma: BRIGHT_LUMA })).toEqual({ ok: true });
    expect(judgePhoto({ ...base, meanLuma: BRIGHT_LUMA + 0.1 })).toEqual({
      ok: false,
      reason: 'tooBright',
    });
  });

  it('대비·선명도 경계', () => {
    expect(judgePhoto({ meanLuma: 128, contrast: MIN_CONTRAST, sharpness: MIN_SHARPNESS })).toEqual({
      ok: true,
    });
    expect(judgePhoto({ meanLuma: 128, contrast: MIN_CONTRAST - 0.1, sharpness: 30 })).toEqual({
      ok: false,
      reason: 'featureless',
    });
    expect(judgePhoto({ meanLuma: 128, contrast: 30, sharpness: MIN_SHARPNESS - 0.1 })).toEqual({
      ok: false,
      reason: 'blurry',
    });
  });

  it('어두움이 흔들림보다 먼저 나온다 — 다시 찍기 쉬운 안내부터', () => {
    expect(judgePhoto({ meanLuma: 5, contrast: 0, sharpness: 0 })).toEqual({
      ok: false,
      reason: 'tooDark',
    });
  });

  it('픽셀을 못 읽으면 막지 않는다', () => {
    // 막는 것보다 분석하는 편이 낫다 (녹음 쪽 미터링 없는 기기와 같은 원칙)
    expect(judgePhoto(statsFromRgba(new Uint8Array(4), W, H))).toEqual({ ok: true });
    expect(judgePhoto(statsFromRgba(new Uint8Array(0), 0, 0))).toEqual({ ok: true });
  });

  it('너무 작은 이미지는 선명도를 재지 않는다', () => {
    const tiny = new Uint8Array(2 * 2 * 4).fill(128);
    expect(statsFromRgba(tiny, 2, 2).sharpness).toBe(255);
  });
});

describe('JPEG 경로 전체', () => {
  /** 실제 앱과 같은 순서: JPEG 인코딩 → base64 → 디코딩 → 판정 */
  function asJpegBase64(rgba: Uint8Array, quality = 80): string {
    const jpg = encode({ data: rgba, width: W, height: H }, quality);
    return Buffer.from(jpg.data).toString('base64');
  }

  it('질감이 있는 사진은 JPEG 을 거쳐도 통과한다', () => {
    expect(judgeJpegBase64(asJpegBase64(textured()))).toEqual({ ok: true });
  });

  it('캄캄한 사진은 JPEG 을 거쳐도 걸린다', () => {
    expect(judgeJpegBase64(asJpegBase64(image(() => 8)))).toEqual({ ok: false, reason: 'tooDark' });
  });

  it('압축 품질을 낮춰도 판정이 뒤집히지 않는다', () => {
    // JPEG 블록 잡음은 선명도를 올리는 방향이라, 낮은 품질에서도 통과 쪽이 유지돼야 한다
    expect(judgeJpegBase64(asJpegBase64(textured(), 40))).toEqual({ ok: true });
  });

  it('JPEG 이 아닌 값을 넣어도 막지 않는다', () => {
    expect(judgeJpegBase64('this-is-not-an-image')).toEqual({ ok: true });
    expect(judgeJpegBase64('')).toEqual({ ok: true });
  });
});
