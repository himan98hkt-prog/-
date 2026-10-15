import { describe, expect, it } from 'vitest';
import { dayKey, relativeTime, splitDuration, startOfDay, startOfNextDay } from '../src/core/date';

describe('날짜 유틸', () => {
  it('로컬 기준 날짜 키를 만든다', () => {
    expect(dayKey(new Date(2026, 7, 28, 23, 59))).toBe('2026-08-28');
    expect(dayKey(new Date(2026, 0, 1, 0, 0))).toBe('2026-01-01');
  });

  it('startOfDay 는 인자를 변형하지 않는다', () => {
    const d = new Date(2026, 7, 28, 15, 30);
    startOfDay(d);
    expect(d.getHours()).toBe(15);
  });

  it('다음 자정을 정확히 계산한다 (월말 포함)', () => {
    const next = new Date(startOfNextDay(new Date(2026, 7, 31, 22)));
    expect(next.getMonth()).toBe(8);
    expect(next.getDate()).toBe(1);
    expect(next.getHours()).toBe(0);
  });
});

describe('relativeTime — 문장이 아니라 구조를 돌려준다', () => {
  const now = new Date(2026, 7, 28, 15, 0).getTime();

  it('구간별로 종류가 갈린다', () => {
    expect(relativeTime(now - 30_000, now)).toEqual({ kind: 'justNow' });
    expect(relativeTime(now - 5 * 60_000, now)).toEqual({ kind: 'minutes', value: 5 });
    expect(relativeTime(now - 3 * 3_600_000, now)).toEqual({ kind: 'hours', value: 3 });
    expect(relativeTime(new Date(2026, 7, 27, 15).getTime(), now)).toEqual({ kind: 'yesterday' });
    expect(relativeTime(new Date(2026, 7, 25, 15).getTime(), now)).toEqual({ kind: 'days', value: 3 });
  });

  it('일주일이 넘으면 날짜로 넘긴다', () => {
    const old = new Date(2026, 7, 1, 15).getTime();
    expect(relativeTime(old, now)).toEqual({ kind: 'date', ts: old });
  });

  it('자정 직후에는 몇 시간 전이 아니라 어제로 읽힌다', () => {
    const midnight = new Date(2026, 7, 28, 0, 30).getTime();
    expect(relativeTime(new Date(2026, 7, 27, 23, 30).getTime(), midnight)).toEqual({ kind: 'yesterday' });
  });
});

describe('splitDuration', () => {
  it('시/분으로 쪼갠다', () => {
    expect(splitDuration(45 * 60_000)).toEqual({ hours: 0, minutes: 45 });
    expect(splitDuration(2 * 3_600_000)).toEqual({ hours: 2, minutes: 0 });
    expect(splitDuration(2 * 3_600_000 + 13 * 60_000)).toEqual({ hours: 2, minutes: 13 });
    expect(splitDuration(-1)).toEqual({ hours: 0, minutes: 0 });
  });
});
