import { describe, expect, it } from 'vitest'
import {
  formatClockOffset,
  formatDuration,
  formatEventDate,
  formatShortDate,
  formatWallClock,
  fromDatetimeLocal,
  normalizeEventAt,
  toDatetimeLocal,
} from '@/lib/format'

// 기본 학원 시간대는 Asia/Seoul(UTC+9). 아래 값들은 서버·브라우저의 시간대와 무관하게 같아야 한다.
const MARCH_14_15H_KST = '2026-03-14T06:00:00.000Z'

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
  it('행사 시작 시각에 오프셋을 더해 학원 시간대로 적는다', () => {
    expect(formatWallClock(MARCH_14_15H_KST, 0)).toBe('오후 3:00')
    expect(formatWallClock(MARCH_14_15H_KST, 12 * 60)).toBe('오후 3:12')
    expect(formatWallClock(MARCH_14_15H_KST, 60 * 60)).toBe('오후 4:00')
  })

  it('자정을 넘어가도 오전 12시로 적는다', () => {
    expect(formatWallClock('2026-03-14T15:00:00.000Z', 0)).toBe('오전 12:00')
  })

  it('시작 시각이 잘못되면 오프셋 표기로 떨어진다', () => {
    expect(formatWallClock('not-a-date', 200)).toBe('3:20')
  })
})

describe('formatEventDate', () => {
  it('요일과 오전/오후를 학원 시간대로 적는다', () => {
    expect(formatEventDate(MARCH_14_15H_KST)).toBe('2026년 3월 14일 (토) 오후 3:00')
  })

  it('UTC 기준으로 날짜가 바뀌는 시각도 학원 시간대의 날짜로 적는다', () => {
    // 2026-03-14T16:00Z = 2026-03-15 01:00 KST
    expect(formatEventDate('2026-03-14T16:00:00.000Z')).toBe('2026년 3월 15일 (일) 오전 1:00')
  })

  it('해석할 수 없는 값은 그대로 돌려준다', () => {
    expect(formatEventDate('언젠가')).toBe('언젠가')
  })
})

describe('formatShortDate', () => {
  it('학원 시간대의 날짜를 점 표기로 적는다', () => {
    expect(formatShortDate(MARCH_14_15H_KST)).toBe('2026.03.14')
    expect(formatShortDate('2026-03-14T16:00:00.000Z')).toBe('2026.03.15')
  })
})

describe('toDatetimeLocal · fromDatetimeLocal', () => {
  it('입력 칸 값과 ISO 를 서로 손실 없이 오간다', () => {
    expect(toDatetimeLocal(MARCH_14_15H_KST)).toBe('2026-03-14T15:00')
    expect(fromDatetimeLocal('2026-03-14T15:00')).toBe(MARCH_14_15H_KST)
    expect(toDatetimeLocal(fromDatetimeLocal('2026-12-24T19:30')!)).toBe('2026-12-24T19:30')
  })

  it('형식이 어긋나면 null 을 돌려준다', () => {
    expect(fromDatetimeLocal('2026/03/14 15:00')).toBeNull()
    expect(fromDatetimeLocal('')).toBeNull()
    expect(toDatetimeLocal('언젠가')).toBe('')
  })
})

describe('normalizeEventAt', () => {
  it('시간대가 붙은 값은 그대로 해석한다', () => {
    expect(normalizeEventAt('2026-03-14T06:00:00.000Z')).toBe(MARCH_14_15H_KST)
    expect(normalizeEventAt('2026-03-14T15:00:00+09:00')).toBe(MARCH_14_15H_KST)
  })

  it('시간대가 없는 값은 학원 시간대의 벽시계로 읽는다', () => {
    expect(normalizeEventAt('2026-03-14T15:00')).toBe(MARCH_14_15H_KST)
  })

  it('빈 값과 잘못된 값은 null 이다', () => {
    expect(normalizeEventAt('  ')).toBeNull()
    expect(normalizeEventAt('내일 오후')).toBeNull()
  })
})
