import { describe, expect, it } from 'vitest'
import { defaultCopy } from '@/lib/design/context'
import {
  CATEGORY_LABEL,
  DESIGN_TEMPLATES,
  PAGE_PX,
  PRINT_PACKS,
  getTemplate,
  packTemplates,
  sheetCount,
  templatesByCategory,
} from '@/lib/design/templates'
import {
  DESIGN_THEMES,
  getTheme,
  searchThemes,
  seasonalThemeIds,
  themeVars,
  themesByFamily,
} from '@/lib/design/themes'

/**
 * WCAG 상대 명도 대비. 인쇄물은 화면보다 대비가 더 떨어져 보이므로
 * 색을 새로 넣을 때마다 여기서 걸러 낸다.
 */
function relativeLuminance(hex: string): number {
  const value = hex.replace('#', '')
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16) / 255)
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}

function contrast(a: string, b: string): number {
  const [x, y] = [relativeLuminance(a), relativeLuminance(b)].sort((m, n) => n - m)
  return (x + 0.05) / (y + 0.05)
}
import type { Academy, EventRecord } from '@/lib/types'

const HEX = /^#[0-9a-f]{6}$/i

describe('디자인 테마', () => {
  it('id 가 겹치지 않는다', () => {
    expect(new Set(DESIGN_THEMES.map((t) => t.id)).size).toBe(DESIGN_THEMES.length)
  })

  it('모든 테마가 색·서체·설명을 갖춘다', () => {
    for (const theme of DESIGN_THEMES) {
      for (const [key, value] of Object.entries(theme.palette)) {
        expect(value, `${theme.id}.${key}`).toMatch(HEX)
      }
      expect(theme.fonts.display.length).toBeGreaterThan(0)
      expect(theme.fonts.body.length).toBeGreaterThan(0)
      expect(theme.tagline.length).toBeGreaterThan(5)
      expect(theme.mood.length).toBeGreaterThan(0)
    }
  })

  it('어두운 테마도 본문과 종이 색이 다르다', () => {
    for (const theme of DESIGN_THEMES) {
      expect(theme.palette.ink.toLowerCase()).not.toBe(theme.palette.paper.toLowerCase())
      expect(theme.palette.bandInk.toLowerCase()).not.toBe(theme.palette.band.toLowerCase())
    }
  })

  it('모르는 id 는 첫 테마로 떨어진다', () => {
    expect(getTheme('없는테마').id).toBe(DESIGN_THEMES[0].id)
    expect(getTheme(null).id).toBe(DESIGN_THEMES[0].id)
    expect(getTheme('modern-mono').id).toBe('modern-mono')
  })

  it('themeVars 는 인쇄물이 쓰는 변수를 모두 채운다', () => {
    const vars = themeVars(DESIGN_THEMES[0])
    for (const key of ['--d-paper', '--d-ink', '--d-accent', '--d-band', '--d-display', '--d-body']) {
      expect(vars[key], key).toBeTruthy()
    }
  })

  it('모든 테마가 로고 자리를 정의한다', () => {
    for (const theme of DESIGN_THEMES) {
      expect(['plain', 'circle', 'ring', 'plate'], theme.id).toContain(theme.logo.shape)
      expect(theme.logo.height, theme.id).toBeGreaterThanOrEqual(40)
      expect(theme.logo.height, theme.id).toBeLessThanOrEqual(96)
    }
  })

  it('어두운 테마의 로고는 밝은 판 위에 올린다', () => {
    // 배경이 어두우면 투명 배경 로고가 묻히므로 plate 로 받쳐 준다
    for (const id of ['midnight-stage', 'halloween-night']) {
      expect(getTheme(id).logo.shape, id).toBe('plate')
    }
  })

  it('모든 테마가 사진 자리 모양을 정의한다', () => {
    for (const theme of DESIGN_THEMES) {
      expect(['rect', 'rounded', 'circle', 'arch'], theme.id).toContain(theme.photo.shape)
    }
  })

  it('강조색은 종이색과 충분히 구분된다', () => {
    for (const theme of DESIGN_THEMES) {
      expect(theme.palette.accent.toLowerCase(), theme.id).not.toBe(theme.palette.paper.toLowerCase())
      expect(theme.palette.line.toLowerCase(), theme.id).not.toBe(theme.palette.paper.toLowerCase())
    }
  })
})

