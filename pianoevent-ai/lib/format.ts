/**
 * 날짜·시간 표기.
 *
 * 서버(대개 UTC)와 브라우저(원장의 로컬)가 같은 값을 서로 다르게 그리면
 * 순서표의 예상 시각이 화면마다 달라진다. 그래서 표기와 해석을 모두
 * 고정된 학원 시간대(APP_TIME_ZONE)에서 수행한다.
 */
export const APP_TIME_ZONE = process.env.NEXT_PUBLIC_APP_TIME_ZONE || 'Asia/Seoul'

const WEEKDAY = ['일', '월', '화', '수', '목', '금', '토']

interface ZonedParts {
  year: number
  month: number
  day: number
  hour: number
  minute: number
  second: number
  weekday: number
}

const partsFormatter = new Intl.DateTimeFormat('en-US', {
  timeZone: APP_TIME_ZONE,
  hour12: false,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
})

/** 주어진 시각을 학원 시간대의 연·월·일·시·분으로 분해한다 */
function zonedParts(date: Date): ZonedParts {
  const map: Record<string, number> = {}
  for (const part of partsFormatter.formatToParts(date)) {
    if (part.type !== 'literal') map[part.type] = Number(part.value)
  }
  const hour = map.hour % 24 // 자정을 24 로 주는 런타임 대응
  const asUtc = Date.UTC(map.year, map.month - 1, map.day, hour, map.minute, map.second)
  return {
    year: map.year,
    month: map.month,
    day: map.day,
    hour,
    minute: map.minute,
    second: map.second,
    weekday: new Date(asUtc).getUTCDay(),
  }
}

function offsetMinutes(date: Date): number {
  const p = zonedParts(date)
  const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second)
  return Math.round((asUtc - date.getTime()) / 60000)
}

const pad = (n: number) => String(n).padStart(2, '0')

function toDate(iso: string): Date | null {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d
}

function ampm(hour: number, minute: number): string {
  const label = hour < 12 ? '오전' : '오후'
  const h = hour % 12 === 0 ? 12 : hour % 12
  return `${label} ${h}:${pad(minute)}`
}

/** 초 → "3분 20초" */
export function formatDuration(sec: number): string {
  const total = Math.max(0, Math.round(sec))
  const m = Math.floor(total / 60)
  const s = total % 60
  if (m === 0) return `${s}초`
  if (s === 0) return `${m}분`
  return `${m}분 ${s}초`
}

/** 초 → "1:05:20" / "5:20" */
export function formatClockOffset(sec: number): string {
  const total = Math.max(0, Math.round(sec))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

/** 행사 시작 시각 + 오프셋 → "오후 3:12" (학원 시간대 기준) */
export function formatWallClock(startISO: string, offsetSec: number): string {
  const start = toDate(startISO)
  if (!start) return formatClockOffset(offsetSec)
  const p = zonedParts(new Date(start.getTime() + offsetSec * 1000))
  return ampm(p.hour, p.minute)
}

/** ISO → "2026년 3월 14일 (토) 오후 3:00" */
export function formatEventDate(iso: string): string {
  const d = toDate(iso)
  if (!d) return iso
  const p = zonedParts(d)
  return `${p.year}년 ${p.month}월 ${p.day}일 (${WEEKDAY[p.weekday]}) ${ampm(p.hour, p.minute)}`
}

/** ISO → "2026.03.14" */
export function formatShortDate(iso: string): string {
  const d = toDate(iso)
  if (!d) return iso
  const p = zonedParts(d)
  return `${p.year}.${pad(p.month)}.${pad(p.day)}`
}

/** ISO → <input type="datetime-local"> 값 (학원 시간대의 벽시계 시각) */
export function toDatetimeLocal(iso: string): string {
  const d = toDate(iso)
  if (!d) return ''
  const p = zonedParts(d)
  return `${p.year}-${pad(p.month)}-${pad(p.day)}T${pad(p.hour)}:${pad(p.minute)}`
}

/**
 * <input type="datetime-local"> 값("2026-09-15T15:00")을 학원 시간대의 벽시계로 해석해 ISO 로 바꾼다.
 * 브라우저나 서버의 시간대가 무엇이든 같은 결과가 나온다.
 */
export function fromDatetimeLocal(value: string): string | null {
  const m = value.trim().match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?$/)
  if (!m) return null
  const naive = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]), Number(m[4]), Number(m[5]), Number(m[6] ?? 0))
  // 오프셋은 시각에 따라 달라질 수 있어(서머타임) 한 번 보정한 뒤 다시 계산한다
  let ts = naive - offsetMinutes(new Date(naive)) * 60000
  ts = naive - offsetMinutes(new Date(ts)) * 60000
  return new Date(ts).toISOString()
}

/**
 * 사용자 입력을 ISO 로 정규화한다.
 * 시간대 정보가 붙어 있으면 그대로, 없으면 학원 시간대의 벽시계로 읽는다.
 */
export function normalizeEventAt(value: string): string | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  if (/(Z|[+-]\d{2}:?\d{2})$/.test(trimmed)) {
    const d = toDate(trimmed)
    return d ? d.toISOString() : null
  }
  return fromDatetimeLocal(trimmed)
}

/** 오늘로부터 n일 뒤 특정 시각(학원 시간대)의 ISO — 기본값·데모 데이터 생성용 */
export function isoAtLocalTime(daysFromNow: number, hour: number, minute = 0): string {
  const base = new Date(Date.now() + daysFromNow * 86_400_000)
  const p = zonedParts(base)
  return (
    fromDatetimeLocal(`${p.year}-${pad(p.month)}-${pad(p.day)}T${pad(hour)}:${pad(minute)}`) ?? base.toISOString()
  )
}
