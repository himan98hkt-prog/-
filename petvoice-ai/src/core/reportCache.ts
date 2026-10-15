/**
 * 주간 리포트 캐시.
 *
 * 리포트 버튼은 누를 때마다 모델을 불렀다. 같은 날 세 번 열면 세 번 과금되고
 * 세 번 다 기다린다 — 그런데 그 사이 새 기록이 없었다면 **입력이 완전히 같다**.
 *
 * 그래서 캐시 키를 "이번 주"가 아니라 **모델에게 준 입력 그대로**로 잡았다.
 * 리포트 구간은 오늘을 끝으로 하는 최근 7일이라 날짜가 바뀌면 입력도 바뀐다.
 * 주 단위로 묶었다면 어제 만든 리포트를 오늘 그대로 내놓게 된다.
 * 새 분석이 하나라도 추가되면 입력이 달라지므로 캐시는 저절로 무효가 된다.
 */

export interface CachedReport<T> {
  key: string;
  report: T;
  createdAt: number;
}

/** 캐시에 남겨 두는 최대 개수 (반려동물 여러 마리 × 언어를 감안) */
export const REPORT_CACHE_LIMIT = 12;

/** 입력이 같아도 이만큼 지났으면 다시 만든다 */
export const REPORT_CACHE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

/**
 * 다이제스트를 그대로 키로 쓰면 저장 상태가 커진다(수천 자).
 * 32비트 FNV-1a 로 줄인다 — 암호용이 아니라 "같은 입력인가"만 보면 되는 자리다.
 */
export function hashDigest(text: string): string {
  let hash = 0x811c9dc5;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, '0');
}

export function reportCacheKey(petId: string, locale: string, digest: string): string {
  return `${petId}|${locale}|${hashDigest(digest)}|${digest.length}`;
}

export function readReportCache<T>(
  cache: readonly CachedReport<T>[],
  key: string,
  now = Date.now(),
  maxAgeMs = REPORT_CACHE_MAX_AGE_MS,
): T | null {
  const hit = cache.find((item) => item.key === key);
  if (!hit) return null;
  if (now - hit.createdAt > maxAgeMs) return null;
  // 시계가 뒤로 간 기기(수동 변경)에서 미래 시각이 박히면 영원히 안 만료된다
  if (hit.createdAt > now) return null;
  return hit.report;
}

/** 새 리포트를 넣고 오래된 것부터 잘라 낸다 */
export function writeReportCache<T>(
  cache: readonly CachedReport<T>[],
  key: string,
  report: T,
  now = Date.now(),
  limit = REPORT_CACHE_LIMIT,
): CachedReport<T>[] {
  const next = [{ key, report, createdAt: now }, ...cache.filter((item) => item.key !== key)];
  return next.slice(0, limit);
}
