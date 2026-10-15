/**
 * 명단 표에서 방금 고치신 것 되돌리기.
 *
 * 붙여넣기는 통째로 되돌릴 수 있게 해 두었는데, 정작 더 자주 일어나는 사고는
 * 표에서다. 이름 칸을 지우고 다른 이름을 치다가 엉뚱한 줄을 고치신다.
 * 화면에는 아무 표시도 안 나므로 **고치신 줄이 어디였는지도 잊으신다.**
 *
 * 그래서 고치실 때마다 "무엇을 무엇에서 무엇으로" 를 쌓아 둔다.
 * 열 번까지만 — 그보다 더 거슬러 올라가시는 일은 없고, 길면 오히려 겁이 난다.
 */
import { LEVEL_LABEL, type Level } from '@/lib/types'

export const EDIT_KEEP = 10

export interface RosterEdit {
  student_id: string
  student_name: string
  /** 고친 칸 이름 (student_name · piece_title …) — 화면에 보여 드리는 이름이다 */
  field: string
  before: unknown
  after: unknown
  /**
   * 한 번에 두 칸이 함께 바뀌는 곳이 있다(사진을 고르면 대표 사진과 목록이 같이 바뀐다).
   * 그럴 때 되돌릴 것 전부를 여기 담는다. 없으면 field 하나만 되돌린다.
   */
  restore?: Record<string, unknown>
}

/** 칸 이름을 원장님이 화면에서 보시는 낱말로 */
export const FIELD_LABEL: Record<string, string> = {
  student_name: '이름',
  piece_title: '연주곡',
  composer: '작곡가',
  duration_sec: '소요시간',
  level: '난이도',
  note: '특징 메모',
  photo_asset_id: '사진',
  photo_asset_ids: '사진',
}

export function fieldLabel(field: string): string {
  return FIELD_LABEL[field] ?? field
}

/**
 * 새 고침을 쌓는다.
 *
 * 값이 그대로면 쌓지 않는다 — 칸을 눌렀다 그냥 빠져나오신 것도 저장으로 들어오는데,
 * 그런 것까지 쌓이면 [되돌리기] 를 눌러도 아무 일이 안 일어난다.
 */
export function pushEdit(log: RosterEdit[], edit: RosterEdit): RosterEdit[] {
  if (same(edit.before, edit.after)) return log
  return [edit, ...log].slice(0, EDIT_KEEP)
}

function same(a: unknown, b: unknown): boolean {
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((v, i) => v === b[i])
  return (a ?? null) === (b ?? null)
}

/** 가장 최근 것을 꺼낸다 */
export function popEdit(log: RosterEdit[]): { edit: RosterEdit | null; rest: RosterEdit[] } {
  if (log.length === 0) return { edit: null, rest: log }
  return { edit: log[0], rest: log.slice(1) }
}

/** 되돌릴 때 서버로 보낼 것 */
export function restorePatch(edit: RosterEdit): Record<string, unknown> {
  return edit.restore ?? { [edit.field]: edit.before }
}

/** 화면에 적을 한 줄 — "김서연 · 연주곡 을 되돌립니다" */
export function describeEdit(edit: RosterEdit): string {
  return `${edit.student_name} · ${fieldLabel(edit.field)}`
}

/** 무엇에서 무엇으로 바뀌었는지 — 되돌리기 전에 보여 드린다 */
export function describeChange(edit: RosterEdit): string {
  return `${valueText(edit.field, edit.after)} → ${valueText(edit.field, edit.before)}`
}

function valueText(field: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '(빈칸)'
  if (field === 'level') return LEVEL_LABEL[value as Level] ?? String(value)
  if (field === 'duration_sec') {
    const sec = Number(value)
    if (!Number.isFinite(sec) || sec <= 0) return '(빈칸)'
    return `${Math.floor(sec / 60)}분 ${sec % 60}초`
  }
  if (Array.isArray(value)) return `${value.length}장`
  const text = String(value)
  return text.length > 20 ? `${text.slice(0, 20)}…` : text
}
