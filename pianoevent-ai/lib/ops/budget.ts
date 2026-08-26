import type { EventRecord } from '@/lib/types'

/**
 * 연주회 예산·정산.
 *
 * 원장이 매번 다시 만드는 두 번째 문서. "참가비를 얼마 받아야 하나"는
 * 대관료가 확정되기 전에는 답이 안 나오는데, 안내는 그보다 먼저 나가야 한다.
 * 항목별 단가와 인원만 넣으면 총액과 1인당 원가, 권장 참가비가 바로 나오게 한다.
 *
 * 금액은 전부 원(KRW) 단위 정수로 다룬다.
 */

/** 무엇에 비례해 늘어나는 비용인지 */
export type BudgetBasis = 'fixed' | 'per_student' | 'per_family' | 'per_guest'

export const BASIS_LABEL: Record<BudgetBasis, string> = {
  fixed: '고정',
  per_student: '학생 1인당',
  per_family: '가정 1곳당',
  per_guest: '관객 1인당',
}

export interface BudgetItem {
  id: string
  label: string
  /** 원장이 금액을 판단할 수 있게 남기는 한 줄 */
  note: string
  basis: BudgetBasis
  unit_cost: number
  /** basis 가 fixed 일 때의 수량 */
  qty: number
  /** 끄고 켤 수 있는 항목인지 */
  optional: boolean
}

/**
 * 기본 항목과 단가. 2026년 기준 중소도시 학원 연주회의 통상 범위를 담았다.
 * 지역·규모에 따라 달라지므로 원장이 고치는 것을 전제로 한다.
 */
export const DEFAULT_BUDGET_ITEMS: BudgetItem[] = [
  { id: 'venue', label: '대관료', note: '4시간 기준. 구민회관·아트홀은 반나절 단위가 많습니다.', basis: 'fixed', unit_cost: 400_000, qty: 1, optional: false },
  { id: 'tuning', label: '피아노 조율', note: '공연 전날 또는 당일 오전. 홀 피아노는 대개 별도입니다.', basis: 'fixed', unit_cost: 120_000, qty: 1, optional: false },
  { id: 'sound', label: '음향·조명 오퍼레이터', note: '홀 자체 인력이 있으면 0원인 경우도 있습니다.', basis: 'fixed', unit_cost: 150_000, qty: 1, optional: true },
  { id: 'photo', label: '사진·영상 촬영', note: '반일 촬영 + 보정본 전달 기준.', basis: 'fixed', unit_cost: 350_000, qty: 1, optional: true },
  { id: 'print', label: '인쇄물', note: '포스터·프로그램·입장권·이름표. 이 프로그램에서 바로 뽑으면 실비만 듭니다.', basis: 'per_family', unit_cost: 1_500, qty: 1, optional: false },
  { id: 'flower', label: '꽃다발·코사지', note: '전원에게 줄지, 피날레 연주자만 줄지 먼저 정하세요.', basis: 'per_student', unit_cost: 8_000, qty: 1, optional: true },
  { id: 'award', label: '상장·부상', note: '상장은 인쇄하고 부상만 구입하면 절반으로 줄어듭니다.', basis: 'per_student', unit_cost: 5_000, qty: 1, optional: false },
  { id: 'snack', label: '간식·음료', note: '대기실 학생용. 관객 배포는 홀 규정을 확인하세요.', basis: 'per_student', unit_cost: 3_000, qty: 1, optional: true },
  { id: 'banner', label: '현수막·포토존', note: '현수막은 재사용하면 연도만 바꿔 다시 씁니다.', basis: 'fixed', unit_cost: 80_000, qty: 1, optional: true },
  { id: 'staff', label: '진행 보조 인건비', note: '접수·안내 2명 기준 반일.', basis: 'fixed', unit_cost: 160_000, qty: 1, optional: true },
]

export interface BudgetInput {
  students: number
  /** 참석 가정 수 — RSVP 집계에서 가져온다 */
  families: number
  /** 관객 총원 — RSVP 인원 합계 */
  guests: number
  items: BudgetItem[]
  /** 학원이 부담할 금액. 나머지를 참가비로 걷는다 */
  academy_share: number
}

