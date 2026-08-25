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
  const mm = h > 0 ? String(m).padStart(2, '0') : String(m)
  return h > 0 ? `${h}:${mm}:${String(s).padStart(2, '0')}` : `${mm}:${String(s).padStart(2, '0')}`
}

/** 행사 시작 시각 + 오프셋 → "오후 3:12" */
export function formatWallClock(startISO: string, offsetSec: number): string {
  const start = new Date(startISO)
  if (Number.isNaN(start.getTime())) return formatClockOffset(offsetSec)
  const at = new Date(start.getTime() + offsetSec * 1000)
  const h24 = at.getHours()
  const ampm = h24 < 12 ? '오전' : '오후'
  const h = h24 % 12 === 0 ? 12 : h24 % 12
  return `${ampm} ${h}:${String(at.getMinutes()).padStart(2, '0')}`
}

const WEEKDAY = ['일', '월', '화', '수', '목', '금', '토']

/** ISO → "2026년 3월 14일 (토) 오후 3:00" */
export function formatEventDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const h24 = d.getHours()
  const ampm = h24 < 12 ? '오전' : '오후'
  const h = h24 % 12 === 0 ? 12 : h24 % 12
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 (${WEEKDAY[d.getDay()]}) ${ampm} ${h}:${String(
    d.getMinutes(),
  ).padStart(2, '0')}`
}

/** ISO → "2026.03.14" */
export function formatShortDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`
}

/** <input type="datetime-local"> 용 값 */
export function toDatetimeLocal(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
