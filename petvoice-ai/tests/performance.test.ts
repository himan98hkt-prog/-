import { describe, expect, it } from 'vitest';
import { buildWeeklyDigest, monthGrid, weeklyStats } from '../src/core/diary';
import { assessHistoryRisk } from '../src/core/health';
import { summarizeFeedback } from '../src/core/insights';
import { quotaState } from '../src/core/quota';
import { MEMORY_LIMIT } from '../src/data/entries';
import type { AnalysisEntry, EmotionKey } from '../src/core/types';

/**
 * 기록이 가득 찼을 때의 계산 비용.
 *
 * 보관 정책(N6)으로 상한은 생겼지만, 메모리에 올라오는 최대치(2,000건)에서
 * 화면이 실제로 도는지는 재 본 적이 없었다.
 *
 * **여기 숫자는 성능 기준이 아니라 회귀 감지선이다.** CI 머신은 들쭉날쭉하고
 * 실제 기기는 더 느리므로, 지금 값의 10배쯤을 상한으로 잡았다.
 * 목적은 "몇 ms 인가"가 아니라 "누가 전체 순회를 다시 집어넣었는가"를 잡는 것이다.
 *
 * (예: monthGrid 는 한 달을 그리려고 기록 전체를 요약하고 있었다. 5.4ms → 0.7ms)
 */

const EMOTIONS: EmotionKey[] = ['happy', 'playful', 'anxiety', 'pain', 'relaxed', 'fear', 'alert'];
const DAY = 24 * 60 * 60 * 1000;
const NOW = new Date(2026, 7, 29, 12).getTime();

/** 하루 3회씩 약 2년치 — 메모리 거울이 담을 수 있는 최대 */
const entries: AnalysisEntry[] = Array.from({ length: MEMORY_LIMIT }, (_, i) => {
  const emotion = EMOTIONS[i % EMOTIONS.length];
  return {
    id: `e${i}`,
    petId: 'p1',
    createdAt: NOW - i * (DAY / 3),
    mediaKind: i % 3 === 0 ? 'image' : 'audio',
    context: `상황 ${i % 10}`,
    contextKey: 'context.beforeLeaving',
    result: {
      petVoiceMessage: 'x',
      primaryEmotion: emotion,
      emotionScores: { [emotion]: 60, happy: 30, sad: 10 },
      behaviorAnalysis: 'x',
      actionGuide: 'x',
    },
    health: { level: i % 17 === 0 ? 'vet' : i % 5 === 0 ? 'watch' : 'none', reasons: [], tips: [] },
    ...(i % 4 === 0 ? { feedback: 'up' as const } : {}),
    ...(i % 7 === 0 ? { feedback: 'down' as const } : {}),
  };
});

/** 중앙값으로 잰다 — 한 번의 GC 가 판정을 뒤집지 않게 */
function medianMs(fn: () => unknown, runs = 15): number {
  fn(); // 워밍업
  const samples: number[] = [];
  for (let i = 0; i < runs; i += 1) {
    const start = performance.now();
    fn();
    samples.push(performance.now() - start);
  }
  samples.sort((a, b) => a - b);
  return samples[Math.floor(samples.length / 2)];
}

describe(`기록 ${MEMORY_LIMIT}건에서의 계산 비용`, () => {
  it('기록이 실제로 가득 차 있다', () => {
    expect(entries).toHaveLength(MEMORY_LIMIT);
    expect(entries.filter((e) => e.feedback).length).toBeGreaterThan(500);
  });

  it.each<[string, () => unknown, number]>([
    // 달을 넘길 때마다 도는 계산. 여기가 가장 위험하다.
    ['monthGrid', () => monthGrid(2026, 8, entries, NOW), 8],
    ['weeklyStats', () => weeklyStats(entries, NOW), 3],
    ['assessHistoryRisk', () => assessHistoryRisk(entries), 3],
    ['summarizeFeedback', () => summarizeFeedback(entries), 8],
    [
      'quotaState',
      () =>
        quotaState(
          entries.map((e) => e.createdAt),
          { pro: false },
          NOW,
        ),
      3,
    ],
    ['buildWeeklyDigest', () => buildWeeklyDigest(entries, (key) => key, NOW), 3],
  ])('%s 이 %s번째 인자 ms 안에 끝난다', (_name, fn, budgetMs) => {
    expect(medianMs(fn)).toBeLessThan(budgetMs);
  });

  it('monthGrid 는 그 달 밖 기록을 훑지 않는다', () => {
    // 시간이 아니라 **동작**으로 못 박는다. 기록을 100배로 늘려도
    // 같은 달의 기록 수가 같으면 비용이 비례해 늘면 안 된다.
    const august = entries.filter((e) => new Date(e.createdAt).getMonth() === 7);
    const onlyAugust = medianMs(() => monthGrid(2026, 8, august, NOW));
    const withEverything = medianMs(() => monthGrid(2026, 8, entries, NOW));

    // 전체를 요약하던 시절에는 이 비가 10배를 넘었다
    expect(withEverything).toBeLessThan(Math.max(onlyAugust, 0.05) * 10 + 1);
  });
});
