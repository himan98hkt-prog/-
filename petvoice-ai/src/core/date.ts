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

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

export function weekdayKo(ts: number | Date): string {
  const d = ts instanceof Date ? ts : new Date(ts);
  return WEEKDAYS[d.getDay()];
}

/** `8월 28일 (금) 오후 3:12` */
export function formatKo(ts: number | Date): string {
  const d = ts instanceof Date ? ts : new Date(ts);
  const hours = d.getHours();
  const ampm = hours < 12 ? '오전' : '오후';
  const h12 = hours % 12 === 0 ? 12 : hours % 12;
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${d.getMonth() + 1}월 ${d.getDate()}일 (${weekdayKo(d)}) ${ampm} ${h12}:${mm}`;
}

/** `방금 전`, `3분 전`, `어제`, `3일 전` */
export function relativeKo(ts: number, now = Date.now()): string {
  const diff = now - ts;
  if (diff < 60_000) return '방금 전';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}분 전`;
  if (dayKey(ts) === dayKey(now)) return `${Math.floor(diff / 3_600_000)}시간 전`;
  const days = Math.round((startOfDay(now) - startOfDay(ts)) / DAY_MS);
  if (days === 1) return '어제';
  if (days < 7) return `${days}일 전`;
  return `${new Date(ts).getMonth() + 1}월 ${new Date(ts).getDate()}일`;
}

/** 남은 시간을 `2시간 13분` 형태로 */
export function durationKo(ms: number): string {
  if (ms <= 0) return '곧';
  const totalMinutes = Math.ceil(ms / 60_000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes}분`;
  if (minutes === 0) return `${hours}시간`;
  return `${hours}시간 ${minutes}분`;
}
