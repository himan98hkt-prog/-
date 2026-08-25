import { describe, expect, it } from 'vitest'
import { formatClockOffset, formatDuration, formatWallClock } from '@/lib/format'

describe('formatDuration', () => {
  it('분과 초를 한국어로 적는다', () => {
    expect(formatDuration(200)).toBe('3분 20초')
    expect(formatDuration(180)).toBe('3분')
    expect(formatDuration(45)).toBe('45초')
    expect(formatDuration(0)).toBe('0초')
  })
})

describe('formatClockOffset', () => {
  it('한 시간을 넘으면 시:분:초로 적는다', () => {
    expect(formatClockOffset(200)).toBe('3:20')
    expect(formatClockOffset(3920)).toBe('1:05:20')
  })
})

describe('formatWallClock', () => {
  it('행사 시작 시각에 오프셋을 더해 오전/오후로 적는다', () => {
    const start = new Date(2026, 2, 14, 15, 0, 0).toISOString()
    expect(formatWallClock(start, 0)).toBe('오후 3:00')
    expect(formatWallClock(start, 12 * 60)).toBe('오후 3:12')
  })

  it('시작 시각이 잘못되면 오프셋 표기로 떨어진다', () => {
    expect(formatWallClock('not-a-date', 200)).toBe('3:20')
  })
})
