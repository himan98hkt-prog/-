import { describe, it, expect } from 'vitest'
import { detectRisk, RISK_LEVEL } from '../src/core/risk.js'
import { ATT } from '../src/core/attendance.js'

const today = '2026-03-30'
const att = (student_id, date, status) => ({ student_id, date, status })

describe('이탈 위험 감지', () => {
  const students = [
    { id: 's1', name: '위험', status: '재원' },
    { id: 's2', name: '양호', status: '재원' },
    { id: 's3', name: '퇴원생', status: '퇴원' }
  ]

  it('결석률이 높고 연속 결석이면 위험도가 높다', () => {
    const attendance = [
      att('s1', '2026-03-09', ATT.PRESENT),
      att('s1', '2026-03-16', ATT.ABSENT),
      att('s1', '2026-03-23', ATT.ABSENT),
      att('s1', '2026-03-30', ATT.ABSENT),
      att('s2', '2026-03-09', ATT.PRESENT),
      att('s2', '2026-03-16', ATT.PRESENT),
      att('s2', '2026-03-23', ATT.PRESENT),
      att('s2', '2026-03-30', ATT.PRESENT)
    ]
    const rows = detectRisk({ students, attendance, payments: [], counselLogs: [], today })
    expect(rows[0].name).toBe('위험')
    expect(rows[0].level).toBe(RISK_LEVEL.HIGH)
    expect(rows[0].absentStreak).toBe(3)
    expect(rows[0].reasons.join()).toContain('연속 결석')
  })

  it('퇴원생은 대상에서 제외한다', () => {
    const rows = detectRisk({
      students,
      attendance: [att('s3', '2026-03-30', ATT.ABSENT), att('s3', '2026-03-23', ATT.ABSENT), att('s3', '2026-03-16', ATT.ABSENT)],
      payments: [], counselLogs: [], today
    })
    expect(rows.find((r) => r.student_id === 's3')).toBeUndefined()
  })

  it('미납이 쌓이면 점수에 반영된다', () => {
    const payments = [
      { student_id: 's2', amount: 100000, paid_at: null },
      { student_id: 's2', amount: 100000, paid_at: null }
    ]
    const rows = detectRisk({ students, attendance: [], payments, counselLogs: [], today })
    const s2 = rows.find((r) => r.student_id === 's2')
    expect(s2.unpaidMonths).toBe(2)
    expect(s2.reasons.join()).toContain('미납 2개월')
  })

  it('완납 기록은 미납으로 세지 않는다', () => {
    const payments = [{ student_id: 's2', amount: 100000, paid_at: '2026-03-05' }]
    const rows = detectRisk({ students, attendance: [], payments, counselLogs: [], today })
    const s2 = rows.find((r) => r.student_id === 's2')
    expect(s2?.unpaidMonths ?? 0).toBe(0)
  })

  it('표본이 3회 미만이면 결석률로 위험을 매기지 않는다', () => {
    const rows = detectRisk({
      students, attendance: [att('s2', '2026-03-30', ATT.ABSENT)], payments: [], counselLogs: [], today
    })
    const s2 = rows.find((r) => r.student_id === 's2')
    expect(s2.reasons.some((r) => r.includes('결석률'))).toBe(false)
  })

  it('위험도 내림차순으로 정렬한다', () => {
    const rows = detectRisk({
      students,
      attendance: [
        att('s1', '2026-03-16', ATT.ABSENT), att('s1', '2026-03-23', ATT.ABSENT), att('s1', '2026-03-30', ATT.ABSENT),
        att('s2', '2026-03-16', ATT.PRESENT), att('s2', '2026-03-23', ATT.PRESENT), att('s2', '2026-03-30', ATT.ABSENT)
      ],
      payments: [], counselLogs: [], today
    })
    expect(rows.map((r) => r.score)).toEqual([...rows.map((r) => r.score)].sort((a, b) => b - a))
  })
})
