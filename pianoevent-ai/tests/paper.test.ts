import { describe, expect, it } from 'vitest'
import {
  PAPERS,
  PAPER_LIST,
  PRINT_CHECKLIST,
  fitScale,
  getPaper,
  pageBreakOffsets,
  sheetsNeeded,
  totalSheets,
} from '@/lib/print/paper'

describe('종이 고르기', () => {
  it('모르는 이름은 A4 세로로 본다 — 원장님이 가장 많이 쓰신다', () => {
    expect(getPaper(undefined).id).toBe('a4-portrait')
    expect(getPaper('없는종이').id).toBe('a4-portrait')
  })

  it('아는 이름은 그대로 준다', () => {
    expect(getPaper('a4-landscape').label).toBe('A4 가로')
  })

  it('모든 종이가 가로·세로와 인쇄용 낱말을 갖고 있다', () => {
    for (const paper of PAPER_LIST) {
      expect(paper.w).toBeGreaterThan(0)
      expect(paper.h).toBeGreaterThan(0)
      expect(paper.css.length).toBeGreaterThan(0)
    }
  })
})

describe('몇 장이 나오는지', () => {
  const a4 = PAPERS['a4-portrait']

  it('한 장에 들어가면 한 장', () => {
    expect(sheetsNeeded(800, a4)).toBe(1)
  })

  it('딱 맞게 채워도 한 장이다 — 반올림으로 빈 장이 붙으면 안 된다', () => {
    expect(sheetsNeeded(a4.h, a4)).toBe(1)
  })

  it('조금이라도 넘치면 두 장', () => {
    expect(sheetsNeeded(a4.h + 40, a4)).toBe(2)
  })

  it('빈 내용도 한 장은 나온다', () => {
    expect(sheetsNeeded(0, a4)).toBe(1)
    expect(sheetsNeeded(Number.NaN, a4)).toBe(1)
  })

  it('여백을 잡으면 들어가는 높이가 줄어 장수가 는다', () => {
    expect(sheetsNeeded(1100, a4, 0)).toBe(1)
    expect(sheetsNeeded(1100, a4, 60)).toBe(2)
  })
})

describe('잘리는 자리', () => {
  const a4 = PAPERS['a4-portrait']

  it('한 장이면 그을 곳이 없다', () => {
    expect(pageBreakOffsets(500, a4)).toEqual([])
  })

  it('세 장이면 두 군데를 긋는다', () => {
    expect(pageBreakOffsets(a4.h * 2.5, a4)).toEqual([a4.h, a4.h * 2])
  })
})

describe('창에 맞추기', () => {
  it('좁은 창에서는 줄인다', () => {
    expect(fitScale(397, PAPERS['a4-portrait'])).toBeCloseTo(0.5, 2)
  })

  it('넓어도 키우지는 않는다 — 확대는 오히려 헷갈린다', () => {
    expect(fitScale(3000, PAPERS['a4-portrait'])).toBe(1)
  })
})

describe('인쇄 대화상자 안내', () => {
  it('배율·여백·배경 그래픽을 모두 짚는다 — 인쇄를 망치는 세 가지다', () => {
    const all = PRINT_CHECKLIST.map((c) => c.what).join(' ')
    expect(all).toContain('배율')
    expect(all).toContain('여백')
    expect(all).toContain('배경 그래픽')
  })
})

describe('부수까지 곱한 종이', () => {
  it('두 장짜리를 100부 뽑으면 200장이다', () => {
    expect(totalSheets(2, 100)).toBe(200)
  })

  it('0부는 없다', () => {
    expect(totalSheets(2, 0)).toBe(2)
  })
})
