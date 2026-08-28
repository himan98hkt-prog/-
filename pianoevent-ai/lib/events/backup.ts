/**
 * 자동 저장.
 *
 * 원장님이 잃으시는 경우는 사고가 아니라 **평범한 하루**다.
 * 브라우저를 잘못 닫고, 명단을 교체로 넣어 버리고, 컴퓨터를 포맷하신다.
 * "내보내기 하세요" 라고 적어 두어도 사고가 나기 전에 하시는 분은 없다.
 *
 * 그래서 하루에 한 번, 프로그램이 알아서 행사를 파일로 떨궈 둔다.
 * 원장님께 **묻지 않는다.** 저장 위치도 고르시게 하지 않는다 —
 * 프로그램 폴더 아래 `백업/날짜/` 다. 인터넷으로 나가는 것은 하나도 없다.
 *
 * 열네 날치만 남긴다. 더 두면 폴더만 무거워지고, 두 주 넘게 모르고 지나신
 * 사고는 백업으로도 못 고친다.
 */

/** 남겨 둘 날수 */
export const BACKUP_KEEP_DAYS = 14

/** 하루에 한 번이면 충분하다 */
export const BACKUP_EVERY_MS = 24 * 60 * 60 * 1000

export const BACKUP_DIR = '백업'
export const BACKUP_MARK = 'pianoevent.backup.at'

/** `2026-08-28` — 폴더 하나가 하루다 */
export function backupDay(at: Date | string = new Date()): string {
  const d = typeof at === 'string' ? new Date(at) : at
  const safe = Number.isNaN(d.getTime()) ? new Date() : d
  const pad = (n: number) => String(n).padStart(2, '0')
  // 원장님 컴퓨터의 날짜로 적는다. UTC 로 적으면 밤에 만든 것이 어제 폴더로 들어간다.
  return `${safe.getFullYear()}-${pad(safe.getMonth() + 1)}-${pad(safe.getDate())}`
}

/** 오늘 몫을 이미 떴는가 */
export function needsBackup(lastAt: string | null, now: Date | string = new Date()): boolean {
  if (!lastAt) return true
  const last = new Date(lastAt)
  if (Number.isNaN(last.getTime())) return true
  const at = typeof now === 'string' ? new Date(now) : now
  return backupDay(last) !== backupDay(at)
}

/**
 * 지울 날 폴더 — 오래된 것부터.
 * 이름이 날짜라 글자 차례가 곧 날짜 차례다.
 */
export function pruneDays(days: string[], keep = BACKUP_KEEP_DAYS): string[] {
  const sorted = [...new Set(days.filter((d) => /^\d{4}-\d{2}-\d{2}$/.test(d)))].sort()
  return sorted.slice(0, Math.max(0, sorted.length - keep))
}

/** 파일 이름에 쓸 수 없는 글자를 걷어 낸다 (윈도우 기준이 가장 좁다) */
export function safeFileName(title: string, fallback = '행사'): string {
  const cleaned = title
    .replace(/[\\/:*?"<>|]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return (cleaned || fallback).slice(0, 60)
}

/** 같은 이름의 행사가 둘이면 뒤에 번호를 붙인다 — 덮어쓰면 하나를 잃는다 */
export function uniqueName(name: string, taken: Set<string>): string {
  if (!taken.has(name)) return name
  for (let i = 2; i < 100; i += 1) {
    const tried = `${name} (${i})`
    if (!taken.has(tried)) return tried
  }
  return `${name} (${Date.now()})`
}

export interface BackupDay {
  day: string
  files: { name: string; bytes: number }[]
}

/** 화면에 적을 한 줄 — "8월 28일 · 행사 3개" */
export function describeBackup(day: BackupDay): string {
  const [, month, date] = day.day.split('-')
  return `${Number(month)}월 ${Number(date)}일 · 행사 ${day.files.length}개`
}

/** 가장 최근 것이 위로 오게 */
export function sortDays(days: BackupDay[]): BackupDay[] {
  return [...days].sort((a, b) => b.day.localeCompare(a.day))
}
