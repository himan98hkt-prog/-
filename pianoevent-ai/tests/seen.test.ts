import { describe, expect, it } from 'vitest'
import { SEEN_STEPS, addSeen, parseSeen, seenStorageKey, unseenSteps } from '@/lib/events/seen'
import { getStep } from '@/lib/flow/steps'

describe('어디까지 보셨는지', () => {
  it('구경용에서 꼭 보시면 좋은 것들이 담겨 있다', () => {
    expect(SEEN_STEPS).toContain('print')
    expect(SEEN_STEPS).toContain('stage')
    expect(SEEN_STEPS).toContain('video')
    expect(SEEN_STEPS).toContain('live')
  })

  it('전부 실제로 있는 화면이다 — 없는 화면으로 보내면 안 된다', () => {
    for (const key of SEEN_STEPS) expect(getStep(key).key, key).toBe(key)
  })

  it('본 것을 더한다', () => {
    expect(addSeen([], 'print')).toEqual(['print'])
    expect(addSeen(['print'], 'stage')).toEqual(['print', 'stage'])
  })

  it('같은 화면을 두 번 적지 않는다', () => {
    const seen = ['print' as const]
    expect(addSeen(seen, 'print')).toBe(seen)
  })

  it('구경거리가 아닌 화면은 세지 않는다 — 명단을 열었다고 구경을 한 것이 아니다', () => {
    expect(addSeen([], 'roster')).toEqual([])
  })

  it('아직 안 보신 것을 알려 준다', () => {
    expect(unseenSteps([])).toEqual(SEEN_STEPS)
    expect(unseenSteps(['print', 'stage', 'video', 'live'])).toEqual([])
    expect(unseenSteps(['print'])).not.toContain('print')
  })

  it('담긴 것이 망가졌어도 멈추지 않는다', () => {
    expect(parseSeen(null)).toEqual([])
    expect(parseSeen('{망가짐')).toEqual([])
    expect(parseSeen('"글자"')).toEqual([])
    expect(parseSeen('["print","없는화면",7]')).toEqual(['print'])
  })

  it('담았다 되읽으면 그대로다', () => {
    const seen = addSeen(addSeen([], 'video'), 'live')
    expect(parseSeen(JSON.stringify(seen))).toEqual(seen)
  })

  it('행사마다 따로 담는다', () => {
    expect(seenStorageKey('a')).not.toBe(seenStorageKey('b'))
  })
})
