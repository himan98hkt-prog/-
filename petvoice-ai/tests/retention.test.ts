import { describe, expect, it } from 'vitest';
import {
  countExpiring,
  keepWithinRetention,
  DEFAULT_RETENTION,
  isRetentionPolicy,
  RETENTION_POLICIES,
  retentionCutoff,
  retentionDays,
} from '../src/core/retention';
import { DAY_MS, startOfDay } from '../src/core/date';

const NOW = new Date(2026, 7, 29, 15, 30).getTime();

describe('보관 정책', () => {
  it('기본값은 무제한이다 — 업데이트 한 번으로 남의 기록을 지우지 않는다', () => {
    expect(DEFAULT_RETENTION).toBe('forever');
    expect(retentionCutoff('forever', NOW)).toBeNull();
    expect(retentionDays('forever')).toBeNull();
  });

  it('정책마다 보관 일수가 있다', () => {
    expect(retentionDays('6m')).toBe(183);
    expect(retentionDays('1y')).toBe(365);
    expect(retentionDays('2y')).toBe(730);
  });

  it('자정 기준으로 자른다 — 같은 날 안에서 갑자기 사라지지 않게', () => {
    const cutoff = retentionCutoff('1y', NOW);
    expect(cutoff).toBe(startOfDay(NOW) - 365 * DAY_MS);
    expect(cutoff).toBe(startOfDay(cutoff!));
  });

  it('알 수 없는 값은 정책으로 받지 않는다', () => {
    expect(isRetentionPolicy('1y')).toBe(true);
    expect(isRetentionPolicy('10y')).toBe(false);
    expect(isRetentionPolicy(undefined)).toBe(false);
    for (const policy of RETENTION_POLICIES) expect(isRetentionPolicy(policy)).toBe(true);
  });
});

describe('countExpiring', () => {
  const cutoff = retentionCutoff('1y', NOW)!;

  it('정책을 바꾸기 전에 몇 건이 지워질지 센다', () => {
    const list = [cutoff - 1, cutoff - DAY_MS, cutoff, cutoff + DAY_MS, NOW];
    expect(countExpiring(list, '1y', NOW)).toBe(2);
  });

  it('경계값은 남는다', () => {
    expect(countExpiring([cutoff], '1y', NOW)).toBe(0);
  });

  it('무제한이면 언제나 0', () => {
    expect(countExpiring([0, 1, 2], 'forever', NOW)).toBe(0);
  });
});

describe('keepWithinRetention', () => {
  const cutoff = retentionCutoff('1y', NOW)!;
  const items = [
    { createdAt: cutoff - DAY_MS, id: 'old' },
    { createdAt: cutoff, id: 'edge' },
    { createdAt: NOW, id: 'new' },
  ];

  it('복원에서 정책 밖 기록을 되살리지 않는다', () => {
    // 이게 없으면 폰을 바꿀 때마다 지운 기록이 백업에서 되돌아온다
    expect(keepWithinRetention(items, '1y', NOW).map((i) => i.id)).toEqual(['edge', 'new']);
  });

  it('무제한이면 전부 남긴다', () => {
    expect(keepWithinRetention(items, 'forever', NOW)).toHaveLength(3);
  });

  it('원본을 건드리지 않는다', () => {
    const copy = [...items];
    keepWithinRetention(items, '6m', NOW);
    expect(items).toEqual(copy);
  });
});
