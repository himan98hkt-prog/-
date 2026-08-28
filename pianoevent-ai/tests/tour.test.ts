import { describe, expect, it } from 'vitest'
import { TOUR_STEPS, nextStep, prevStep, stepLabel } from '@/lib/tour/steps'

describe('처음 켰을 때 안내', () => {
  it('다섯 걸음을 넘지 않는다 — 그 이상이면 끝까지 안 보신다', () => {
    expect(TOUR_STEPS.length).toBeLessThanOrEqual(5)
    expect(TOUR_STEPS.length).toBeGreaterThan(0)
  })

  it('걸음마다 제목·설명·어디서 하는지가 다 있다', () => {
    for (const step of TOUR_STEPS) {
      expect(step.title.length).toBeGreaterThan(0)
      expect(step.body.length).toBeGreaterThan(0)
      expect(step.where.length).toBeGreaterThan(0)
    }
  })

  it('설명서에 적은 세 가지를 그대로 짚는다', () => {
    const all = TOUR_STEPS.map((s) => s.title).join(' ')
    expect(all).toContain('학생 명단')
    expect(all).toContain('순서표')
    expect(all).toContain('인쇄물')
  })

  it('마지막에서 다음을 누르면 닫는다', () => {
    expect(nextStep(TOUR_STEPS.length - 1)).toBe(-1)
    expect(nextStep(0)).toBe(1)
  })

  it('첫 걸음에서 이전을 눌러도 뒤로 넘어가지 않는다', () => {
    expect(prevStep(0)).toBe(0)
    expect(prevStep(2)).toBe(1)
  })

  it('몇 걸음 중 몇 번째인지 적어 준다 — 끝이 보여야 끝까지 보신다', () => {
    expect(stepLabel(0)).toBe(`1 / ${TOUR_STEPS.length}`)
    expect(stepLabel(TOUR_STEPS.length - 1)).toBe(`${TOUR_STEPS.length} / ${TOUR_STEPS.length}`)
  })
})
