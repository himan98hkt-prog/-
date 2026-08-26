import { describe, expect, it } from 'vitest'
import { defaultCopy } from '@/lib/design/context'
import {
  CATEGORY_LABEL,
  DESIGN_TEMPLATES,
  PAGE_PX,
  getTemplate,
  sheetCount,
  templatesByCategory,
} from '@/lib/design/templates'
import { DESIGN_THEMES, getTheme, themeVars } from '@/lib/design/themes'
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
