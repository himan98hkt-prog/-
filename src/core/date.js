// 날짜 유틸 — 저장 포맷은 전부 'YYYY-MM-DD'(date) / 'YYYY-MM'(month) 문자열이다.
// IndexedDB / PostgreSQL 양쪽에서 그대로 범위 인덱스로 쓸 수 있어서 Date 객체를 저장하지 않는다.

export const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

export function pad2(n) {
  return String(n).padStart(2, '0')
}

export function toYmd(d = new Date()) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

export function toMonth(ymd) {
  return String(ymd).slice(0, 7)
}

export function monthRange(month) {
  // '2026-03' -> { from: '2026-03-01', to: '2026-03-31' }
  const [y, m] = month.split('-').map(Number)
  const last = new Date(y, m, 0).getDate()
  return { from: `${month}-01`, to: `${month}-${pad2(last)}` }
}

export function addDays(ymd, n) {
  const [y, m, d] = ymd.split('-').map(Number)
  const dt = new Date(y, m - 1, d + n)
  return toYmd(dt)
}

export function addMonths(month, n) {
  const [y, m] = month.split('-').map(Number)
  const dt = new Date(y, m - 1 + n, 1)
  return `${dt.getFullYear()}-${pad2(dt.getMonth() + 1)}`
}

export function dowOf(ymd) {
  const [y, m, d] = ymd.split('-').map(Number)
  return new Date(y, m - 1, d).getDay() // 0=일
}

export function daysBetween(a, b) {
  const pa = a.split('-').map(Number)
  const pb = b.split('-').map(Number)
  const ta = Date.UTC(pa[0], pa[1] - 1, pa[2])
  const tb = Date.UTC(pb[0], pb[1] - 1, pb[2])
  return Math.round((tb - ta) / 86400000)
}

export function lastNWeeks(endYmd, weeks = 4) {
  return { from: addDays(endYmd, -(weeks * 7 - 1)), to: endYmd }
}

export function hhmmToMin(hhmm) {
  const [h, m] = String(hhmm).split(':').map(Number)
  return h * 60 + (m || 0)
}

export function minToHhmm(min) {
  return `${pad2(Math.floor(min / 60))}:${pad2(min % 60)}`
}
