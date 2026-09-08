// 월간 출석부 표 만들기 — 인쇄물과 CSV 가 같은 데이터를 쓴다.
//
// 학원 현장의 종이 출석부와 같은 모양: 세로는 원생, 가로는 날짜, 칸에는 한 글자 기호.
// 마지막 세 칸에 출석/결석/출석률을 넣어 학부모 문의에 바로 답할 수 있게 한다.

import { monthRange } from './date.js'
import { ATT } from './attendance.js'

export const ATT_LABELS = {
  [ATT.PRESENT]: 'O',
  [ATT.LATE]: '지',
  [ATT.ABSENT]: 'X',
  [ATT.MAKEUP]: '보',
  [ATT.EARLY]: '조'
}

function daysOfMonth(month) {
  const { to } = monthRange(month)
  const last = Number(to.slice(8, 10))
  return Array.from({ length: last }, (_, i) => String(i + 1).padStart(2, '0'))
}

/**
 * @param {{month:string, roster:Array, records:Array}} input
 * @returns {{headers:string[], rows:Array<Array<string>>, days:string[]}}
 */
export function monthlyRegister({ month, roster = [], records = [] }) {
  const days = daysOfMonth(month)
  // 수업이 하루도 없던 날짜는 빼서 A4 한 장에 들어가게 한다
  const used = new Set(records.map((r) => String(r.date).slice(8, 10)))
  const cols = days.filter((d) => used.has(d))
  const shown = cols.length ? cols : days

  const byStudent = new Map()
  for (const r of records) {
    if (!byStudent.has(r.student_id)) byStudent.set(r.student_id, new Map())
    byStudent.get(r.student_id).set(String(r.date).slice(8, 10), r.status)
  }

  const rows = roster.map((s) => {
    const mine = byStudent.get(s.id) || new Map()
    let present = 0
    let absent = 0
    const cells = shown.map((d) => {
      const st = mine.get(d)
      if (!st) return ''
      if (st === ATT.ABSENT) absent++
      else present++
      return ATT_LABELS[st] || st.slice(0, 1)
    })
    const total = present + absent
    return [s.name, ...cells, String(present), String(absent), total ? `${Math.round((present / total) * 100)}%` : '-']
  })

  return {
    days: shown,
    headers: ['원생', ...shown.map((d) => String(Number(d))), '출석', '결석', '출석률'],
    rows
  }
}
