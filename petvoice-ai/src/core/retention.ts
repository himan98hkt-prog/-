import { DAY_MS, startOfDay } from './date';

/**
 * 기록 보관 정책.
 *
 * 기록은 지금까지 무한히 쌓였다. 하루 세 번씩 몇 년이면 수천 건이고,
 * 개인정보처리방침에는 "삭제 요청 시까지"라고만 적혀 있었다 —
 * 즉 실제로는 보관 기간이 없었다는 뜻이다.
 *
 * 기본값은 **무제한**이다. 이미 쓰고 있는 사람의 기록을 업데이트 한 번으로
 * 조용히 지우는 것보다, 고르게 하는 편이 맞다. 고른 뒤에는 앱을 열 때마다 정리한다.
 */

export type RetentionPolicy = 'forever' | '1y' | '2y' | '6m';

export const RETENTION_POLICIES: RetentionPolicy[] = ['forever', '2y', '1y', '6m'];

export const DEFAULT_RETENTION: RetentionPolicy = 'forever';

/** 정책이 뜻하는 보관 일수. 무제한이면 null. */
export function retentionDays(policy: RetentionPolicy): number | null {
  switch (policy) {
    case '6m':
      return 183;
    case '1y':
      return 365;
    case '2y':
      return 730;
    default:
      return null;
  }
}

export function isRetentionPolicy(value: unknown): value is RetentionPolicy {
  return RETENTION_POLICIES.includes(value as RetentionPolicy);
}

/**
 * 이 시각보다 **오래된** 기록을 지운다. 무제한이면 null.
 *
 * 자정 기준으로 자른다. 시:분까지 따지면 같은 날 아침에 남아 있던 기록이
 * 저녁에 사라져 "왜 방금까지 있던 게 없어졌지"가 된다.
 */
export function retentionCutoff(policy: RetentionPolicy, now = Date.now()): number | null {
  const days = retentionDays(policy);
  if (days === null) return null;
  return startOfDay(now) - days * DAY_MS;
}

/** 지금 정책에서 지워질 기록 수 — 정책을 바꾸기 전에 미리 보여 준다 */
export function countExpiring(
  createdAts: readonly number[],
  policy: RetentionPolicy,
  now = Date.now(),
): number {
  const cutoff = retentionCutoff(policy, now);
  if (cutoff === null) return 0;
  return createdAts.filter((ts) => ts < cutoff).length;
}

/**
 * 정책에 맞는 기록만 남긴다.
 *
 * 복원(restore)에서 이게 없으면 보관 정책이 조용히 무효가 된다 —
 * 기기에서 지운 오래된 기록이 백업에서 그대로 되돌아오기 때문이다.
 * 사용자는 지웠다고 생각하는데 폰을 바꾸면 다시 나타난다.
 */
export function keepWithinRetention<T extends { createdAt: number }>(
  items: readonly T[],
  policy: RetentionPolicy,
  now = Date.now(),
): T[] {
  const cutoff = retentionCutoff(policy, now);
  if (cutoff === null) return [...items];
  return items.filter((item) => item.createdAt >= cutoff);
}