describe('인쇄 양식', () => {
  it('id 가 겹치지 않고 용지 크기가 정의돼 있다', () => {
    expect(new Set(DESIGN_TEMPLATES.map((t) => t.id)).size).toBe(DESIGN_TEMPLATES.length)
    for (const template of DESIGN_TEMPLATES) {
      expect(PAGE_PX[template.page], template.id).toBeTruthy()
      expect(template.description.length).toBeGreaterThan(10)
    }
  })

  it('포스터·프로그램·초대·행사당일 네 갈래를 모두 제공한다', () => {
    const groups = templatesByCategory()
    expect(groups).toHaveLength(Object.keys(CATEGORY_LABEL).length)
    for (const group of groups) expect(group.items.length).toBeGreaterThan(0)
    expect(groups.flatMap((g) => g.items)).toHaveLength(DESIGN_TEMPLATES.length)
  })

  it('사진을 쓰는 양식이 포함돼 있다', () => {
    expect(DESIGN_TEMPLATES.some((t) => t.id === 'poster-photo')).toBe(true)
    expect(getTemplate('poster-photo').category).toBe('poster')
  })

  it('모르는 id 는 첫 양식으로 떨어진다', () => {
    expect(getTemplate('없음').id).toBe(DESIGN_TEMPLATES[0].id)
    expect(getTemplate('certificate').id).toBe('certificate')
  })

  it('반복 양식은 인원수에 맞춰 장수를 계산한다', () => {
    expect(sheetCount('certificate', 12)).toBe(12)
    expect(sheetCount('nametag', 12)).toBe(2)
    expect(sheetCount('nametag', 8)).toBe(1)
    expect(sheetCount('nametag', 0)).toBe(1)
    expect(sheetCount('poster-classic', 30)).toBe(1)
  })

  it('순서표가 필요한 양식이 표시돼 있다', () => {
    expect(getTemplate('program-inner').needsProgram).toBe(true)
    expect(getTemplate('poster-classic').needsProgram).toBe(false)
  })
})

describe('기본 문구', () => {
  const academy = { name: '하모니 피아노학원' } as Academy

  it('연주회와 시즌 특강의 부제가 다르다', () => {
    expect(defaultCopy(academy, { type: 'recital' } as EventRecord).subtitle).toBe('정기 연주회')
    expect(defaultCopy(academy, { type: 'season' } as EventRecord).subtitle).toBe('시즌 특강 발표회')
  })

  it('주최에 학원명이 들어간다', () => {
    expect(defaultCopy(academy, { type: 'recital' } as EventRecord).host).toContain('하모니 피아노학원')
  })
})

