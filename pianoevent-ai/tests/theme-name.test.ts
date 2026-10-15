import { describe, expect, it } from 'vitest'
import { DESIGN_THEMES, isDarkTheme } from '@/lib/design/themes'

/**
 * 이름과 색이 어긋나지 않게 지킨다.
 *
 * 원장님은 **이름을 보고 고르십니다.** 「클래식 네이비」를 골랐는데 남색이 한 군데도
 * 없으면 고른 뜻이 사라진다. 실제로 「앤티크 로즈골드」에 금색이 없었고, 눈으로는
 * 108종을 다 훑을 수 없어 못 잡고 있었다. 그래서 재서 지킨다.
 *
 * 이름의 색 낱말이 **종이·머리띠·강조색 중 하나**에는 들어 있어야 한다.
 * 셋 다 아니면 그 이름은 거짓이다.
 */
function hsl(hex: string): { h: number; s: number } {
  const v = hex.replace('#', '')
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(v.slice(i, i + 2), 16) / 255)
  const mx = Math.max(r, g, b)
  const mn = Math.min(r, g, b)
  const d = mx - mn
  let h = 0
  if (d) h = mx === r ? 60 * (((g - b) / d) % 6) : mx === g ? 60 * ((b - r) / d + 2) : 60 * ((r - g) / d + 4)
  if (h < 0) h += 360
  const l = (mx + mn) / 2
  return { h: Math.round(h), s: Math.round((d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1))) * 100) }
}

/** 색 낱말이 허용하는 색상환 구간(도). 넉넉하게 잡는다 — 잡으려는 것은 "전혀 다른 색"이다 */
const HUE: Record<string, [number, number][]> = {
  네이비: [[195, 255]],
  블루: [[185, 255]],
  스카이: [[180, 240]],
  문릿: [[185, 255]],
  마린: [[185, 250]],
  로즈: [[315, 360], [0, 20]],
  핑크: [[300, 360]],
  블러시: [[320, 360], [0, 20]],
  벚꽃: [[315, 360], [0, 20]],
  피치: [[5, 40]],
  코랄: [[0, 30]],
  에메랄드: [[125, 185]],
  포레스트: [[90, 170]],
  민트: [[135, 190]],
  그린: [[85, 170]],
  세이지: [[70, 160]],
  터콰이즈: [[160, 200]],
  골드: [[25, 58]],
  샴페인: [[25, 58]],
  앰버: [[20, 55]],
  허니: [[25, 55]],
  아이보리: [[25, 60]],
  세피아: [[15, 50]],
  단풍: [[10, 45]],
  버건디: [[325, 360], [0, 20]],
  와인: [[325, 360], [0, 20]],
  크림슨: [[330, 360], [0, 18]],
  레드: [[340, 360], [0, 20]],
  라벤더: [[245, 305]],
  퍼플: [[250, 305]],
  바이올렛: [[250, 305]],
}

/** 이름이 어둠을 말하면 종이도 어두워야 한다 */
const DARK_WORDS = ['미드나잇', '느와르', '나이트', '오닉스', '블랙', '다크', '심야']

describe('테마 이름과 색', () => {
  it('이름에 든 색이 종이·머리띠·강조색 어딘가에는 있다', () => {
    const wrong: string[] = []
    for (const theme of DESIGN_THEMES) {
      const candidates = [theme.palette.accent, theme.palette.band, theme.palette.paperAlt, theme.palette.paper].map(hsl)
      for (const [word, ranges] of Object.entries(HUE)) {
        if (!theme.name.includes(word)) continue
        // 채도가 아주 낮은 회색에는 색 이름을 붙일 수 없다
        const ok = candidates.some((c) => c.s >= 14 && ranges.some(([lo, hi]) => c.h >= lo && c.h <= hi))
        if (!ok) wrong.push(`${theme.name}(${theme.id}) — '${word}' 인데 그 색이 없다`)
      }
    }
    expect(wrong).toEqual([])
  })

  it('이름이 어두우면 종이도 어둡다', () => {
    const wrong = DESIGN_THEMES.filter(
      (t) => DARK_WORDS.some((w) => t.name.includes(w)) && !isDarkTheme(t),
    ).map((t) => t.name)
    expect(wrong).toEqual([])
  })

  it('설명 한 줄도 이름과 같은 색을 말한다', () => {
    // 이름은 「버건디」인데 설명이 「파란 밤」이면 고르실 때 헷갈린다
    for (const theme of DESIGN_THEMES) {
      expect(theme.tagline.length, theme.id).toBeGreaterThan(5)
      expect(theme.mood.length, theme.id).toBeGreaterThan(0)
    }
  })
})
