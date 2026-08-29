import { readdirSync, readFileSync, statSync } from 'node:fs';
import { extname, join } from 'node:path';
import { decode } from 'jpeg-js';
import { downscaleRgba } from './imageOps.mjs';
import {
  judgePhoto,
  statsFromRgba,
  BRIGHT_LUMA,
  DARK_LUMA,
  MIN_CONTRAST,
  MIN_SHARPNESS,
  PHOTO_PROBE_WIDTH,
  type PhotoStats,
  type PhotoVerdict,
} from '../src/core/photo';

/**
 * 사진 사전 필터의 오탐률을 잰다.
 *
 * 임계값은 합성 이미지로 방향만 잡은 값이다. 진짜 사진에서 **몇 %가 잘못
 * 걸리는지**는 재 본 적이 없고, 그 숫자를 모르면 임계값을 조정할 근거도 없다.
 *
 * 앱과 같은 코드(`judgePhoto`)를 부른다. 여기 결과가 곧 기기에서의 결과다.
 * 다만 축소는 앱이 ImageManipulator 로 하고 여기서는 JS 로 한다 —
 * 판정 폭(320px)을 맞추는 게 목적이라 알고리즘의 미세한 차이는 감수한다.
 *
 * 쓰는 법:
 *   npm run eval:photos -- --dir <사진 폴더>
 *   npm run eval:photos -- --good <통과해야 할 폴더> --bad <걸려야 할 폴더>
 *
 * JPEG 만 읽는다. 아이폰 HEIC 는 미리 변환해 주세요.
 */

const args = process.argv.slice(2);

function valueOf(flag: string): string | undefined {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : undefined;
}

function listJpegs(dir: string): string[] {
  return readdirSync(dir)
    .filter((name) => ['.jpg', '.jpeg'].includes(extname(name).toLowerCase()))
    .map((name) => join(dir, name))
    .filter((file) => statSync(file).isFile())
    .sort();
}

interface Measured {
  file: string;
  stats: PhotoStats;
  verdict: PhotoVerdict;
}

function measure(file: string): Measured | null {
  try {
    const image = decode(readFileSync(file), {
      useTArray: true,
      formatAsRGBA: true,
      maxMemoryUsageInMB: 512,
    });
    const small = downscaleRgba(image.data, image.width, image.height, PHOTO_PROBE_WIDTH);
    const stats = statsFromRgba(small.data, small.width, small.height);
    return { file, stats, verdict: judgePhoto(stats) };
  } catch (error) {
    console.warn(`  건너뜀: ${file} (${(error as Error).message})`);
    return null;
  }
}

function percentile(values: number[], p: number): number {
  if (values.length === 0) return NaN;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor((sorted.length - 1) * p))];
}

function describe(label: string, values: number[]): string {
  return `${label.padEnd(10)} 최소 ${percentile(values, 0).toFixed(1).padStart(7)} | 5% ${percentile(values, 0.05).toFixed(1).padStart(7)} | 중앙 ${percentile(values, 0.5).toFixed(1).padStart(7)} | 95% ${percentile(values, 0.95).toFixed(1).padStart(7)} | 최대 ${percentile(values, 1).toFixed(1).padStart(7)}`;
}

