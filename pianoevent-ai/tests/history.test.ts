import { describe, expect, it } from 'vitest'
import { countedEvent, historyNote, sortHistory, summarizeHistory, type HistoryRow } from '@/lib/ops/history'
import type { EventRecord } from '@/lib/types'

const row = (id: string, at: string, performers: number, planned = 3600): HistoryRow => ({
  id,
  title: `${id} 연주회`,
  event_at: at,
  performers,
  pieces: performers,
  planned_sec: planned,
  headcount: performers * 2,
  withPhoto: performers,
})

describe('학원 기록', () => {
  it('오래된 것부터 늘어놓는다 — 흐름이 보여야 한다', () => {
    const sorted = sortHistory([row('b', '2026-09-18', 15), row('a', '2025-09-18', 12)])
    expect(sorted.map((item) => item.id)).toEqual(['a', 'b'])
  })

  it('평균과 가장 많았을 때를 셈한다', () => {
    const summary = summarizeHistory([row('a', '2024-01-01', 10, 3000), row('b', '2025-01-01', 20, 5000)])
    expect(summary).toMatchObject({ events: 2, averagePerformers: 15, mostPerformers: 20, averageSec: 4000 })
  })

  it('최근 두 번을 견줘 늘고 있는지 본다', () => {
    expect(summarizeHistory([row('a', '2024-01-01', 10), row('b', '2025-01-01', 15)]).trend).toBe('up')
    expect(summarizeHistory([row('a', '2024-01-01', 15), row('b', '2025-01-01', 10)]).trend).toBe('down')
    expect(summarizeHistory([row('a', '2024-01-01', 12), row('b', '2025-01-01', 12)]).trend).toBe('flat')
    expect(summarizeHistory([row('a', '2024-01-01', 12)]).trend).toBe('unknown')
  })

  it('차례가 뒤섞여 들어와도 최근 두 번을 제대로 고른다', () => {
    const summary = summarizeHistory([row('b', '2026-01-01', 20), row('a', '2025-01-01', 10)])
    expect(summary.trend).toBe('up')
  })

  it('기록이 없으면 0 으로 채운다', () => {
    expect(summarizeHistory([])).toEqual({
      events: 0,
      mostPerformers: 0,
      averagePerformers: 0,
      averageSec: 0,
      trend: 'unknown',
    })
  })

  it('숫자만 던지지 않고 무슨 뜻인지 한 줄로 말해 준다', () => {
    expect(historyNote(summarizeHistory([]))).toContain('아직')
    expect(historyNote(summarizeHistory([row('a', '2025-01-01', 10)]))).toContain('첫 연주회')
    expect(historyNote(summarizeHistory([row('a', '2024-01-01', 10), row('b', '2025-01-01', 15)]))).toContain('늘고')
    expect(historyNote(summarizeHistory([row('a', '2024-01-01', 15), row('b', '2025-01-01', 10)]))).toContain('줄었')
  })

  it('기획만 하고 만 행사는 기록으로 세지 않는다', () => {
    const event = { status: 'draft' } as EventRecord
    expect(countedEvent(event, 12)).toBe(false)
    expect(countedEvent({ status: 'published' } as EventRecord, 12)).toBe(true)
    expect(countedEvent({ status: 'done' } as EventRecord, 12)).toBe(true)
    // 명단이 비어 있으면 치른 것이 아니다
    expect(countedEvent({ status: 'done' } as EventRecord, 0)).toBe(false)
  })
})
