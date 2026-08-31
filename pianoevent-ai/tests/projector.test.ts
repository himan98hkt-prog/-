import { describe, expect, it } from 'vitest'
import { PROJECTOR_GUIDE, PROJECTOR_PACKING, PROJECTOR_WHEN } from '@/lib/ops/projector'

describe('빔프로젝터 연결 안내', () => {
  it('윈도우 · 맥 · 안 될 때 세 갈래를 다 짚는다', () => {
    const titles = PROJECTOR_GUIDE.map((b) => b.title).join(' ')
    expect(titles).toContain('윈도우')
    expect(titles).toContain('맥')
    expect(titles).toContain('안 나올 때')
  })

  it('눌러야 할 자판을 정확히 적는다 — 이게 없으면 안내가 아니다', () => {
    const all = PROJECTOR_GUIDE.flatMap((b) => b.steps).join(' ')
    expect(all).toContain('윈도우키')
    expect(all).toContain('복제')
    expect(all).toContain('미러링')
  })

  it('가장 흔한 원인(빔프로젝터 입력)을 짚는다', () => {
    const all = PROJECTOR_GUIDE.flatMap((b) => b.steps).join(' ')
    expect(all).toContain('입력')
    expect(all).toContain('HDMI')
  })

  it('갈래마다 걸음이 비어 있지 않다', () => {
    for (const block of PROJECTOR_GUIDE) {
      expect(block.steps.length, block.title).toBeGreaterThanOrEqual(2)
      for (const step of block.steps) expect(step.length, block.title).toBeGreaterThan(8)
    }
  })

  it('연주회장에 없어서 낭패 보는 것들을 챙기라고 한다', () => {
    const packing = PROJECTOR_PACKING.join(' ')
    expect(packing).toContain('젠더')
    expect(packing).toContain('충전기')
    expect(packing).toContain('멀티탭')
  })

  it('언제 해 보시라는 말이 있다 — 당일 저녁에 알면 늦다', () => {
    expect(PROJECTOR_WHEN).toContain('리허설')
  })
})
