import type { EventStudent, ProgramItem } from '@/lib/types'

/**
 * 한 아이가 여러 번 무대에 서는 경우.
 *
 * 독주도 하고 듀엣도 하는 아이는 흔하다. 순서표에서는 **두 줄이 맞다** —
 * 무대에 두 번 오르니까. 그런데 명단 화면과 감동영상에서는 두 줄이 어색하다.
 * 명단에서는 같은 이름이 따로 떨어져 보이고, 영상에서는 같은 얼굴이 두 번 지나간다.
 *
 * 그래서 순서표는 그대로 두고, **사람 단위로 묶어 보는 눈**을 따로 둔다.
 */

/** 같은 사람인지 — 이름의 공백과 대소문자를 무시한다 */
export function performerKey(name: string): string {
  return name.replace(/\s+/g, '').toLowerCase()
}

export interface Appearance<T> {
  key: string
  name: string
  /** 이 사람이 맡은 곡들 — 순서표 차례 그대로 */
  rows: T[]
}

/** 이름으로 묶는다. 묶음의 차례는 그 사람이 처음 나오는 자리를 따른다 */
export function groupByPerformer<T extends { student_name: string }>(rows: T[]): Appearance<T>[] {
  const out: Appearance<T>[] = []
  const index = new Map<string, Appearance<T>>()
  for (const row of rows) {
    const key = performerKey(row.student_name)
    let found = index.get(key)
    if (!found) {
      found = { key, name: row.student_name.trim(), rows: [] }
      index.set(key, found)
      out.push(found)
    }
    found.rows.push(row)
  }
  return out
}

/** 순서표를 사람 단위로 묶는다 */
export function groupProgram(items: ProgramItem[]): Appearance<ProgramItem>[] {
  const out: Appearance<ProgramItem>[] = []
  const index = new Map<string, Appearance<ProgramItem>>()
  for (const item of items) {
    const key = performerKey(item.student.student_name)
    let found = index.get(key)
    if (!found) {
      found = { key, name: item.student.student_name.trim(), rows: [] }
      index.set(key, found)
      out.push(found)
    }
    found.rows.push(item)
  }
  return out
}

/** 실제 사람 수 — "연주자 32명, 곡 37곡" 처럼 보여 준다 */
export function performerCount(rows: { student_name: string }[]): number {
  return new Set(rows.map((row) => performerKey(row.student_name))).size
}

/**
 * 이 줄이 그 아이의 몇 번째 곡인가 (1부터). 한 곡뿐이면 null —
 * 화면에 "1곡 중 1번째" 라고 붙이면 오히려 시끄럽다.
 */
export function pieceIndex<T extends { student_name: string }>(
  rows: T[],
  target: T,
): { index: number; total: number } | null {
  const key = performerKey(target.student_name)
  const mine = rows.filter((row) => performerKey(row.student_name) === key)
  if (mine.length < 2) return null
  const index = mine.indexOf(target)
  return { index: index + 1, total: mine.length }
}

/**
 * 같은 이름의 아이가 사진을 하나만 올렸다면 나머지 줄에도 그 사진을 쓴다.
 *
 * 곡을 하나 더 추가할 때마다 같은 얼굴을 다시 올리게 하는 건 말이 안 된다.
 * (사진을 따로 지정한 줄은 그대로 둔다 — 독주 사진과 듀엣 사진이 다를 수 있다)
 */
export function sharePhotosByName(
  photos: Record<string, string>,
  students: Pick<EventStudent, 'id' | 'student_name'>[],
): Record<string, string> {
  const byName = new Map<string, string>()
  for (const student of students) {
    const url = photos[student.id]
    if (url && !byName.has(performerKey(student.student_name))) {
      byName.set(performerKey(student.student_name), url)
    }
  }
  const out = { ...photos }
  for (const student of students) {
    if (out[student.id]) continue
    const shared = byName.get(performerKey(student.student_name))
    if (shared) out[student.id] = shared
  }
  return out
}