function report(name: string, measured: Measured[]): void {
  console.log(`\n[${name}] ${measured.length}장`);
  if (measured.length === 0) return;

  console.log(
    describe(
      '밝기',
      measured.map((m) => m.stats.meanLuma),
    ),
  );
  console.log(
    describe(
      '대비',
      measured.map((m) => m.stats.contrast),
    ),
  );
  console.log(
    describe(
      '선명도',
      measured.map((m) => m.stats.sharpness),
    ),
  );

  const counts = new Map<string, number>();
  for (const item of measured) {
    const key = item.verdict.ok ? 'ok' : item.verdict.reason;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const share = (n: number) => `${((n / measured.length) * 100).toFixed(1)}%`;
  console.log(`  판정: ${[...counts.entries()].map(([key, n]) => `${key} ${n} (${share(n)})`).join(', ')}`);

  const rejected = measured.filter((m) => !m.verdict.ok);
  if (rejected.length > 0) {
    console.log('  걸린 사진:');
    for (const item of rejected.slice(0, 20)) {
      const reason = item.verdict.ok ? '' : item.verdict.reason;
      console.log(
        `    ${reason.padEnd(12)} 밝기 ${item.stats.meanLuma.toFixed(1).padStart(6)} 대비 ${item.stats.contrast.toFixed(1).padStart(6)} 선명도 ${item.stats.sharpness.toFixed(2).padStart(7)}  ${item.file}`,
      );
    }
    if (rejected.length > 20) console.log(`    … 그 외 ${rejected.length - 20}장`);
  }
}

/** 통과해야 할 사진들의 분포에서 임계값 후보를 제안한다 */
function suggest(good: Measured[]): void {
  if (good.length < 10) {
    console.log('\n임계값 제안: 표본이 10장 미만이라 생략합니다.');
    return;
  }
  console.log('\n임계값 제안 (통과해야 할 사진의 하위 5% 지점 — 여기를 넘지 않게 잡으면 오탐 5% 이하)');
  console.log(
    `  DARK_LUMA      지금 ${DARK_LUMA}\t제안 ${percentile(
      good.map((m) => m.stats.meanLuma),
      0.05,
    ).toFixed(1)} 아래`,
  );
  console.log(
    `  BRIGHT_LUMA    지금 ${BRIGHT_LUMA}\t제안 ${percentile(
      good.map((m) => m.stats.meanLuma),
      0.95,
    ).toFixed(1)} 위`,
  );
  console.log(
    `  MIN_CONTRAST   지금 ${MIN_CONTRAST}\t제안 ${percentile(
      good.map((m) => m.stats.contrast),
      0.05,
    ).toFixed(1)} 아래`,
  );
  console.log(
    `  MIN_SHARPNESS  지금 ${MIN_SHARPNESS}\t제안 ${percentile(
      good.map((m) => m.stats.sharpness),
      0.05,
    ).toFixed(2)} 아래`,
  );
  console.log('  ⚠️ 제안값을 그대로 넣지 마세요. 표본이 편향돼 있으면 임계값도 같이 편향됩니다.');
}

function main(): void {
  const dir = valueOf('--dir');
  const goodDir = valueOf('--good');
  const badDir = valueOf('--bad');

  if (!dir && !goodDir && !badDir) {
    console.log(`사진 사전 필터 오탐률 측정

  npm run eval:photos -- --dir <폴더>              한 폴더의 분포와 판정만 봅니다
  npm run eval:photos -- --good <폴더> --bad <폴더>  오탐률·미탐률을 계산합니다

  --good : 반려동물이 제대로 찍힌, **통과해야 할** 사진들
  --bad  : 캄캄하거나 흔들린, **걸려야 할** 사진들

JPEG 만 읽습니다. 최소 30장씩 모아야 숫자를 읽을 만합니다.`);
    return;
  }

  const load = (path: string) =>
    listJpegs(path)
      .map(measure)
      .filter((m): m is Measured => m !== null);

  if (dir) report(dir, load(dir));

  if (goodDir) {
    const good = load(goodDir);
    report(`통과해야 할 사진 — ${goodDir}`, good);

    const falsePositives = good.filter((m) => !m.verdict.ok).length;
    console.log(
      `\n▶ 오탐률(멀쩡한 사진을 막은 비율): ${good.length ? ((falsePositives / good.length) * 100).toFixed(1) : '—'}%  (${falsePositives}/${good.length})`,
    );
    console.log('  이 값이 5% 를 넘으면 임계값을 낮춰야 합니다 — 좋은 사진을 막는 쪽이 더 나쁩니다.');
    suggest(good);
  }

  if (badDir) {
    const bad = load(badDir);
    report(`걸려야 할 사진 — ${badDir}`, bad);

    const caught = bad.filter((m) => !m.verdict.ok).length;
    console.log(
      `\n▶ 검출률(실패한 사진을 막은 비율): ${bad.length ? ((caught / bad.length) * 100).toFixed(1) : '—'}%  (${caught}/${bad.length})`,
    );
    console.log('  낮아도 큰 문제는 아닙니다. 놓친 사진은 그냥 분석될 뿐입니다.');
  }
}

main();
