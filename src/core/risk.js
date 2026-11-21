// 이탈 위험 감지 — 최근 4주 결석률 + 연속 결석 + 상담 공백 + 미납을 합산한 0~100 점수.
// 원장이 "왜 위험한지"를 바로 읽을 수 있도록 reasons 를 함께 돌려준다.

import { ATT, summarize, currentAbsentStreak } from './attendance.js'
import { daysBetween } from './date.js'
import { PAY_STATUS, statusOf } from './fees.js'

export const RISK_LEVEL = { HIGH: '높음', MID: '주의', LOW: '양호' }

/**
 * @param ctx { students, attendance(최근 4주), counselLogs, payments, today }
 * @returns 위험도 내림차순 목록
 */
export function detectRisk(ctx = {}) {
  const { students = [], attendance = [], counselLogs = [], payments = [], today } = ctx
  const attByStudent = new Map()
  for (const r of attendance) {
    if (!attByStudent.has(r.student_id)) attByStudent.set(r.student_id, [])
    attByStudent.get(r.student_id).push(r)
  }
  const lastCounsel = new Map()
  for (const c of counselLogs) {
    const d = String(c.created_at || '').slice(0, 10)
    const prev = lastCounsel.get(c.student_id)
    if (!prev || d > prev) lastCounsel.set(c.student_id, d)
  }
  const unpaidMonths = new Map()
  for (const p of payments) {
    if (statusOf(p) === PAY_STATUS.FULL) continue
    unpaidMonths.set(p.student_id, (unpaidMonths.get(p.student_id) || 0) + 1)
  }

  const rows = []
  for (const s of students) {
    if (s.status && s.status !== '재원') continue
    const recs = attByStudent.get(s.id) || []
    const sum = summarize(recs)
    const streak = currentAbsentStreak(recs)
    const unpaid = unpaidMonths.get(s.id) || 0
    const counselDate = lastCounsel.get(s.id)
    const counselGap = counselDate && today ? daysBetween(counselDate, today) : null

    let score = 0
    const reasons = []
    if (sum.total >= 3) {
      if (sum.absentRate >= 40) { score += 45; reasons.push(`최근 4주 결석률 ${sum.absentRate}%`) }
      else if (sum.absentRate >= 25) { score += 28; reasons.push(`최근 4주 결석률 ${sum.absentRate}%`) }
      else if (sum.absentRate >= 15) { score += 14; reasons.push(`최근 4주 결석률 ${sum.absentRate}%`) }
    }
    if (streak >= 3) { score += 30; reasons.push(`연속 결석 ${streak}회`) }
    else if (streak === 2) { score += 15; reasons.push('연속 결석 2회') }
    if (unpaid >= 2) { score += 20; reasons.push(`미납 ${unpaid}개월`) }
    else if (unpaid === 1) { score += 10; reasons.push('미납 1개월') }
    if (counselGap == null) { score += 8; reasons.push('상담 이력 없음') }
    else if (counselGap > 90) { score += 8; reasons.push(`마지막 상담 ${counselGap}일 전`) }

    if (!score) continue
    score = Math.min(100, score)
    rows.push({
      student_id: s.id,
      name: s.name,
      score,
      level: score >= 55 ? RISK_LEVEL.HIGH : score >= 30 ? RISK_LEVEL.MID : RISK_LEVEL.LOW,
      absentRate: sum.absentRate,
      absentStreak: streak,
      unpaidMonths: unpaid,
      lastCounselAt: counselDate || null,
      reasons
    })
  }
  return rows.sort((a, b) => b.score - a.score || String(a.name).localeCompare(String(b.name), 'ko'))
}

export const _internals = { ATT }
