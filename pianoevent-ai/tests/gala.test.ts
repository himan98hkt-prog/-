import { describe, expect, it } from 'vitest'
import { fitTitle } from '@/lib/design/fit'
import { DESIGN_THEMES, FAMILY_LABEL, isDarkTheme, themesByFamily } from '@/lib/design/themes'
import { recommendDesigns } from '@/lib/design/recommend'

describe('제목 글씨 크기 맞추기', () => {
  it('짧은 제목은 가장 크게 그대로', () => {
    expect(fitTitle('봄 연주회', 74)).toBe(74)
  })

  it('제목이 길수록 작아진다 — 큰 글씨가 판을 무너뜨리지 않게', () => {
    const sizes = [
      fitTitle('봄 연주회', 74),
      fitTitle('제12회 정기 연주회', 74),
      fitTitle('제12회 하모니 정기 연주회', 74),
      fitTitle('제12회 하모니피아노학원 정기 연주회 및 시상식', 74),
      fitTitle('제12회 하모니피아노학원 정기 연주회 및 시상식 그리고 수료식', 74),
    ]
    for (let i = 1; i < sizes.length; i += 1) {
      expect(sizes[i], String(i)).toBeLessThan(sizes[i - 1])
    }
    expect(sizes.at(-1)).toBeGreaterThan(20)
  })

  it('앞뒤 공백은 세지 않는다', () => {
    expect(fitTitle('  봄 연주회  ', 74)).toBe(74)
  })
})

describe('예술회관 테마', () => {
  const gala = DESIGN_THEMES.filter((t) => t.family === 'gala')

  it('여덟 종이 있고 이름이 원장님 말로 붙어 있다', () => {
    expect(gala).toHaveLength(8)
    expect(FAMILY_LABEL.gala).toContain('격조')
  })

  it('어두운 것과 밝은 것이 섞여 있다 — 흑백 인쇄만 되는 학원도 있다', () => {
    expect(gala.some((t) => isDarkTheme(t))).toBe(true)
    expect(gala.some((t) => !isDarkTheme(t))).toBe(true)
  })

  it('성격 묶음에서 맨 앞에 온다', () => {
    expect(themesByFamily()[0].family).toBe('gala')
  })

  it('찾기에 "예술회관" 으로 걸린다', () => {
    for (const theme of gala) expect(theme.mood, theme.id).toContain('예술회관')
  })
})

describe('세 장 중 화려한 쪽', () => {
  it('예술회관 테마로 나온다 — 이 정도가 나온다는 것을 바로 보시게', () => {
    const fancy = recommendDesigns({ eventAt: '2026-09-19T15:00:00+09:00', hasProgram: true }).find(
      (s) => s.kind === 'fancy',
    )
    expect(fancy).toBeTruthy()
    expect(DESIGN_THEMES.find((t) => t.id === fancy!.themeId)!.family).toBe('gala')
  })

  it('자리 셋은 늘 같다 — 고르신 것이 있어도 화려한 쪽이 빠지지 않는다', () => {
    const kinds = recommendDesigns({
      eventAt: '2026-09-19T15:00:00+09:00',
      hasProgram: true,
      themeId: 'classic-navy',
    }).map((s) => s.kind)
    expect(kinds).toEqual(['chosen', 'plain', 'fancy'])
  })
})
