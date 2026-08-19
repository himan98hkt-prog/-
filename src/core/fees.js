// 수납 계산 — 손절성 버그가 잦았던 영역이라 순수 함수로 분리하고 단위 테스트로 고정한다.
//
// payment 레코드 형태:
//   { id, academy_id, student_id, month:'2026-03', amount(청구총액), method,
//     paid_at, status, installments: [{ seq, due_date, amount, paid_at, method }] }
// installments 가 비어 있으면 "일시납"으로 보고 paid_at 유무로 완납/미납을 판정한다.

export const PAY_STATUS = { FULL: '완납', PARTIAL: '부분', UNPAID: '미납' }

export function paidAmountOf(payment) {
  const inst = payment?.installments
  if (Array.isArray(inst) && inst.length) {
    return inst.reduce((s, i) => s + (i.paid_at ? Number(i.amount) || 0 : 0), 0)
  }
  return payment?.paid_at ? Number(payment.amount) || 0 : 0
}

export function statusOf(payment) {
  const amount = Number(payment?.amount) || 0
  const paid = paidAmountOf(payment)
  if (amount <= 0) return PAY_STATUS.FULL
  if (paid <= 0) return PAY_STATUS.UNPAID
  return paid >= amount ? PAY_STATUS.FULL : PAY_STATUS.PARTIAL
}

/** 화면·집계용 파생값을 붙여 돌려준다 (원본 불변) */
export function decorate(payment) {
  const amount = Number(payment?.amount) || 0
  const paid = paidAmountOf(payment)
  return {
    ...payment,
    amount,
    paid,
    remaining: Math.max(0, amount - paid),
    overpaid: Math.max(0, paid - amount),
    status: statusOf(payment)
  }
}

/**
 * 분할납부 계산기.
 * 총액을 count회로 쪼개되 unit(기본 10원) 단위로 맞추고, 딱 떨어지지 않는 차액은 1회차에 몰아준다.
 * (학원 현장에서 "마지막 회차가 이상한 금액"이 되는 것보다 첫 회차가 조금 큰 쪽이 설명하기 쉽다)
 */
export function splitInstallments(total, count, opts = {}) {
  const { unit = 10, dueDates = [] } = opts
  const amount = Math.max(0, Math.round(Number(total) || 0))
  const n = Math.max(1, Math.floor(count))
  if (n === 1) return [{ seq: 1, amount, due_date: dueDates[0] || null, paid_at: null, method: null }]

  const per = Math.floor(amount / n / unit) * unit
  const rows = []
  for (let i = 0; i < n; i++) {
    rows.push({ seq: i + 1, amount: per, due_date: dueDates[i] || null, paid_at: null, method: null })
  }
  const diff = amount - per * n
  rows[0].amount += diff
  return rows
}

/** 월 마감 도우미: 청구/수납/미납/지출/순이익 */
export function settleMonth(payments = [], expenses = []) {
  let billed = 0
  let collected = 0
  let unpaidCount = 0
  let partialCount = 0
  for (const raw of payments) {
    const p = decorate(raw)
    billed += p.amount
    collected += p.paid
    if (p.status === PAY_STATUS.UNPAID) unpaidCount++
    else if (p.status === PAY_STATUS.PARTIAL) partialCount++
  }
  const spent = expenses.reduce((s, e) => s + (Number(e.amount) || 0), 0)
  return {
    billed,
    collected,
    outstanding: Math.max(0, billed - collected),
    collectRate: billed ? Math.round((collected / billed) * 1000) / 10 : 0,
    unpaidCount,
    partialCount,
    expense: spent,
    net: collected - spent
  }
}

/** 수강 내역 기준 이달 청구액 (fee_override 우선, 없으면 반 수강료) */
export function billableFor(enrollments = [], classMap = new Map()) {
  return enrollments.reduce((sum, e) => {
    if (e.fee_override != null && e.fee_override !== '') return sum + (Number(e.fee_override) || 0)
    const cls = classMap.get(e.class_id)
    return sum + (Number(cls?.fee) || 0)
  }, 0)
}

export function formatWon(n) {
  return `${Math.round(Number(n) || 0).toLocaleString('ko-KR')}원`
}
