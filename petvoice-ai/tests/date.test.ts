import { describe, expect, it } from 'vitest';
import { dayKey, durationKo, relativeKo, startOfDay, startOfNextDay, weekdayKo } from '../src/core/date';

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

  it('요일을 한국어로', () => {
    expect(weekdayKo(new Date(2026, 7, 28))).toBe('금');
  });

  it('상대 시각 표기', () => {
    const now = new Date(2026, 7, 28, 15, 0).getTime();
    expect(relativeKo(now - 30_000, now)).toBe('방금 전');
    expect(relativeKo(now - 5 * 60_000, now)).toBe('5분 전');
    expect(relativeKo(now - 3 * 3_600_000, now)).toBe('3시간 전');
    expect(relativeKo(new Date(2026, 7, 27, 15).getTime(), now)).toBe('어제');
    expect(relativeKo(new Date(2026, 7, 25, 15).getTime(), now)).toBe('3일 전');
  });

  it('자정 직후에는 몇 시간 전이 아니라 어제로 읽힌다', () => {
    const now = new Date(2026, 7, 28, 0, 30).getTime();
    expect(relativeKo(new Date(2026, 7, 27, 23, 30).getTime(), now)).toBe('어제');
  });

  it('남은 시간 표기', () => {
    expect(durationKo(0)).toBe('곧');
    expect(durationKo(45 * 60_000)).toBe('45분');
    expect(durationKo(2 * 3_600_000)).toBe('2시간');
    expect(durationKo(2 * 3_600_000 + 13 * 60_000)).toBe('2시간 13분');
  });
});