describe('디자인 확장 — 테마 100종 · 양식 50종', () => {
  it('테마가 100종이고 id 가 겹치지 않는다', () => {
    expect(DESIGN_THEMES).toHaveLength(100)
    expect(new Set(DESIGN_THEMES.map((t) => t.id)).size).toBe(100)
  })

  it('이름도 겹치지 않는다 — 고를 때 헷갈리지 않게', () => {
    const names = DESIGN_THEMES.map((t) => t.name)
    expect(new Set(names).size).toBe(names.length)
  })

  it('테마 찾기가 이름·분위기·설명 어디에 걸려도 나온다', () => {
    expect(searchThemes('벚꽃').length).toBeGreaterThan(0)
    expect(searchThemes('격식').length).toBeGreaterThan(3)
    expect(searchThemes('겨울').length).toBeGreaterThan(2)
    expect(searchThemes('')).toHaveLength(DESIGN_THEMES.length)
    expect(searchThemes('존재하지않는말zzz')).toHaveLength(0)
  })

  it('모든 테마가 성격 묶음에 하나씩만 들어간다', () => {
    const grouped = themesByFamily().flatMap((g) => g.items)
    expect(grouped).toHaveLength(DESIGN_THEMES.length)
    expect(new Set(grouped.map((t) => t.id)).size).toBe(DESIGN_THEMES.length)
  })

  it('요청받은 성격이 모두 있다 — 고급·클래식, 사랑스러운, 계절', () => {
    const families = themesByFamily().map((g) => g.family)
    expect(families).toContain('classic')
    expect(families).toContain('lovely')
    expect(families).toContain('season')
    for (const group of themesByFamily()) {
      expect(group.items.length).toBeGreaterThanOrEqual(8)
    }
  })

  it('본문 글씨가 종이 위에서 읽힌다 — ink 와 paper 대비 7:1 이상', () => {
    for (const theme of DESIGN_THEMES) {
      expect(contrast(theme.palette.ink, theme.palette.paper)).toBeGreaterThanOrEqual(7)
    }
  })

  it('보조 글씨도 최소 대비를 지킨다 — muted 와 paper 3:1 이상', () => {
    for (const theme of DESIGN_THEMES) {
      expect(contrast(theme.palette.muted, theme.palette.paper)).toBeGreaterThanOrEqual(3)
    }
  })

  it('강조색이 큰 숫자로 쓰여도 보인다 — accent 와 paper 3:1 이상', () => {
    for (const theme of DESIGN_THEMES) {
      expect(contrast(theme.palette.accent, theme.palette.paper)).toBeGreaterThanOrEqual(3)
    }
  })

  it('제목 밴드 글씨가 밴드 위에서 읽힌다 — 4.5:1 이상', () => {
    for (const theme of DESIGN_THEMES) {
      expect(contrast(theme.palette.bandInk, theme.palette.band)).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('양식이 50종이고 id 가 겹치지 않는다', () => {
    expect(DESIGN_TEMPLATES).toHaveLength(50)
    expect(new Set(DESIGN_TEMPLATES.map((t) => t.id)).size).toBe(50)
  })

  it('갈래마다 고를 것이 넉넉하다 — 한 갈래에 한둘뿐이면 고르는 뜻이 없다', () => {
    for (const group of templatesByCategory()) {
      expect(group.items.length).toBeGreaterThanOrEqual(4)
    }
  })

  it('여러 장이 한 종이에 들어가는 양식은 몇 장인지 적어 둔다', () => {
    for (const item of DESIGN_TEMPLATES) {
      if (item.perSheet !== undefined) expect(item.perSheet).toBeGreaterThan(0)
    }
  })

  it('양식 이름도 겹치지 않는다', () => {
    const names = DESIGN_TEMPLATES.map((t) => t.name)
    expect(new Set(names).size).toBe(names.length)
  })

  it('모든 양식이 분류에 들어가고 용지 규격이 정의돼 있다', () => {
    const listed = templatesByCategory().flatMap((g) => g.items)
    expect(listed).toHaveLength(DESIGN_TEMPLATES.length)
    for (const template of DESIGN_TEMPLATES) {
      expect(PAGE_PX[template.page]).toBeTruthy()
    }
  })

  it('한 벌 인쇄는 용지가 같은 양식만 묶는다', () => {
    for (const pack of PRINT_PACKS) {
      const pages = new Set(packTemplates(pack).map((t) => t.page))
      expect(pages.size).toBe(1)
      expect(packTemplates(pack).length).toBeGreaterThanOrEqual(2)
    }
  })

  it('행사 달에 맞는 계절 테마를 추천한다', () => {
    for (const month of [1, 4, 7, 10]) {
      const ids = seasonalThemeIds(month)
      expect(ids.length).toBeGreaterThanOrEqual(3)
      for (const id of ids) {
        expect(DESIGN_THEMES.some((t) => t.id === id)).toBe(true)
      }
    }
  })
})
