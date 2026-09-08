import { describe, expect, it } from 'vitest'
import { SAVED_PER_ITEM_SEC, paceAdvice } from '@/lib/ops/pace'

describe('밀렸으면 어쩌라는 말까지', () => {
  it('예정대로면 아무것도 하지 말라고 한다', () => {
    const advice = paceAdvice(0, 10)
    expect(advice.level).toBe('ok')
    expect(advice.say).toContain('그대로')
  })

  it('4분 안쪽은 늘 생기는 차이라 흔들지 않는다', () => {
    expect(paceAdvice(3 * 60, 10).level).toBe('ok')
    expect(paceAdvice(-3 * 60, 10).level).toBe('ok')
  })

  it('조금 밀리면 멘트를 짧게 하라고 한다', () => {
    const advice = paceAdvice(6 * 60, 10)
    expect(advice.level).toBe('warn')
    expect(advice.say).toContain('짧게')
  })

  it('많이 밀리면 곡 해설을 건너뛰라고 한다', () => {
    const advice = paceAdvice(15 * 60, 10)
    expect(advice.level).toBe('late')
    expect(advice.say).toContain('해설')
  })

  it('빠르면 한마디 더 얹으라고 한다 — 너무 일찍 끝나도 곤란하다', () => {
    const advice = paceAdvice(-8 * 60, 10)
    expect(advice.level).toBe('ahead')
    expect(advice.say).toContain('한 줄 더')
  })

  it('남은 순서로 따라잡을 수 있으면 그렇다고 말해 준다', () => {
    // 20순서 × 10초 = 200초. 2분 밀린 것은 따라잡는다
    const advice = paceAdvice(11 * 60, 80)
    expect(advice.level).toBe('late')
    expect(advice.why).toContain('따라잡')
  })

  it('못 따라잡으면 마무리를 짧게 할 준비를 시킨다 — 헛되이 급하게만 만들지 않는다', () => {
    const advice = paceAdvice(20 * 60, 2)
    expect(advice.why).toContain('마무리')
  })

  it('한 순서에서 버는 시간은 실제 값이다', () => {
    expect(SAVED_PER_ITEM_SEC).toBe(10)
  })

  it('어느 값에서도 네 가지를 다 채워 준다', () => {
    for (const drift of [-3600, -300, -60, 0, 60, 240, 600, 3600]) {
      for (const left of [0, 1, 5, 40]) {
        const advice = paceAdvice(drift, left)
        expect(advice.what.length, `${drift}/${left}`).toBeGreaterThan(1)
        expect(advice.say.length, `${drift}/${left}`).toBeGreaterThan(4)
        expect(advice.why.length, `${drift}/${left}`).toBeGreaterThan(4)
      }
    }
  })

  it('남은 순서가 없어도 멈추지 않는다', () => {
    expect(() => paceAdvice(600, 0)).not.toThrow()
    expect(() => paceAdvice(600, -5)).not.toThrow()
  })
})
