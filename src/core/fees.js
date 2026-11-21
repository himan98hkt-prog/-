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

// ── 할인 정책과 청구 계산 ───────────────────────────────────
// 원장이 매달 계산기로 두드리던 형제 할인·개인 할인을 규칙으로 굳힌다.
// 규칙을 여기 모아 두면 "왜 이 금액이 나왔는지" 를 청구서에 그대로 적어 줄 수 있다.

export const DEFAULT_BILLING = {
  dueDay: 10,              // 납부 기준일 — 이 날이 지나야 미납 독촉 대상이 된다
  roundUnit: 100,          // 최종 금액 절사 단위
  sibling: {
    enabled: false,
    type: 'percent',       // 'percent' | 'amount'
    value: 10,
    applyTo: 'all'         // 'all' = 형제 전원, 'others' = 첫째를 뺀 나머지
  }
}

export function billingPolicy(saved) {
  const s = saved || {}
  return { ...DEFAULT_BILLING, ...s, sibling: { ...DEFAULT_BILLING.sibling, ...(s.sibling || {}) } }
}

function discountAmount(rule, base) {
  if (!rule) return 0
  const value = Number(rule.value) || 0
  if (value <= 0) return 0
  const raw = rule.type === 'amount' ? value : (base * value) / 100
  return Math.min(base, Math.round(raw))
}

/**
 * 원생 한 명의 이번 달 청구액.
 * @param {object} opts
 * @param {object} opts.student            student.discount = {type,value,memo} 로 개인 할인
 * @param {Array}  opts.enrollments        이 원생의 유효 수강 내역
 * @param {Map}    opts.classMap           class_id -> class
 * @param {object} [opts.policy]           billingPolicy()
 * @param {number} [opts.siblingCount]     형제 그룹 인원(본인 포함)
 * @param {boolean}[opts.isFirstSibling]   형제 중 첫째인지 (applyTo:'others' 에서만 씀)
 * @returns {{base:number, total:number, lines:Array, discount:number}}
 */
export function computeBill({ student = {}, enrollments = [], classMap = new Map(), policy, siblingCount = 1, isFirstSibling = false }) {
  const p = billingPolicy(policy)
  const lines = []
  let base = 0
  for (const e of enrollments) {
    const cls = classMap.get(e.class_id)
    const amount = e.fee_override != null && e.fee_override !== ''
      ? Number(e.fee_override) || 0
      : Number(cls?.fee) || 0
    if (!amount) continue
    base += amount
    lines.push({ label: cls?.name || '수강', amount })
  }
  if (!base) return { base: 0, total: 0, discount: 0, lines }

  let discount = 0
  if (p.sibling.enabled && siblingCount >= 2 && !(p.sibling.applyTo === 'others' && isFirstSibling)) {
    const amt = discountAmount(p.sibling, base)
    if (amt) { discount += amt; lines.push({ label: `형제 할인(${siblingCount}명)`, amount: -amt }) }
  }
  const own = student.discount
  if (own && Number(own.value) > 0) {
    const amt = discountAmount(own, base)
    if (amt) { discount += amt; lines.push({ label: own.memo ? `할인 · ${own.memo}` : '개인 할인', amount: -amt }) }
  }

  const unit = Math.max(1, Number(p.roundUnit) || 1)
  const total = Math.max(0, Math.floor((base - discount) / unit) * unit)
  return { base, total, discount: base - total, lines }
}

/** 납부 기한 대비 연체 일수 (0 이하면 아직 기한 전) */
export function overdueDays(month, today, dueDay = DEFAULT_BILLING.dueDay) {
  const due = `${month}-${String(dueDay).padStart(2, '0')}`
  const [y1, m1, d1] = due.split('-').map(Number)
  const [y2, m2, d2] = String(today).split('-').map(Number)
  return Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86400000)
}
