import { describe, it, expect } from 'vitest'
import { splitInstallments, decorate, statusOf, settleMonth, billableFor, PAY_STATUS } from '../src/core/fees.js'

describe('수납 상태 판정', () => {
  it('일시납은 paid_at 유무로 완납/미납', () => {
    expect(statusOf({ amount: 150000, paid_at: '2026-03-05' })).toBe(PAY_STATUS.FULL)
    expect(statusOf({ amount: 150000, paid_at: null })).toBe(PAY_STATUS.UNPAID)
  })

  it('분할납부는 납부된 회차 합계로 판정', () => {
    const p = {
      amount: 300000,
      installments: [
        { seq: 1, amount: 100000, paid_at: '2026-03-05' },
        { seq: 2, amount: 100000, paid_at: null },
        { seq: 3, amount: 100000, paid_at: null }
      ]
    }
    const d = decorate(p)
    expect(d.paid).toBe(100000)
    expect(d.remaining).toBe(200000)
    expect(d.status).toBe(PAY_STATUS.PARTIAL)
  })

  it('청구액 0원은 완납으로 본다(면제/장학)', () => {
    expect(statusOf({ amount: 0, paid_at: null })).toBe(PAY_STATUS.FULL)
  })

  it('과납이면 완납이고 overpaid 로 남는다', () => {
    const d = decorate({ amount: 100000, installments: [{ amount: 120000, paid_at: 'x' }] })
    expect(d.status).toBe(PAY_STATUS.FULL)
    expect(d.overpaid).toBe(20000)
    expect(d.remaining).toBe(0)
  })
})

describe('분할납부 계산기', () => {
  it('회차 합계는 언제나 총액과 일치한다', () => {
    for (const total of [100000, 150000, 250000, 333333, 99999, 1]) {
      for (const n of [1, 2, 3, 4, 5, 6, 7, 12]) {
        const rows = splitInstallments(total, n)
        expect(rows).toHaveLength(n)
        expect(rows.reduce((s, r) => s + r.amount, 0)).toBe(total)
      }
    }
  })

  it('나머지는 1회차에 몰아준다 (마지막 회차가 깔끔하게)', () => {
    const rows = splitInstallments(250000, 3)
    expect(rows.map((r) => r.amount)).toEqual([83340, 83330, 83330])
  })

  it('납기일을 순서대로 채운다', () => {
    const rows = splitInstallments(300000, 3, { dueDates: ['2026-03-05', '2026-04-05', '2026-05-05'] })
    expect(rows.map((r) => r.due_date)).toEqual(['2026-03-05', '2026-04-05', '2026-05-05'])
  })

  it('0회/음수는 1회로 보정한다', () => {
    expect(splitInstallments(100000, 0)).toHaveLength(1)
    expect(splitInstallments(100000, -3)).toHaveLength(1)
  })
})

describe('월 마감 집계', () => {
  it('청구/수납/미수/순이익을 계산한다', () => {
    const s = settleMonth(
      [
        { amount: 100000, paid_at: '2026-03-02' },
        { amount: 100000, installments: [{ amount: 50000, paid_at: 'x' }, { amount: 50000 }] },
        { amount: 100000, paid_at: null }
      ],
      [{ amount: 30000 }, { amount: 20000 }]
    )
    expect(s.billed).toBe(300000)
    expect(s.collected).toBe(150000)
    expect(s.outstanding).toBe(150000)
    expect(s.unpaidCount).toBe(1)
    expect(s.partialCount).toBe(1)
    expect(s.expense).toBe(50000)
    expect(s.net).toBe(100000)
    expect(s.collectRate).toBe(50)
  })
})

describe('수강 기준 청구액', () => {
  it('fee_override 가 반 수강료보다 우선한다', () => {
    const classMap = new Map([['c1', { fee: 150000 }], ['c2', { fee: 100000 }]])
    const amount = billableFor(
      [{ class_id: 'c1' }, { class_id: 'c2', fee_override: 80000 }],
      classMap
    )
    expect(amount).toBe(230000)
  })
})
