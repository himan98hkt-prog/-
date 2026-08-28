import type { ProgramPlan } from '@/lib/types'

/**
 * 당일 진행 화면 — 스태프 휴대폰에 드는 것.
 *
 * 연주회 당일 무대 옆에는 종이 순서표를 든 사람이 서 있다. 종이에는
 * "지금 몇 번째인지" 가 적혀 있지 않다. 누가 손가락으로 짚고 있어야 하고,
 * 한 번 놓치면 다음 아이를 잘못 부른다.
 *
 * 그래서 지금·다음·그다음만 크게 띄우고, 넘기는 단추 하나만 둔다.
 * 예정 시각과 견주어 몇 분 밀렸는지도 함께 — 그걸 알아야 사회자가 멘트를 줄인다.
 *
 * 이 파일은 순수 계산만 한다.
 */

export interface LiveEntry {
  id: string
  kind: 'item' | 'break'
  /** 연주 순번. 휴식은 null */
  order_no: number | null
  /** 크게 뜨는 글자 — 아이 이름 또는 "중간 휴식" */
  title: string
  /** 그 아래 한 줄 — 곡과 작곡가 */
  detail: string
  /** 개회 기준 예정 시각(초) */
  planned_offset_sec: number
  duration_sec: number
}

/** 순서표를 그대로 한 줄씩 늘어놓는다 — 휴식도 한 자리를 차지한다 */
export function buildLiveList(plan: ProgramPlan): LiveEntry[] {
  const out: LiveEntry[] = []
  const breaksByOrder = new Map(plan.breaks.map((b) => [b.after_order_no, b]))

  for (const item of plan.items) {
    const brk = breaksByOrder.get(item.order_no - 1)
    if (brk) {
      out.push({
        id: `break-${brk.after_order_no}`,
        kind: 'break',
        order_no: null,
        title: brk.label,
        detail: `${Math.round(brk.duration_sec / 60)}분`,
        planned_offset_sec: brk.start_offset_sec,
        duration_sec: brk.duration_sec,
      })
    }
    out.push({
      id: item.student.id,
      kind: 'item',
      order_no: item.order_no,
      title: item.student.student_name,
      detail: [item.student.piece_title, item.student.composer].filter(Boolean).join(' · '),
      planned_offset_sec: item.start_offset_sec,
      duration_sec: item.duration_sec,
    })
  }
  return out
}

/**
 * 예정보다 얼마나 밀렸는가.
 *
 * 1분 미만은 "예정대로" 라고 말한다 — 초 단위로 흔들리는 숫자를 보여 주면
 * 무대 옆에 선 사람이 불안해진다.
 */
export function driftLabel(actualSec: number, plannedSec: number): string {
  const diff = Math.round((actualSec - plannedSec) / 60)
  if (diff === 0) return '예정대로'
  return diff > 0 ? `예정보다 ${diff}분 늦음` : `예정보다 ${-diff}분 빠름`
}

/** 밀림이 문제가 될 만한가 — 화면 색을 바꿀지 정한다 */
export function driftLevel(actualSec: number, plannedSec: number): 'ok' | 'warn' | 'late' {
  const diff = (actualSec - plannedSec) / 60
  if (diff >= 10) return 'late'
  if (diff >= 4) return 'warn'
  return 'ok'
}

/** 초 → "12:04" (경과 시간 표시용) */
export function formatElapsed(sec: number): string {
  const total = Math.max(0, Math.floor(sec))
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

/** 진행 상태 — 새로고침해도 잃지 않도록 브라우저에 담아 둔다 */
export interface LiveState {
  /** 지금 몇 번째 줄인가 */
  index: number
  /** 개회를 누른 시각 (epoch ms). 아직 시작 전이면 null */
  started_at: number | null
}

export const EMPTY_LIVE_STATE: LiveState = { index: 0, started_at: null }

export function liveStorageKey(eventId: string): string {
  return `pianoevent.live.${eventId}`
}

/** 담아 둔 상태를 되읽는다. 이상하면 처음부터 — 당일에 오류 화면을 볼 수는 없다 */
export function parseLiveState(raw: string | null, total: number): LiveState {
  if (!raw) return EMPTY_LIVE_STATE
  try {
    const parsed = JSON.parse(raw) as Partial<LiveState>
    const index =
      typeof parsed.index === 'number' && Number.isFinite(parsed.index)
        ? Math.min(Math.max(0, Math.floor(parsed.index)), Math.max(0, total - 1))
        : 0
    const started =
      typeof parsed.started_at === 'number' && Number.isFinite(parsed.started_at) ? parsed.started_at : null
    return { index, started_at: started }
  } catch {
    return EMPTY_LIVE_STATE
  }
}
