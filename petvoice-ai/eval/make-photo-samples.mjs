import { encode } from 'jpeg-js';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

/**
 * 사진 측정 도구를 시험해 볼 합성 표본을 만든다.
 *
 * **진짜 사진의 대용이 아니다.** 오탐률은 진짜 사진으로만 잴 수 있다.
 * 이건 도구 자체가 도는지(폴더를 읽고, 축소하고, 판정하고, 숫자를 내는지)
 * 사진 없이 확인하기 위한 것이다. 대조군 오디오(`make-controls.mjs`)와 같은 역할이다.
 *
 *   node eval/make-photo-samples.mjs
 *   npm run eval:photos -- --good eval/dataset/photos/good --bad eval/dataset/photos/bad
 */

const W = 960;
const H = 1200;
const OUT = 'eval/dataset/photos';

let seed = 7;
function rnd() {
  seed = (seed * 1103515245 + 12345) % 2147483648;
  return seed / 2147483648;
}

function image(fn) {
  const data = new Uint8Array(W * H * 4);
  for (let y = 0; y < H; y += 1) {
    for (let x = 0; x < W; x += 1) {
      const [r, g, b] = fn(x, y);
      const o = (y * W + x) * 4;
      data[o] = Math.max(0, Math.min(255, r));
      data[o + 1] = Math.max(0, Math.min(255, g));
      data[o + 2] = Math.max(0, Math.min(255, b));
      data[o + 3] = 255;
    }
  }
  return data;
}

function blur(src, radius) {
  const out = new Uint8Array(src.length);
  for (let y = 0; y < H; y += 1) {
    for (let x = 0; x < W; x += 1) {
      let r = 0;
      let g = 0;
      let b = 0;
      let n = 0;
      for (let dy = -radius; dy <= radius; dy += 1) {
        for (let dx = -radius; dx <= radius; dx += 1) {
          const nx = x + dx;
          const ny = y + dy;
          if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
          const o = (ny * W + nx) * 4;
          r += src[o];
          g += src[o + 1];
          b += src[o + 2];
          n += 1;
        }
      }
      const o = (y * W + x) * 4;
      out[o] = r / n;
      out[o + 1] = g / n;
      out[o + 2] = b / n;
      out[o + 3] = 255;
    }
  }
  return out;
}

/** 털·풀 같은 잔결이 있는 화면 — 실제 반려동물 사진의 질감에 가장 가깝다 */
function furry(base, amplitude) {
  return image((x, y) => {
    const shape = amplitude * Math.sin(x / 40) * Math.cos(y / 55);
    const fur = 14 * Math.sin(x / 2.5 + Math.sin(y / 9)) + rnd() * 16 - 8;
    const v = base + shape + fur;
    return [v * 1.05, v, v * 0.9];
  });
}

function save(dir, name, data, quality = 85) {
  mkdirSync(dir, { recursive: true });
  const jpg = encode({ data, width: W, height: H }, quality);
  writeFileSync(join(dir, `${name}.jpg`), jpg.data);
}

const good = join(OUT, 'good');
const bad = join(OUT, 'bad');

// 통과해야 할 것들 — 밝기와 질감이 다양하게
save(good, 'daylight', furry(150, 45));
save(good, 'indoor', furry(105, 35));
save(good, 'dim-room', furry(58, 22));
save(good, 'bright-window', furry(200, 30));
save(good, 'low-contrast-but-textured', furry(130, 12));
save(good, 'slightly-soft', blur(furry(140, 40), 1));
save(good, 'low-quality-jpeg', furry(135, 38), 35);

// 걸려야 할 것들
save(
  bad,
  'pitch-black',
  image(() => [7 + rnd() * 4, 7 + rnd() * 4, 7 + rnd() * 4]),
);
save(
  bad,
  'blown-out',
  image(() => [251 + rnd() * 4, 251 + rnd() * 4, 251 + rnd() * 4]),
);
save(
  bad,
  'blank-wall',
  image(() => [131 + rnd() * 3, 128 + rnd() * 3, 124 + rnd() * 3]),
);
save(bad, 'motion-blur', blur(furry(140, 45), 12));
save(bad, 'out-of-focus', blur(furry(120, 40), 9));

console.log(`합성 표본을 만들었습니다: ${OUT}/good (7장), ${OUT}/bad (5장)`);
console.log('진짜 사진의 대용이 아닙니다 — 도구가 도는지 확인하는 용도입니다.');
