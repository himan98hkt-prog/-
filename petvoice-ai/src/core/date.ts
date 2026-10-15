/** 로컬 타임존 기준 날짜 유틸. 다이어리/캘린더/무료 횟수 리셋이 전부 이 기준을 쓴다. */

export const DAY_MS = 24 * 60 * 60 * 1000;

/** `2026-08-28` 형태의 로컬 날짜 키 */
export function dayKey(ts: number | Date): string {
  const d = ts instanceof Date ? ts : new Date(ts);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function startOfDay(ts: number | Date): number {
  const d = ts instanceof Date ? new Date(ts.getTime()) : new Date(ts);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

/** 다음 자정 — 무료 사용 횟수가 초기화되는 시각 */
export function startOfNextDay(ts: number | Date): number {
  const d = ts instanceof Date ? new Date(ts.getTime()) : new Date(ts);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + 1);
  return d.getTime();
}

export function addDays(ts: number, days: number): number {
  const d = new Date(ts);
  d.setDate(d.getDate() + days);
  return d.getTime();
}

/**
 * 상대 시각을 **표현이 아니라 구조로** 돌려준다.
 * 문장은 언어마다 다르므로 조립은 UI 가 한다.
 */
export type RelativeTime =
  | { kind: 'justNow' }
  | { kind: 'minutes'; value: number }
  | { kind: 'hours'; value: number }
  | { kind: 'yesterday' }
  | { kind: 'days'; value: number }
  | { kind: 'date'; ts: number };

export function relativeTime(ts: number, now = Date.now()): RelativeTime {
  const diff = now - ts;
  if (diff < 60_000) return { kind: 'justNow' };
  if (diff < 3_600_000) return { kind: 'minutes', value: Math.floor(diff / 60_000) };
  if (dayKey(ts) === dayKey(now)) return { kind: 'hours', value: Math.floor(diff / 3_600_000) };

  const days = Math.round((startOfDay(now) - startOfDay(ts)) / DAY_MS);
  if (days === 1) return { kind: 'yesterday' };
  if (days < 7) return { kind: 'days', value: days };
  return { kind: 'date', ts };
}

/** 남은 시간을 시/분으로 쪼갠다. 문장 조립은 UI. */
export function splitDuration(ms: number): { hours: number; minutes: number } {
  const totalMinutes = Math.max(0, Math.ceil(ms / 60_000));
  return { hours: Math.floor(totalMinutes / 60), minutes: totalMinutes % 60 };
}
