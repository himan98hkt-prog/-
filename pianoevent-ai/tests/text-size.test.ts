import { describe, expect, it } from 'vitest'
import { TEXT_SIZES, getTextSize, nextTextSize, rootFontPx } from '@/lib/text-size'

describe('글씨 크기', () => {
  it('세 단계뿐이다 — 고를 것이 많으면 그것대로 짐이 된다', () => {
    expect(TEXT_SIZES).toHaveLength(3)
  })

  it('단계마다 이름이 우리말로 있다', () => {
    expect(TEXT_SIZES.map((s) => s.label)).toEqual(['보통', '크게', '아주 크게'])
  })

  it('뒤로 갈수록 커진다', () => {
    for (let i = 1; i < TEXT_SIZES.length; i += 1) {
      expect(TEXT_SIZES[i].scale).toBeGreaterThan(TEXT_SIZES[i - 1].scale)
    }
  })

  it('모르는 값은 보통으로 본다 — 멈추는 것보다 낫다', () => {
    expect(getTextSize('없는것').id).toBe('normal')
    expect(getTextSize(null).id).toBe('normal')
  })

  it('누를 때마다 한 단계씩, 끝에서는 처음으로', () => {
    expect(nextTextSize('normal')).toBe('big')
    expect(nextTextSize('big')).toBe('huge')
    expect(nextTextSize('huge')).toBe('normal')
  })

  it('뿌리 글씨 크기를 바꾼다 — 글자만 커지고 상자가 그대로면 글이 뚫고 나온다', () => {
    expect(rootFontPx('normal')).toBe(16)
    expect(rootFontPx('big')).toBeGreaterThan(16)
    expect(rootFontPx('huge')).toBeGreaterThan(rootFontPx('big'))
  })

  it('너무 커지지는 않는다 — 표가 옆으로 넘친다', () => {
    expect(rootFontPx('huge')).toBeLessThanOrEqual(22)
  })
})
