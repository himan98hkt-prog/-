import { performerKey } from '@/lib/program/appearances'
import type { Level } from '@/lib/types'

/**
 * 이 학원 아이들이 실제로 몇 분 걸리는가.
 *
 * 순서표의 예상 시간은 책에 적힌 평균이다. 그런데 아이마다 다르다 —
 * 같은 곡이라도 어떤 아이는 2분이고 어떤 아이는 3분 반이다.
 *
 * 당일 진행 화면에서 넘긴 시각이 곡마다 실제 초로 남는다. 그것을 **학원에**
 * 쌓아 둔다. 학생 명단은 행사마다 새로 만들어지지만 아이는 그대로이기 때문이다.
 *
 * 한 해치만 두면 지난번 값이 늘 덮어쓴다. 몇 해를 쌓아 **평균**을 내면
 * 그날 유난히 느렸던 한 번에 끌려다니지 않는다.
 */

/** 아이 한 명당 몇 번까지 기억할지 — 오래된 것은 지금의 그 아이가 아니다 */
export const TIMING_KEEP = 5

/**
 * 이름(공백·대소문자 무시) → 무대 기록, 오래된 것부터.
 *
 * 초만 적어 두면 곡이 달라진 것을 알 수 없다. 작년에 쉬운 곡, 올해 어려운 곡이면
 * 지난 기록이 오히려 틀린 값이 된다. 그래서 그때의 **난이도**를 함께 적는다.
 * (예전에 초만 적어 둔 것도 그대로 읽는다 — 난이도를 모르는 기록으로 본다)
 */
export interface TimingEntry {
  seconds: number
  /** 그때의 난이도. 모르면 없음 */
  level?: Level
}

export type TimingLog = Record<string, TimingEntry[]>

/** 기억할 만한 값인가 — 잘못 누른 것은 쌓지 않는다 (lib/ops/live.ts 와 같은 기준) */
export function usableTiming(seconds: number): boolean {
  return Number.isFinite(seconds) && seconds >= 20 && seconds <= 20 * 60
}

/** 어디서 왔든 믿을 수 있는 모양으로 — 학원 기록은 오래 남으므로 더 꼼꼼히 본다 */
const LEVELS = new Set<Level>(['beginner', 'intermediate', 'advanced', 'ensemble'])

function readEntry(item: unknown): TimingEntry | null {
  // 예전 판은 숫자만 적어 두었다
  if (typeof item === 'number') return usableTiming(item) ? { seconds: Math.round(item) } : null
  if (!item || typeof item !== 'object') return null
  const row = item as Record<string, unknown>
  const seconds = Math.round(Number(row.seconds))
  if (!usableTiming(seconds)) return null
  const level = LEVELS.has(row.level as Level) ? (row.level as Level) : undefined
  return level ? { seconds, level } : { seconds }
}

export function normalizeTimingLog(input: unknown, keep = TIMING_KEEP): TimingLog {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return {}
  const out: TimingLog = {}
  for (const [name, value] of Object.entries(input as Record<string, unknown>)) {
    const key = performerKey(String(name))
    if (!key || !Array.isArray(value)) continue
    const rows = value
      .map(readEntry)
      .filter((row): row is TimingEntry => row !== null)
      .slice(-keep)
    if (rows.length > 0) out[key] = rows
  }
  return out
}

/** 한 아이의 이번 기록을 뒤에 붙인다 (오래된 것부터 밀려 나간다) */
export function pushTiming(
  log: TimingLog,
  name: string,
  seconds: number,
  level?: Level,
  keep = TIMING_KEEP,
): TimingLog {
  if (!usableTiming(seconds)) return log
  const key = performerKey(name)
  if (!key) return log
  const entry: TimingEntry = level ? { seconds: Math.round(seconds), level } : { seconds: Math.round(seconds) }
  return { ...log, [key]: [...(log[key] ?? []), entry].slice(-keep) }
}

/** 여러 아이의 기록을 한 번에 쌓는다 */
export function pushTimings(
  log: TimingLog,
  rows: { name: string; seconds: number; level?: Level }[],
  keep = TIMING_KEEP,
): TimingLog {
  let next = log
  for (const row of rows) next = pushTiming(next, row.name, row.seconds, row.level, keep)
  return next
}

/**
 * 견줄 만한 기록만 고른다.
 *
 * 난이도를 알려 주시면 **그 난이도의 기록만** 본다. 작년에 쉬운 곡, 올해 어려운 곡이면
 * 지난 시간이 오히려 틀린 값이기 때문이다. 그 난이도의 기록이 하나도 없으면
 * 난이도를 모르는 기록(예전 판에서 온 것)만 쓰고, 그것도 없으면 아무것도 없는 것으로 본다.
 */
export function relevantTimings(
  log: TimingLog | null | undefined,
  name: string,
  level?: Level,
): TimingEntry[] {
  const rows = log?.[performerKey(name)] ?? []
  if (!level) return rows
  const same = rows.filter((row) => row.level === level)
  if (same.length > 0) return same
  return rows.filter((row) => row.level === undefined)
}

/**
 * 이 아이가 무대에서 실제로 걸린 시간의 평균(초).
 * 기록이 없으면 null — 없는 값을 지어내면 순서표가 조용히 틀어진다.
 */
export function averageTiming(log: TimingLog | null | undefined, name: string, level?: Level): number | null {
  const rows = relevantTimings(log, name, level)
  if (rows.length === 0) return null
  return Math.round(rows.reduce((sum, item) => sum + item.seconds, 0) / rows.length)
}

/** 몇 번의 무대에서 나온 값인가 — 한 번뿐이면 화면에서도 그렇게 말해야 한다 */
export function timingCount(log: TimingLog | null | undefined, name: string, level?: Level): number {
  return relevantTimings(log, name, level).length
}

/** 명단 화면에 붙일 한 줄 — 없으면 null */
export function timingHint(log: TimingLog | null | undefined, name: string, level?: Level): string | null {
  const average = averageTiming(log, name, level)
  if (average === null) return null
  const count = timingCount(log, name, level)
  const m = Math.floor(average / 60)
  const s = average % 60
  const time = m > 0 ? `${m}:${String(s).padStart(2, '0')}` : `${s}초`
  return count === 1 ? `지난 무대 실제 ${time}` : `지난 ${count}번 평균 ${time}`
}

/**
 * 기억해 둔 시간으로 명단의 예상 시간을 채운다.
 *
 * 곡을 비운 채 지난 행사에서 이름만 가져올 때가 이 값이 가장 쓸모 있는 자리다 —
 * 곡이 없으니 난이도로 추정할 수밖에 없는데, 그 아이의 실제 기록이 더 낫다.
 */
export function fillFromTimings<T extends { student_name: string; duration_sec: number | null; level?: Level }>(
  rows: T[],
  log: TimingLog | null | undefined,
): T[] {
  return rows.map((row) => {
    if (row.duration_sec) return row
    const average = averageTiming(log, row.student_name, row.level)
    return average === null ? row : { ...row, duration_sec: average }
  })
}

/** 학원이 쌓아 온 기록을 한눈에 — 몇 명이 몇 번 무대에 올랐는가 */
export function timingSummary(log: TimingLog | null | undefined): {
  people: number
  records: number
  averageSec: number | null
} {
  const rows = Object.values(log ?? {})
  const all = rows.flat()
  return {
    people: rows.length,
    records: all.length,
    averageSec: all.length === 0 ? null : Math.round(all.reduce((sum, row) => sum + row.seconds, 0) / all.length),
  }
}
