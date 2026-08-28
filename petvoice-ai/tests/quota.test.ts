import { describe, expect, it } from 'vitest';
import { FREE_DAILY_LIMIT, canAddPet, isProActive, quotaState } from '../src/core/quota';

/** 로컬 자정 기준으로 계산되므로 테스트도 로컬 시각으로 만든다. */
function today(hour: number, minute = 0): number {
  const d = new Date();
  d.setHours(hour, minute, 0, 0);
  return d.getTime();
}

function daysAgo(days: number, hour = 12): number {
  const d = new Date();
  d.setDate(d.getDate() - days);
  d.setHours(hour, 0, 0, 0);
  return d.getTime();
}

describe('quotaState', () => {
  const now = today(15);

  it('처음이면 무료 3회가 모두 남아 있다', () => {
    const state = quotaState([], { pro: false }, now);
    expect(state.remaining).toBe(FREE_DAILY_LIMIT);
    expect(state.canAnalyze).toBe(true);
  });

  it('오늘 3회를 쓰면 더 분석할 수 없다', () => {
    const state = quotaState([today(9), today(11), today(13)], { pro: false }, now);
    expect(state.used).toBe(3);
    expect(state.remaining).toBe(0);
    expect(state.canAnalyze).toBe(false);
    expect(state.label).toContain('초기화');
  });

  it('어제 기록은 오늘 한도에 포함되지 않는다', () => {
    const state = quotaState([daysAgo(1), daysAgo(1, 20), daysAgo(2)], { pro: false }, now);
    expect(state.used).toBe(0);
    expect(state.canAnalyze).toBe(true);
  });

  it('자정 직전 사용도 같은 날로 센다', () => {
    const state = quotaState([today(23, 59)], { pro: false }, today(23, 59));
    expect(state.used).toBe(1);
  });

  it('프로는 무제한이다', () => {
    const state = quotaState([today(1), today(2), today(3), today(4)], { pro: true }, now);
    expect(state.limit).toBeNull();
    expect(state.canAnalyze).toBe(true);
    expect(state.label).toContain('무제한');
  });

  it('만료된 프로는 무료로 되돌린다', () => {
    const state = quotaState([], { pro: true, expiresAt: now - 1000 }, now);
    expect(state.isPro).toBe(false);
    expect(state.remaining).toBe(FREE_DAILY_LIMIT);
  });

  it('리셋 시각은 다음 자정이다', () => {
    const state = quotaState([], { pro: false }, now);
    expect(new Date(state.resetsAt).getHours()).toBe(0);
    expect(state.resetsAt).toBeGreaterThan(now);
  });
});

describe('isProActive / canAddPet', () => {
  it('만료가 없으면 계속 프로', () => {
    expect(isProActive({ pro: true })).toBe(true);
  });

  it('무료는 한 마리까지만 등록할 수 있다', () => {
    expect(canAddPet(0, { pro: false })).toBe(true);
    expect(canAddPet(1, { pro: false })).toBe(false);
    expect(canAddPet(5, { pro: true })).toBe(true);
  });
});
