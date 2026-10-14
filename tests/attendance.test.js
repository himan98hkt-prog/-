import { describe, it, expect } from 'vitest'
import { ATT, summarize, summarizeBy, currentAbsentStreak, isPresent } from '../src/core/attendance.js'

const rec = (student_id, date, status) => ({ student_id, date, status })

describe('출결 집계', () => {
  it('결석만 미출석으로 계산한다 (지각·조퇴·보강은 출석)', () => {
    const s = summarize([
      rec('a', '2026-03-02', ATT.PRESENT),
      rec('a', '2026-03-03', ATT.LATE),
      rec('a', '2026-03-04', ATT.EARLY),
      rec('a', '2026-03-05', ATT.MAKEUP),
      rec('a', '2026-03-06', ATT.ABSENT)
    ])
    expect(s.total).toBe(5)
    expect(s.present).toBe(4)
    expect(s.absent).toBe(1)
    expect(s.rate).toBe(80)
    expect(s.absentRate).toBe(20)
  })

  it('기록이 없으면 0%로 나누지 않는다', () => {
    const s = summarize([])
    expect(s.total).toBe(0)
    expect(s.rate).toBe(0)
    expect(s.absentRate).toBe(0)
  })

  it('알 수 없는 상태값은 무시한다', () => {
    const s = summarize([rec('a', '2026-03-02', ATT.PRESENT), rec('a', '2026-03-03', 'ㅁㅁ')])
    expect(s.total).toBe(1)
  })

  it('소수 첫째 자리까지 반올림한다', () => {
    const s = summarize([rec('a', '1', ATT.PRESENT), rec('a', '2', ATT.PRESENT), rec('a', '3', ATT.ABSENT)])
    expect(s.rate).toBe(66.7)
  })

  it('원생별로 나눠 집계한다', () => {
    const map = summarizeBy([
      rec('a', '2026-03-02', ATT.PRESENT),
      rec('a', '2026-03-03', ATT.ABSENT),
      rec('b', '2026-03-02', ATT.PRESENT)
    ], (r) => r.student_id)
    expect(map.get('a').rate).toBe(50)
    expect(map.get('b').rate).toBe(100)
  })
})

describe('연속 결석', () => {
  it('가장 최근 날짜부터 연속된 결석만 센다', () => {
    const recs = [
      rec('a', '2026-03-02', ATT.ABSENT),
      rec('a', '2026-03-09', ATT.PRESENT),
      rec('a', '2026-03-16', ATT.ABSENT),
      rec('a', '2026-03-23', ATT.ABSENT)
    ]
    expect(currentAbsentStreak(recs)).toBe(2)
  })

  it('마지막이 출석이면 0', () => {
    expect(currentAbsentStreak([rec('a', '2026-03-02', ATT.ABSENT), rec('a', '2026-03-03', ATT.PRESENT)])).toBe(0)
  })

  it('입력 순서와 무관하게 날짜 기준으로 판단한다', () => {
    const shuffled = [
      rec('a', '2026-03-23', ATT.ABSENT),
      rec('a', '2026-03-02', ATT.ABSENT),
      rec('a', '2026-03-16', ATT.ABSENT)
    ]
    expect(currentAbsentStreak(shuffled)).toBe(3)
  })
})

describe('isPresent', () => {
  it('결석만 false', () => {
    expect(isPresent(ATT.ABSENT)).toBe(false)
    for (const s of [ATT.PRESENT, ATT.LATE, ATT.MAKEUP, ATT.EARLY]) expect(isPresent(s)).toBe(true)
  })
})
