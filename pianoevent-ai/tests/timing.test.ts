import { describe, expect, it } from 'vitest'
import {
  averageTiming,
  fillFromTimings,
  normalizeTimingLog,
  pushTiming,
  pushTimings,
  TIMING_KEEP,
  timingCount,
  timingHint,
  usableTiming,
} from '@/lib/ops/timing'

describe('아이별 실제 연주 시간 쌓기', () => {
  it('기억할 만한 값만 쌓는다 — 잘못 누른 것은 버린다', () => {
    expect(usableTiming(120)).toBe(true)
    expect(usableTiming(3)).toBe(false)
    expect(usableTiming(40 * 60)).toBe(false)
    expect(usableTiming(Number.NaN)).toBe(false)
  })

  it('한 번 무대에 서면 한 줄이 쌓인다', () => {
    expect(pushTiming({}, '김서연', 118)).toEqual({ 김서연: [118] })
  })

  it('이름의 띄어쓰기가 달라도 같은 아이로 쌓인다', () => {
    const log = pushTiming(pushTiming({}, '김 서연', 110), '김서연', 120)
    expect(Object.keys(log)).toHaveLength(1)
    expect(Object.values(log)[0]).toEqual([110, 120])
  })

  it('정해진 횟수만 기억한다 — 오래된 것은 지금의 그 아이가 아니다', () => {
    let log = {}
    for (let i = 0; i < TIMING_KEEP + 3; i += 1) log = pushTiming(log, '박지호', 100 + i)
    expect(Object.values(log)[0]).toHaveLength(TIMING_KEEP)
    // 최근 것이 남는다
    expect((Object.values(log)[0] as number[]).at(-1)).toBe(100 + TIMING_KEEP + 2)
  })

  it('말이 안 되는 값은 쌓지 않는다', () => {
    expect(pushTiming({}, '김서연', 4)).toEqual({})
    expect(pushTiming({}, '', 120)).toEqual({})
  })

  it('여러 아이를 한 번에 쌓는다', () => {
    const log = pushTimings({}, [
      { name: '김서연', seconds: 110 },
      { name: '박지호', seconds: 95 },
      { name: '김서연', seconds: 130 },
    ])
    expect(log).toEqual({ 김서연: [110, 130], 박지호: [95] })
  })

  it('평균을 낸다 — 그날 유난히 느렸던 한 번에 끌려다니지 않게', () => {
    const log = pushTimings({}, [
      { name: '김서연', seconds: 100 },
      { name: '김서연', seconds: 140 },
    ])
    expect(averageTiming(log, '김서연')).toBe(120)
    expect(timingCount(log, '김서연')).toBe(2)
  })

  it('기록이 없으면 지어내지 않는다', () => {
    expect(averageTiming({}, '김서연')).toBeNull()
    expect(averageTiming(null, '김서연')).toBeNull()
    expect(timingHint(null, '김서연')).toBeNull()
  })

  it('한 번뿐이면 화면에서도 그렇게 말한다', () => {
    expect(timingHint({ 김서연: [110] }, '김서연')).toBe('지난 무대 실제 1:50')
    expect(timingHint({ 김서연: [110, 130] }, '김서연')).toBe('지난 2번 평균 2:00')
  })

  it('저장돼 있던 것이 망가져 있어도 무너지지 않는다', () => {
    expect(normalizeTimingLog(null)).toEqual({})
    expect(normalizeTimingLog('기록')).toEqual({})
    expect(normalizeTimingLog([1, 2])).toEqual({})
    expect(normalizeTimingLog({ 김서연: '백십초' })).toEqual({})
    expect(normalizeTimingLog({ 김서연: [110, 3, '어제', 40 * 60, 130] })).toEqual({ 김서연: [110, 130] })
  })

  it('되읽을 때도 정해진 횟수만 남긴다', () => {
    const many = Array.from({ length: 20 }, (_, i) => 100 + i)
    expect(normalizeTimingLog({ 김서연: many }).김서연).toHaveLength(TIMING_KEEP)
  })

  it('곡을 비운 명단의 예상 시간을 실제 기록으로 채운다', () => {
    const rows = [
      { student_name: '김서연', duration_sec: null },
      { student_name: '박지호', duration_sec: null },
      { student_name: '김서연', duration_sec: 200 },
    ]
    const filled = fillFromTimings(rows, { 김서연: [110, 130] })
    expect(filled[0].duration_sec).toBe(120)
    // 기록이 없는 아이는 그대로 비워 둔다 — 난이도로 추정하게
    expect(filled[1].duration_sec).toBeNull()
    // 이미 적어 두신 시간은 건드리지 않는다
    expect(filled[2].duration_sec).toBe(200)
  })
})
