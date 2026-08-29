import { describe, expect, it } from 'vitest'
import { CHIME_LEAD_SEC, chimeAtSec, chimeDue, chimeStorageKey } from '@/lib/ops/chime'

describe('다음 차례 알림음', () => {
  it('보통 곡은 끝나기 1분 전에 울린다', () => {
    expect(chimeAtSec(210)).toBe(210 - CHIME_LEAD_SEC)
  })

  it('알림보다 짧은 곡은 절반쯤에서 한 번 울린다 — 아예 안 울리면 유아부는 알림이 하나도 없다', () => {
    expect(chimeAtSec(60)).toBe(30)
    expect(chimeAtSec(40)).toBe(20)
  })

  it('너무 짧으면 울리지 않는다 — 시작하자마자 울리면 뜻이 없다', () => {
    expect(chimeAtSec(10)).toBeNull()
    expect(chimeAtSec(0)).toBeNull()
    expect(chimeAtSec(Number.NaN)).toBeNull()
  })

  it('울릴 자리는 늘 그 순서 안이다', () => {
    for (const sec of [12, 30, 60, 95, 210, 600]) {
      const at = chimeAtSec(sec)
      if (at === null) continue
      expect(at, `${sec}초`).toBeGreaterThan(0)
      expect(at, `${sec}초`).toBeLessThan(sec)
    }
  })

  it('때가 되면 울릴 때라고 한다', () => {
    expect(chimeDue(0, 210)).toBe(false)
    expect(chimeDue(149, 210)).toBe(false)
    expect(chimeDue(150, 210)).toBe(true)
    expect(chimeDue(400, 210)).toBe(true)
  })

  it('울릴 자리가 없는 순서는 언제 봐도 울리지 않는다', () => {
    expect(chimeDue(5, 8)).toBe(false)
    expect(chimeDue(999, 8)).toBe(false)
  })

  it('행사마다 따로 담는다 — 한 행사에서 켜면 다른 행사도 켜지면 안 된다', () => {
    expect(chimeStorageKey('a')).not.toBe(chimeStorageKey('b'))
    expect(chimeStorageKey('a')).toContain('a')
  })
})
