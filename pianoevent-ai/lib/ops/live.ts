import type { EventStudent, ProgramPlan } from '@/lib/types'

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
 * 넘긴 시각을 하나씩 적어 두면 두 가지가 더 된다.
 *   · 스태프 여러 명이 **같은 화면**을 볼 수 있다 (한 사람이 넘기면 나머지가 따라간다)
 *   · 곡이 **실제로 몇 분 걸렸는지** 남아, 다음 해 순서표가 그 학원 아이들에 맞게 된다
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
  planned_sec: number
  /** 이 줄에 해당하는 학생 (휴식은 없다) — 실제 시간을 명단에 되돌릴 때 쓴다 */
  student_id: string | null
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
        planned_sec: brk.duration_sec,
        student_id: null,
      })
    }
    out.push({
      id: item.student.id,
      kind: 'item',
      order_no: item.order_no,
      title: item.student.student_name,
      detail: [item.student.piece_title, item.student.composer].filter(Boolean).join(' · '),
      planned_offset_sec: item.start_offset_sec,
      planned_sec: item.duration_sec,
      student_id: item.student.id,
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

/**
 * 진행 상태.
 *
 * 새로고침해도 잃지 않도록 휴대폰에 담고, 함께 보기를 켜면 서버에도 올린다.
 * `marks[i]` 는 **i 번째 순서로 넘어간 시각**(epoch ms)이다. marks[0] 은 개회 시각.
 */
export interface LiveState {
  /** 지금 몇 번째 줄인가 */
  index: number
  /** 개회를 누른 시각 (epoch ms). 아직 시작 전이면 null */
  started_at: number | null
  /** 각 순서로 넘어간 시각. 넘긴 만큼만 쌓인다 */
  marks: number[]
  /** 마지막으로 손댄 시각 — 함께 보기에서 어느 쪽이 최신인지 가른다 */
  updated_at: number
}

export const EMPTY_LIVE_STATE: LiveState = { index: 0, started_at: null, marks: [], updated_at: 0 }

export function liveStorageKey(eventId: string): string {
  return `pianoevent.live.${eventId}`
}

/** 담아 둔 상태를 되읽는다. 이상하면 처음부터 — 당일에 오류 화면을 볼 수는 없다 */
export function parseLiveState(raw: string | null, total: number): LiveState {
  if (!raw) return EMPTY_LIVE_STATE
  try {
    return normalizeLiveState(JSON.parse(raw), total)
  } catch {
    return EMPTY_LIVE_STATE
  }
}

const stamp = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) && value > 0 ? Math.round(value) : null

/**
 * 어디서 왔든(휴대폰 · 서버) 믿을 수 있는 모양으로 다듬는다.
 * 순서표가 짧아졌으면 마지막 순서로 당겨 온다 — 빈 화면이 뜨지 않게.
 *
 * `total` 을 주지 않으면 길이는 건드리지 않는다. 서버가 그저 값을 넘겨 주기만 할 때는
 * 순서표를 다시 계산할 이유가 없다 — 화면 쪽에서 제 목록 길이로 한 번 더 다듬는다.
 */
export function normalizeLiveState(input: unknown, total?: number): LiveState {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return EMPTY_LIVE_STATE
  const source = input as Record<string, unknown>
  const limit = total === undefined ? Number.MAX_SAFE_INTEGER : Math.max(0, total - 1)
  const index =
    typeof source.index === 'number' && Number.isFinite(source.index)
      ? Math.min(Math.max(0, Math.floor(source.index)), limit)
      : 0
  const started = stamp(source.started_at)
  // 넘긴 시각은 늘 앞에서 뒤로 흐른다. 거꾸로 간 값이 나오면 거기서 끊는다
  const marks: number[] = []
  if (Array.isArray(source.marks)) {
    for (const raw of source.marks) {
      const value = stamp(raw)
      if (value === null) break
      if (marks.length > 0 && value < marks[marks.length - 1]) break
      marks.push(value)
      if (total !== undefined && marks.length >= Math.max(0, total)) break
    }
  }
  return {
    index,
    started_at: started,
    marks: started === null ? [] : marks,
    updated_at: stamp(source.updated_at) ?? 0,
  }
}

/** 두 상태 중 나중 것 — 함께 보기에서 서버와 내 휴대폰을 견줄 때 */
export function newerLiveState(a: LiveState, b: LiveState): LiveState {
  return b.updated_at > a.updated_at ? b : a
}

/** 지금 이 순서가 시작된 시각 */
export function startedAtIndex(state: LiveState, index: number): number | null {
  return state.marks[index] ?? (index === 0 ? state.started_at : null)
}

/** 이 순서를 시작한 지 몇 초 지났는가 */
export function elapsedAtIndex(state: LiveState, index: number, now: number): number {
  const from = startedAtIndex(state, index)
  return from === null ? 0 : Math.max(0, (now - from) / 1000)
}

/** 개회한 지 몇 초 지났는가 */
export function elapsedTotal(state: LiveState, now: number): number {
  return state.started_at === null ? 0 : Math.max(0, (now - state.started_at) / 1000)
}

/**
 * 한 순서를 넘긴다. 넘긴 시각을 적어 두어야 실제로 몇 분 걸렸는지 남는다.
 * 되돌아갈 때는 그 뒤에 적어 둔 시각을 지운다 — 잘못 눌렀다는 뜻이니까.
 */
export function moveLive(state: LiveState, next: number, now: number, total: number): LiveState {
  const index = Math.min(Math.max(0, next), Math.max(0, total - 1))
  if (state.started_at === null) return { ...state, index, updated_at: now }
  // 되돌아가면 그 뒤에 적어 둔 시각만 지운다. **이미 지나온 순서의 시각은 그대로 둔다** —
  // 잘못 눌러 되돌아갔다고 앞 곡이 실제로 더 오래 걸린 것이 되면 안 된다
  const marks = state.marks.slice(0, index + 1)
  // 아직 지나오지 않은 자리로 건너뛰면 그 사이는 지금 시각으로 메운다 (건너뛴 순서는 0초로 남아 걸러진다)
  while (marks.length <= index) marks.push(now)
  return { index, started_at: state.started_at, marks, updated_at: now }
}

/** 개회 — 시계를 켠다 */
export function startLive(now: number): LiveState {
  return { index: 0, started_at: now, marks: [now], updated_at: now }
}

/** 실제로 몇 초 걸렸는가 — 끝난 순서만 (지금 진행 중인 것은 아직 모른다) */
export function actualSeconds(state: LiveState, index: number): number | null {
  const from = state.marks[index]
  const to = state.marks[index + 1]
  if (from === undefined || to === undefined || to < from) return null
  return (to - from) / 1000
}

export interface ActualRow {
  entry: LiveEntry
  actual_sec: number
  planned_sec: number
  /** 명단에 되돌릴 만한 값인가 — 너무 짧거나 긴 것은 잘못 누른 것으로 본다 */
  usable: boolean
}

/** 실제로 걸린 시간이 말이 되는 범위인가 (20초 ~ 20분) */
export const ACTUAL_MIN_SEC = 20
export const ACTUAL_MAX_SEC = 20 * 60

/**
 * 끝난 순서들의 실제 시간.
 *
 * 리허설이나 연주회에서 한 번 돌려 두면, 다음 해 순서표의 예상 시간이
 * **그 학원 아이들** 에 맞게 된다. 책에 적힌 평균이 아니라.
 */
export function actualRows(list: LiveEntry[], state: LiveState): ActualRow[] {
  const out: ActualRow[] = []
  for (let i = 0; i < list.length; i += 1) {
    const seconds = actualSeconds(state, i)
    if (seconds === null) continue
    out.push({
      entry: list[i],
      actual_sec: Math.round(seconds),
      planned_sec: list[i].planned_sec,
      usable:
        list[i].kind === 'item' &&
        list[i].student_id !== null &&
        seconds >= ACTUAL_MIN_SEC &&
        seconds <= ACTUAL_MAX_SEC,
    })
  }
  return out
}

/** 명단에 되돌릴 값만 추린다 — 예정과 10초 넘게 차이 나는 것만 (같으면 고칠 이유가 없다) */
export function durationUpdates(rows: ActualRow[], gapSec = 10): { student_id: string; duration_sec: number }[] {
  return rows
    .filter((row) => row.usable && Math.abs(row.actual_sec - row.planned_sec) > gapSec)
    .map((row) => ({ student_id: row.entry.student_id as string, duration_sec: row.actual_sec }))
}

/** "12곡 중 9곡을 마쳤습니다" 처럼 진행 상황 한 줄 */
export function progressLabel(list: LiveEntry[], state: LiveState): string {
  const done = list.filter((_, index) => actualSeconds(state, index) !== null).length
  return `${list.length}개 중 ${done}개를 마쳤습니다`
}

/** 명단에 되돌릴 때 쓰는 이름 — 학생 id → 실제 초 */
export function durationsByStudent(rows: ActualRow[]): Record<string, number> {
  const out: Record<string, number> = {}
  for (const row of rows) {
    if (row.usable && row.entry.student_id) out[row.entry.student_id] = row.actual_sec
  }
  return out
}

/** 이 학생의 실제 시간을 명단에 되돌릴 수 있게 이름과 함께 (화면에 보여 줄 용) */
export function namedDurations(
  rows: ActualRow[],
  students: Pick<EventStudent, 'id' | 'student_name' | 'duration_sec'>[],
): { id: string; name: string; before: number; after: number }[] {
  const byId = new Map(students.map((student) => [student.id, student]))
  return durationUpdates(rows).flatMap((update) => {
    const student = byId.get(update.student_id)
    if (!student) return []
    return [{ id: student.id, name: student.student_name, before: student.duration_sec, after: update.duration_sec }]
  })
}

/**
 * 따라보기 열쇠.
 *
 * 따라보기 화면(`/e/{id}/live`)은 초대장과 같은 자리에 있다. 거기에 뜨는 것은
 * 초대장에 이미 있는 이름과 곡뿐이지만, **누가 보는지는 원장님이 정하셔야 한다.**
 * 코드를 켜 두면 그 코드를 아는 화면만 따라온다.
 *
 * 비밀번호가 아니다. 스태프가 한 번 열고 마는 화면의 문고리다 —
 * 화면에도 그렇게 적어 둔다.
 */

/** 헷갈리는 글자를 뺀다 — 무대 옆에서 손으로 옮겨 적을 수도 있다 (0/O, 1/I/L) */
export const LIVE_CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
export const LIVE_CODE_LENGTH = 6

export function makeLiveCode(random: () => number = Math.random): string {
  let out = ''
  for (let i = 0; i < LIVE_CODE_LENGTH; i += 1) {
    out += LIVE_CODE_ALPHABET[Math.floor(random() * LIVE_CODE_ALPHABET.length) % LIVE_CODE_ALPHABET.length]
  }
  return out
}

/** 받아 둘 만한 코드인가 — 대문자로 맞추고 아는 글자만 남긴다 */
export function normalizeLiveCode(input: unknown): string | null {
  if (typeof input !== 'string') return null
  const cleaned = input
    .toUpperCase()
    .split('')
    .filter((ch) => LIVE_CODE_ALPHABET.includes(ch))
    .join('')
  return cleaned.length >= 4 && cleaned.length <= 12 ? cleaned : null
}

/** 이 화면이 따라볼 수 있는가. 코드를 걸어 두지 않았으면 누구나 볼 수 있다 */
export function liveCodeAllows(stored: string | null | undefined, given: unknown): boolean {
  if (!stored) return true
  return normalizeLiveCode(given) === stored
}
