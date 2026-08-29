import { decode } from 'jpeg-js';
import { decodeBase64 } from './base64';

/**
 * 사진 사전 필터.
 *
 * 소리에는 이미 무음 차단(P1)이 걸려 있었는데 사진에는 없었다.
 * 캄캄한 사진이나 흔들린 사진을 보내도 모델은 **무언가를 답한다** —
 * 그게 문제다. 근거 없는 결과가 나오고, 무료 3회 중 하나가 사라진다.
 *
 * 그래서 보내기 전에 밝기·대비·선명도를 재서 명백한 실패만 되돌린다.
 * 판정은 여기(순수 함수)에서 하고, 픽셀을 꺼내 오는 일은 화면 쪽이 한다.
 *
 * ⚠️ 임계값은 데이터가 아니라 **설계 시점의 판단**이다. 이상 징후 임계값과 같다.
 * 방향은 정해 뒀다 — 좋은 사진을 막는 쪽(거짓 양성)이 애매한 사진을 보내는 쪽보다
 * 훨씬 나쁘다. 그래서 전부 보수적으로, "누가 봐도 실패한 사진"만 걸리게 잡았다.
 */

/**
 * 판정에 쓰는 썸네일 가로 폭. 이 값이 바뀌면 아래 임계값도 다시 잡아야 한다.
 *
 * 320 / 480 / 640 / 800 을 재 보고 320 을 골랐다 (`npm run eval:photos` 의 측정).
 * 축소는 흔들림을 가리는 방향이라 폭이 클수록 유리할 것 같지만, 실제로는
 * 반대였다 — 폭이 커지면 **멀쩡한 사진의 선명도도 같이 떨어져** 둘 사이 간격이
 * 좁아진다. 320px 에서 질감 있는 화면 11~12, 흔들린 화면 2 안팎으로 가장 벌어졌다.
 */
export const PHOTO_PROBE_WIDTH = 320;

export interface PhotoStats {
  /** 평균 밝기 0~255 */
  meanLuma: number;
  /** 밝기의 표준편차 — 낮으면 벽·바닥처럼 아무것도 없는 화면 */
  contrast: number;
  /** 라플라시안 절댓값의 평균 — 낮으면 초점이 안 맞았거나 흔들린 사진 */
  sharpness: number;
}

export type PhotoVerdict =
  { ok: true } | { ok: false; reason: 'tooDark' | 'tooBright' | 'featureless' | 'blurry' };

/** 이보다 어두우면 형체를 알아볼 수 없다 */
export const DARK_LUMA = 28;
/** 이보다 밝으면 하얗게 날아갔다 */
export const BRIGHT_LUMA = 244;
/** 대비가 이보다 낮으면 피사체가 없다고 본다 */
export const MIN_CONTRAST = 8;
/**
 * 선명도 하한.
 *
 * 처음에는 1.6 이었는데, 측정 도구를 만들고 나서 그 값이 **거의 아무것도 막지
 * 못한다**는 걸 알았다. 원본 해상도에서 크게 흔들린 사진도 320px 로 줄이면
 * 1.96~2.13 이 나와 아슬아슬하게 통과했다. 합성 이미지를 판정 해상도에서
 * 직접 흐리게 만들어 시험했던 탓에, 축소가 흔들림을 가린다는 걸 놓쳤다.
 *
 * 측정된 흔들림 상한(2.13) 바로 위인 2.5 로 올렸다. 같은 측정에서 질감이 있는
 * 화면은 11 이상이라 여유는 충분하다. 다만 **합성 이미지 기준**이라는 걸 잊으면
 * 안 된다 — 매끈한 배경의 진짜 사진은 더 낮게 나올 수 있다.
 * 진짜 사진으로 다시 잡는 것이 `npm run eval:photos` 의 목적이다.
 */
export const MIN_SHARPNESS = 2.5;

/**
 * RGBA 픽셀에서 통계를 뽑는다.
 *
 * 휘도는 Rec.601 가중치를 쓴다. 사람 눈이 초록에 가장 민감해서,
 * 단순 평균을 쓰면 초록 잔디밭이 실제보다 어둡게 계산된다.
 */
