import { describe, it, expect } from 'vitest'
import { monthlyRegister, ATT_LABELS } from '../src/core/register.js'

const roster = [{ id: 's1', name: '김하늘' }, { id: 's2', name: '이바다' }]
const records = [
  { student_id: 's1', date: '2026-03-02', status: '출석' },
  { student_id: 's1', date: '2026-03-09', status: '결석' },
  { student_id: 's1', date: '2026-03-16', status: '지각' },
  { student_id: 's2', date: '2026-03-02', status: '출석' },
  { student_id: 's2', date: '2026-03-16', status: '출석' }
]

describe('월간 출석부', () => {
  const table = monthlyRegister({ month: '2026-03', roster, records })

  it('수업이 있었던 날짜만 열로 만든다', () => {
    expect(table.days).toEqual(['02', '09', '16'])
    expect(table.headers).toEqual(['원생', '2', '9', '16', '출석', '결석', '출석률'])
  })

  it('상태를 한 글자 기호로 찍는다', () => {
    expect(table.rows[0].slice(1, 4)).toEqual([ATT_LABELS['출석'], ATT_LABELS['결석'], ATT_LABELS['지각']])
  })

  it('기록이 없는 칸은 비운다', () => {
    expect(table.rows[1][2]).toBe('')
  })

  it('지각·조퇴는 출석으로 세고 출석률을 낸다', () => {
    expect(table.rows[0].slice(-3)).toEqual(['2', '1', '67%'])
    expect(table.rows[1].slice(-3)).toEqual(['2', '0', '100%'])
  })

  it('기록이 하나도 없으면 그 달 전체 날짜를 보여 준다', () => {
    const empty = monthlyRegister({ month: '2026-02', roster, records: [] })
    expect(empty.days).toHaveLength(28)
    expect(empty.rows[0].slice(-3)).toEqual(['0', '0', '-'])
  })
})