export interface BudgetLine {
  item: BudgetItem
  /** 실제 곱해진 수량 */
  qty: number
  amount: number
}

export interface BudgetResult {
  lines: BudgetLine[]
  total: number
  /** 학원 부담을 뺀, 학부모에게 걷어야 할 금액 */
  collect: number
  /** 학생 1인당 원가 */
  per_student: number
  /** 1,000원 단위로 올림한 권장 참가비 */
  suggested_fee: number
  /** 권장 참가비로 걷었을 때 남는 금액 */
  margin: number
  warnings: string[]
}

function qtyFor(item: BudgetItem, input: BudgetInput): number {
  switch (item.basis) {
    case 'per_student':
      return input.students
    case 'per_family':
      return input.families
    case 'per_guest':
      return input.guests
    default:
      return item.qty
  }
}

export function buildBudget(input: BudgetInput): BudgetResult {
  const lines: BudgetLine[] = input.items.map((item) => {
    const qty = qtyFor(item, input)
    return { item, qty, amount: Math.round(item.unit_cost * qty) }
  })

  const total = lines.reduce((sum, line) => sum + line.amount, 0)
  const collect = Math.max(0, total - Math.max(0, input.academy_share))
  const students = Math.max(1, input.students)
  const perStudent = Math.round(collect / students)
  const suggested = Math.ceil(perStudent / 1000) * 1000
  const margin = suggested * students - collect

  const warnings: string[] = []
  if (input.students === 0) {
    warnings.push('학생 수가 0명입니다. 명단을 먼저 등록하면 1인당 금액이 계산됩니다.')
  }
  if (suggested > 50_000) {
    warnings.push(
      `권장 참가비가 ${suggested.toLocaleString()}원입니다. 5만원을 넘으면 문의가 늘어납니다. ` +
        '학원 부담을 늘리거나 촬영·꽃다발 같은 선택 항목을 빼 보세요.',
    )
  }
  // 소규모 학원에서 1인당이 튀는 진짜 원인은 대관료 같은 고정비다. 그걸 이름으로 짚어 준다.
  const fixedTotal = lines.filter((l) => l.item.basis === 'fixed').reduce((s, l) => s + l.amount, 0)
  if (total > 0 && input.students > 0 && input.students < 20 && fixedTotal / total > 0.6) {
    warnings.push(
      `고정비가 전체의 ${Math.round((fixedTotal / total) * 100)}%입니다. 학생 ${input.students}명으로 나누면 1인당이 클 수밖에 없습니다. ` +
        '학원 홀에서 열거나 촬영을 학부모 촬영으로 대체하면 가장 크게 줄어듭니다.',
    )
  }

  const optionalTotal = lines.filter((l) => l.item.optional).reduce((s, l) => s + l.amount, 0)
  if (total > 0 && optionalTotal / total > 0.45) {
    warnings.push('선택 항목이 전체의 45%를 넘습니다. 무엇을 뺄지 미리 정해 두면 대관료가 오를 때 조정할 여지가 생깁니다.')
  }
  if (input.families > 0 && input.guests / input.families > 4) {
    warnings.push('가정당 관객이 4명을 넘습니다. 좌석과 간식 수량을 다시 확인하세요.')
  }

  return { lines, total, collect, per_student: perStudent, suggested_fee: suggested, margin, warnings }
}

export function formatWon(value: number): string {
  return `${Math.round(value).toLocaleString('ko-KR')}원`
}

/** 학부모에게 보내는 참가비 안내 문구 */
export function feeNoticeMessage(event: EventRecord, result: BudgetResult, academyName: string): string {
  return [
    `[${academyName}] ${event.title} 참가비 안내`,
    '',
    `참가비 · ${formatWon(result.suggested_fee)} (학생 1인)`,
    '포함 · 대관, 조율, 인쇄물, 상장, 기념 촬영',
    '',
    '납부해 주시면 좌석과 프로그램을 준비해 두겠습니다.',
    '사정이 어려우신 경우 편하게 말씀해 주세요. 조정해 드립니다.',
  ].join('\n')
}