export function statsFromRgba(rgba: ArrayLike<number>, width: number, height: number): PhotoStats {
  const count = width * height;
  if (count <= 0 || rgba.length < count * 4) {
    // 못 재면 통과시킨다 — 막는 것보다 분석하는 편이 낫다 (녹음 쪽과 같은 원칙)
    return { meanLuma: 128, contrast: 255, sharpness: 255 };
  }

  const luma = new Float32Array(count);
  let sum = 0;
  for (let i = 0; i < count; i += 1) {
    const o = i * 4;
    const value = 0.299 * rgba[o] + 0.587 * rgba[o + 1] + 0.114 * rgba[o + 2];
    luma[i] = value;
    sum += value;
  }
  const meanLuma = sum / count;

  let variance = 0;
  for (let i = 0; i < count; i += 1) {
    const d = luma[i] - meanLuma;
    variance += d * d;
  }
  const contrast = Math.sqrt(variance / count);

  return { meanLuma, contrast, sharpness: laplacianEnergy(luma, width, height) };
}

/**
 * 4방향 라플라시안의 절댓값 평균.
 *
 * 분산 대신 절댓값 평균을 쓴다 — 분산은 밝은 점 하나에 크게 흔들려서,
 * 흔들린 사진에 반사광 하나만 있어도 "선명하다"가 되어 버린다.
 */
function laplacianEnergy(luma: Float32Array, width: number, height: number): number {
  if (width < 3 || height < 3) return 255;

  let total = 0;
  let n = 0;
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const i = y * width + x;
      const value = luma[i - 1] + luma[i + 1] + luma[i - width] + luma[i + width] - 4 * luma[i];
      total += Math.abs(value);
      n += 1;
    }
  }
  return n > 0 ? total / n : 255;
}

/**
 * 이 사진을 분석에 보낼 만한지.
 *
 * 순서가 곧 안내 문구의 우선순위다. 캄캄한 사진은 선명도를 따질 것도 없이
 * 어둡다고 말해 주는 편이 사용자가 바로 다시 찍을 수 있다.
 */
export function judgePhoto(stats: PhotoStats): PhotoVerdict {
  if (stats.meanLuma < DARK_LUMA) return { ok: false, reason: 'tooDark' };
  if (stats.meanLuma > BRIGHT_LUMA) return { ok: false, reason: 'tooBright' };
  if (stats.contrast < MIN_CONTRAST) return { ok: false, reason: 'featureless' };
  // 매끈한 그라데이션(하늘·천장만 찍힌 사진)도 여기 걸린다. 이름은 '흔들림'이지만
  // 어느 쪽이든 사용자가 할 일은 같다 — 아이가 화면에 들어오게 다시 찍는 것.
  if (stats.sharpness < MIN_SHARPNESS) return { ok: false, reason: 'blurry' };
  return { ok: true };
}

/**
 * JPEG(base64) 한 장을 그대로 판정한다.
 *
 * 디코더는 순수 JS(jpeg-js)라 노드에서도 기기에서도 같은 코드가 돈다 —
 * 덕분에 "썸네일 → 판정" 경로 전체를 테스트로 돌려 볼 수 있다.
 * `useTArray` 를 켜야 Buffer 를 찾지 않는다 (React Native 에는 Buffer 가 없다).
 *
 * 어떤 이유로든 읽지 못하면 통과시킨다. 사전 필터가 분석을 막는 원인이 되면 안 된다.
 */
export function judgeJpegBase64(base64: string): PhotoVerdict {
  try {
    const bytes = decodeBase64(base64);
    if (bytes.length === 0) return { ok: true };

    const image = decode(bytes, {
      useTArray: true,
      formatAsRGBA: true,
      // 썸네일만 넣는 자리다. 원본이 잘못 들어와도 메모리를 물지 않게 막아 둔다.
      maxMemoryUsageInMB: 64,
    });
    return judgePhoto(statsFromRgba(image.data, image.width, image.height));
  } catch {
    return { ok: true };
  }
}
