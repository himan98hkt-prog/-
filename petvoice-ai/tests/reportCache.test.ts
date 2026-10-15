import { describe, expect, it } from 'vitest';
import {
  hashDigest,
  readReportCache,
  REPORT_CACHE_LIMIT,
  REPORT_CACHE_MAX_AGE_MS,
  reportCacheKey,
  writeReportCache,
  type CachedReport,
} from '../src/core/reportCache';

const NOW = 1_800_000_000_000;
const REPORT = { headline: '이번 주는 편안했어요', trend: '', todo: [] };

describe('캐시 키', () => {
  it('같은 입력이면 같은 키', () => {
    expect(reportCacheKey('p1', 'ko', 'digest')).toBe(reportCacheKey('p1', 'ko', 'digest'));
  });

  it('반려동물이 다르면 다른 키', () => {
    expect(reportCacheKey('p1', 'ko', 'd')).not.toBe(reportCacheKey('p2', 'ko', 'd'));
  });

  it('언어가 다르면 다른 키 — 한국어 리포트를 영어 화면에 보여 주면 안 된다', () => {
    expect(reportCacheKey('p1', 'ko', 'd')).not.toBe(reportCacheKey('p1', 'en', 'd'));
  });

  it('기록이 하나만 늘어도 다른 키가 된다', () => {
    const before = '- 총 분석 3회\n- 긍정 70%';
    const after = '- 총 분석 4회\n- 긍정 70%';
    expect(reportCacheKey('p1', 'ko', before)).not.toBe(reportCacheKey('p1', 'ko', after));
  });

  it('해시가 부딪혀도 길이가 다르면 갈라진다', () => {
    expect(hashDigest('abc')).toHaveLength(8);
    expect(hashDigest('')).toHaveLength(8);
  });
});

describe('읽기', () => {
  const key = reportCacheKey('p1', 'ko', 'digest');
  const cache: CachedReport<typeof REPORT>[] = [{ key, report: REPORT, createdAt: NOW }];

  it('같은 입력이면 모델을 부르지 않고 돌려준다', () => {
    expect(readReportCache(cache, key, NOW + 1000)).toEqual(REPORT);
  });

  it('없는 키는 null', () => {
    expect(readReportCache(cache, 'other', NOW)).toBeNull();
  });

  it('너무 오래된 캐시는 버린다', () => {
    expect(readReportCache(cache, key, NOW + REPORT_CACHE_MAX_AGE_MS + 1)).toBeNull();
  });

  it('기기 시계가 뒤로 간 경우에도 영원히 살아남지 않는다', () => {
    expect(readReportCache(cache, key, NOW - 1)).toBeNull();
  });
});

describe('쓰기', () => {
  it('가장 최근 것이 앞에 온다', () => {
    let cache = writeReportCache<typeof REPORT>([], 'a', REPORT, NOW);
    cache = writeReportCache(cache, 'b', REPORT, NOW + 1);
    expect(cache.map((c) => c.key)).toEqual(['b', 'a']);
  });

  it('같은 키를 다시 쓰면 중복이 생기지 않는다', () => {
    let cache = writeReportCache<typeof REPORT>([], 'a', REPORT, NOW);
    cache = writeReportCache(cache, 'a', REPORT, NOW + 1);
    expect(cache).toHaveLength(1);
    expect(cache[0].createdAt).toBe(NOW + 1);
  });

  it('상한을 넘으면 오래된 것부터 버린다 — 저장 상태가 무한정 커지지 않게', () => {
    let cache: CachedReport<typeof REPORT>[] = [];
    for (let i = 0; i < REPORT_CACHE_LIMIT + 5; i += 1) {
      cache = writeReportCache(cache, `k${i}`, REPORT, NOW + i);
    }
    expect(cache).toHaveLength(REPORT_CACHE_LIMIT);
    expect(cache[0].key).toBe(`k${REPORT_CACHE_LIMIT + 4}`);
  });
});
