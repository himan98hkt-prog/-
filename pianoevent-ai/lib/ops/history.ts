import type { EventRecord } from '@/lib/types'

/**
 * 학원이 쌓아 온 기록.
 *
 * 해마다 연주회를 치르면서도 "작년엔 몇 명이었지, 몇 분 걸렸지" 는 늘 기억에 없다.
 * 다음 연주회 규모를 정하실 때 근거가 되는 것들만 한 장으로 모은다.
 *
 * 새로 입력받는 것은 하나도 없다 — 이미 들어 있는 것을 세는 것뿐이다.
 */

export interface HistoryRow {
  id: string
  title: string
  event_at: string
  /** 연주자 수 (사람 기준) */
  performers: number
  /** 곡 수 */
  pieces: number
  /** 예상 러닝타임(초) */
  planned_sec: number
  /** 참석 회신 인원 */
  headcount: number
  /** 사진을 넣어 둔 아이 수 */
  withPhoto: number
}

export interface HistorySummary {
  events: number
  /** 가장 많았을 때 연주자 수 */
  mostPerformers: number
  /** 연주자 수 평균 */
  averagePerformers: number
  /** 러닝타임 평균(초) */
  averageSec: number
  /** 늘고 있는가 — 최근 두 번을 견준다 */
  trend: 'up' | 'down' | 'flat' | 'unknown'
}

/** 오래된 것부터. 화면에서는 흐름이 보여야 한다 */
export function sortHistory(rows: HistoryRow[]): HistoryRow[] {
  return [...rows].sort((a, b) => a.event_at.localeCompare(b.event_at))
}

export function summarizeHistory(rows: HistoryRow[]): HistorySummary {
  const sorted = sortHistory(rows)
  if (sorted.length === 0) {
    return { events: 0, mostPerformers: 0, averagePerformers: 0, averageSec: 0, trend: 'unknown' }
  }
  const performers = sorted.map((row) => row.performers)
  const average = (list: number[]) => Math.round(list.reduce((sum, item) => sum + item, 0) / list.length)
  const last = sorted[sorted.length - 1]
  const before = sorted[sorted.length - 2]
  const trend: HistorySummary['trend'] = !before
    ? 'unknown'
    : last.performers > before.performers
      ? 'up'
      : last.performers < before.performers
        ? 'down'
        : 'flat'
  return {
    events: sorted.length,
    mostPerformers: Math.max(...performers),
    averagePerformers: average(performers),
    averageSec: average(sorted.map((row) => row.planned_sec)),
    trend,
  }
}

/** 화면에 그대로 쓰는 한 줄 — 숫자만 던지면 무슨 뜻인지 원장님이 해석하셔야 한다 */
export function historyNote(summary: HistorySummary): string {
  if (summary.events === 0) return '아직 치른 연주회가 없습니다. 한 번 치르고 나면 여기에 쌓입니다.'
  if (summary.events === 1) return '이번이 첫 연주회입니다. 다음 해부터 견줄 수 있습니다.'
  switch (summary.trend) {
    case 'up':
      return `연주자가 늘고 있습니다. 지난번보다 많은 아이가 무대에 섰습니다.`
    case 'down':
      return `지난번보다 연주자가 줄었습니다. 대관 규모를 다시 보실 만합니다.`
    default:
      return `연주자 수가 지난번과 비슷합니다.`
  }
}

/** 행사가 실제로 치러진 것인가 — 기획만 하고 만 것은 기록으로 세지 않는다 */
export function countedEvent(event: EventRecord, performers: number): boolean {
  return performers > 0 && (event.status === 'done' || event.status === 'published')
}
