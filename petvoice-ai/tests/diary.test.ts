import { describe, expect, it } from 'vitest';
import { buildWeeklyDigest, monthGrid, positiveRatio, summarizeDays, weeklyHeadline, weeklyStats } from '../src/core/diary';
import type { AnalysisEntry, EmotionScores, HealthLevel } from '../src/core/types';

const DAY = 24 * 60 * 60 * 1000;

function at(daysAgo: number, hour = 12): number {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  d.setHours(hour, 0, 0, 0);
  return d.getTime();
}

function entry(createdAt: number, scores: EmotionScores, level: HealthLevel = 'none', context = ''): AnalysisEntry {
  const primary = (Object.entries(scores).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))[0]?.[0] ?? 'happy') as never;
  return {
    id: `e${createdAt}${Math.random()}`,
    petId: 'p1',
    createdAt,
    mediaKind: 'audio',
    context,
    result: {
      petVoiceMessage: '메시지',
      primaryEmotion: primary,
      emotionScores: scores,
      behaviorAnalysis: '분석',
      actionGuide: '가이드',
    },
    health: { level, reasons: [], tips: [] },
  };
}

describe('positiveRatio', () => {
  it('긍정 감정 비율을 계산한다', () => {
    expect(positiveRatio({ happy: 50, playful: 30, anxiety: 20 })).toBe(80);
    expect(positiveRatio({ anxiety: 100 })).toBe(0);
    expect(positiveRatio({})).toBe(0);
  });
});

describe('summarizeDays', () => {
  it('같은 날 기록을 묶고 대표 감정을 고른다', () => {
    const days = summarizeDays([
      entry(at(0, 9), { playful: 70, happy: 30 }),
      entry(at(0, 18), { anxiety: 60, sad: 40 }),
      entry(at(1), { happy: 100 }),
    ]);
    expect(days).toHaveLength(2);
    expect(days[0].count).toBe(2);
    // playful 70 vs anxiety 60 → 합산 1위가 대표
    expect(days[0].dominant).toBe('playful');
  });

  it('그 날 가장 높은 이상 징후 단계를 올린다', () => {
    const days = summarizeDays([
      entry(at(0, 9), { happy: 100 }, 'none'),
      entry(at(0, 20), { pain: 100 }, 'vet'),
    ]);
    expect(days[0].level).toBe('vet');
  });

  it('최신 날짜가 앞에 온다', () => {
    const days = summarizeDays([entry(at(3), { happy: 100 }), entry(at(0), { happy: 100 })]);
    expect(days[0].date).toBeGreaterThan(days[1].date);
  });
});

describe('monthGrid', () => {
  it('7일씩 끊어진 격자를 만든다', () => {
    const grid = monthGrid(2026, 8, []);
    expect(grid.every((week) => week.length === 7)).toBe(true);
    expect(grid.flat().filter((c) => c.day !== null)).toHaveLength(31);
  });

  it('2026년 8월 1일은 토요일이라 앞이 6칸 비어 있다', () => {
    const grid = monthGrid(2026, 8, []);
    expect(grid[0].filter((c) => c.day === null)).toHaveLength(6);
    expect(grid[0][6].day).toBe(1);
  });

  it('윤년 2월도 정확히 29일', () => {
    expect(monthGrid(2028, 2, []).flat().filter((c) => c.day !== null)).toHaveLength(29);
  });

  it('그 날의 요약이 셀에 붙는다', () => {
    const now = new Date();
    const grid = monthGrid(now.getFullYear(), now.getMonth() + 1, [entry(at(0), { playful: 100 })]);
    const todayCell = grid.flat().find((c) => c.isToday);
    expect(todayCell?.summary?.dominant).toBe('playful');
  });
});

describe('weeklyStats', () => {
  it('최근 7일만 집계한다', () => {
    const stats = weeklyStats([
      entry(at(0), { happy: 100 }),
      entry(at(3), { playful: 100 }),
      entry(at(9), { anxiety: 100 }),
    ]);
    expect(stats.count).toBe(2);
    expect(stats.activeDays).toBe(2);
  });

  it('대표 감정을 헤드라인 참조로 만든다', () => {
    const stats = weeklyStats([entry(at(1), { playful: 100 })]);
    expect(weeklyHeadline(stats)).toMatchObject({ key: 'diary.headline.noCompare' });
  });

  it('지난주 대비 긍정 비율 변화를 낸다', () => {
    const stats = weeklyStats([
      entry(at(1), { happy: 100 }),
      entry(at(9), { anxiety: 100 }),
    ]);
    expect(stats.positiveRatio).toBe(100);
    expect(stats.positiveDelta).toBe(100);
  });

  it('지난주 기록이 없으면 변화량은 null', () => {
    expect(weeklyStats([entry(at(1), { happy: 100 })]).positiveDelta).toBeNull();
  });

  it('가장 자주 기록한 상황을 뽑는다', () => {
    const stats = weeklyStats([
      entry(at(1), { happy: 100 }, 'none', '외출 직전'),
      entry(at(2), { happy: 100 }, 'none', '외출 직전'),
      entry(at(3), { happy: 100 }, 'none', '식사 후'),
    ]);
    expect(stats.topContext).toBe('외출 직전');
  });

  it('이상 징후 횟수를 센다', () => {
    const stats = weeklyStats([
      entry(at(1), { pain: 100 }, 'vet'),
      entry(at(2), { anxiety: 100 }, 'watch'),
      entry(at(3), { happy: 100 }, 'none'),
    ]);
    expect(stats.vetCount).toBe(1);
    expect(stats.watchCount).toBe(1);
  });

  it('기록이 없어도 안전하게 0을 낸다', () => {
    const stats = weeklyStats([]);
    expect(stats.count).toBe(0);
    expect(stats.dominant).toBeNull();
    expect(weeklyHeadline(stats)).toMatchObject({ key: 'diary.headline.empty' });
  });
});

describe('buildWeeklyDigest', () => {
  /** 감정 이름은 호출부가 번역해 넘긴다 */
  const labelOf = (key: string) => key.replace('emotion.', '');

  it('리포트 프롬프트에 넣을 요약을 만든다', () => {
    const digest = buildWeeklyDigest([
      entry(at(1), { anxiety: 70, sad: 30 }, 'watch', '외출 직전'),
      entry(at(2), { playful: 100 }, 'none', '산책 준비 중'),
    ], labelOf);
    expect(digest).toContain('총 분석 2회');
    expect(digest).toContain('외출 직전');
    expect(digest).toContain('관찰 필요 1회');
  });

  it('기록이 없으면 그렇게 알려 준다', () => {
    expect(buildWeeklyDigest([], labelOf)).toBe('기록 없음');
  });
});
