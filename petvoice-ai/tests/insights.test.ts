import { describe, expect, it } from 'vitest';
import {
  METRIC_WINDOW,
  MIN_SAMPLES,
  pushAttempt,
  summarizeFeedback,
  summarizeQuality,
  type AnalysisAttempt,
} from '../src/core/insights';
import type { AnalysisEntry, EmotionKey } from '../src/core/types';

function entry(
  id: string,
  emotion: EmotionKey,
  feedback?: 'up' | 'down',
  extra: Partial<AnalysisEntry> = {},
): AnalysisEntry {
  return {
    id,
    petId: 'p1',
    createdAt: 1000,
    mediaKind: 'audio',
    context: '',
    result: {
      petVoiceMessage: '',
      primaryEmotion: emotion,
      emotionScores: { [emotion]: 100 },
      behaviorAnalysis: '',
      actionGuide: '',
    },
    health: { level: 'none', reasons: [], tips: [] },
    ...(feedback ? { feedback } : {}),
    ...extra,
  };
}

describe('피드백 집계', () => {
  it('평가가 없으면 비율은 null 이다 — 0% 로 보이면 안 된다', () => {
    const summary = summarizeFeedback([entry('a', 'happy'), entry('b', 'anxiety')]);
    expect(summary.analyses).toBe(2);
    expect(summary.rated).toBe(0);
    expect(summary.rate).toBeNull();
  });

  it('전체 정확도를 센다', () => {
    const summary = summarizeFeedback([
      entry('a', 'happy', 'up'),
      entry('b', 'happy', 'up'),
      entry('c', 'happy', 'down'),
      entry('d', 'happy'),
    ]);
    expect(summary.rated).toBe(3);
    expect(summary.up).toBe(2);
    expect(summary.down).toBe(1);
    expect(summary.rate).toBe(67);
  });

  it('감정별로 나눈다', () => {
    const summary = summarizeFeedback([
      entry('a', 'happy', 'up'),
      entry('b', 'anxiety', 'down'),
      entry('c', 'anxiety', 'down'),
    ]);
    const anxiety = summary.byEmotion.find((b) => b.id === 'emotion.anxiety');
    expect(anxiety).toMatchObject({ down: 2, up: 0, rate: 0 });
  });

  it('정확도가 낮은 것부터 보여 준다 — 고칠 곳이 위에 와야 한다', () => {
    const rows = [
      ...Array.from({ length: MIN_SAMPLES }, (_, i) => entry(`h${i}`, 'happy', 'up')),
      ...Array.from({ length: MIN_SAMPLES }, (_, i) => entry(`a${i}`, 'anxiety', i === 0 ? 'up' : 'down')),
    ];
    expect(summarizeFeedback(rows).byEmotion[0].id).toBe('emotion.anxiety');
  });

  it('표본이 적으면 표시만 하고 위로 올리지 않는다', () => {
    const rows = [
      ...Array.from({ length: MIN_SAMPLES }, (_, i) => entry(`h${i}`, 'happy', i === 0 ? 'down' : 'up')),
      entry('p', 'pain', 'down'),
    ];
    const buckets = summarizeFeedback(rows).byEmotion;
    // pain 은 0% 지만 1건뿐이다 — 80% 인 happy 보다 뒤에 온다
    expect(buckets[0].id).toBe('emotion.happy');
    expect(buckets[0].enough).toBe(true);
    expect(buckets[1]).toMatchObject({ id: 'emotion.pain', enough: false, rate: 0 });
  });

  it('프리셋으로 고른 상황만 묶는다', () => {
    const rows = [
      entry('a', 'anxiety', 'down', { contextKey: 'context.beforeLeaving' }),
      entry('b', 'anxiety', 'up', { contextKey: 'context.beforeLeaving' }),
      entry('c', 'happy', 'up', { context: '직접 쓴 상황' }),
    ];
    const summary = summarizeFeedback(rows);
    expect(summary.byContext).toHaveLength(1);
    expect(summary.byContext[0]).toMatchObject({ id: 'context.beforeLeaving', total: 2, rate: 50 });
  });

  it('소리와 사진을 나눠 본다 — 어느 쪽이 더 틀리는지가 핵심 질문이다', () => {
    const rows = [
      entry('a', 'happy', 'up'),
      entry('b', 'happy', 'down', { mediaKind: 'image' }),
      entry('c', 'happy', 'down', { mediaKind: 'image' }),
    ];
    const summary = summarizeFeedback(rows);
    expect(summary.byMedia.find((b) => b.id === 'media.image')).toMatchObject({ rate: 0, total: 2 });
    expect(summary.byMedia.find((b) => b.id === 'media.audio')).toMatchObject({ rate: 100, total: 1 });
  });
});

describe('품질 지표', () => {
  const attempt = (ok: boolean, ms: number, code?: string): AnalysisAttempt => ({ at: 0, ok, ms, code });

  it('아무것도 없으면 null 로 답한다', () => {
    expect(summarizeQuality([])).toEqual({
      attempts: 0,
      failures: 0,
      failureRate: null,
      medianMs: null,
      topCodes: [],
    });
  });

  it('실패율과 실패 사유를 센다', () => {
    const summary = summarizeQuality([
      attempt(true, 1000),
      attempt(false, 45000, 'timeout'),
      attempt(false, 200, 'network'),
      attempt(false, 45000, 'timeout'),
    ]);
    expect(summary.failureRate).toBe(75);
    expect(summary.topCodes[0]).toEqual({ code: 'timeout', count: 2 });
  });

  it('평균이 아니라 중앙값을 쓴다 — 45초 타임아웃 하나에 끌려가지 않게', () => {
    const summary = summarizeQuality([attempt(true, 900), attempt(true, 1000), attempt(true, 44000)]);
    expect(summary.medianMs).toBe(1000);
  });

  it('실패만 있으면 소요 시간은 null', () => {
    expect(summarizeQuality([attempt(false, 100, 'network')]).medianMs).toBeNull();
  });

  it('최근 것만 들고 있는다', () => {
    let history: AnalysisAttempt[] = [];
    for (let i = 0; i < METRIC_WINDOW + 10; i += 1) {
      history = pushAttempt(history, { at: i, ok: true, ms: i });
    }
    expect(history).toHaveLength(METRIC_WINDOW);
    expect(history[0].at).toBe(METRIC_WINDOW + 9);
  });
});
