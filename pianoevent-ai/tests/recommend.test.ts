import { describe, expect, it } from 'vitest'
import { describePick, eventMonth, recommendDesign, recommendDesigns } from '@/lib/design/recommend'
import { getTheme } from '@/lib/design/themes'
import { getTemplate } from '@/lib/design/templates'

const march = '2027-03-14T09:00:00.000Z'
const october = '2026-10-10T09:00:00.000Z'

describe('행사 달 읽기', () => {
  it('행사 날짜의 달을 쓴다', () => {
    expect(eventMonth(march)).toBe(3)
  })

  it('날짜가 망가졌으면 이번 달로 본다 — 멈추는 것보다 낫다', () => {
    expect(eventMonth('날짜아님', new Date(2026, 6, 1))).toBe(7)
  })
})

describe('인쇄물을 미리 정해 드리기', () => {
  it('행사 달에 어울리는 테마를 고른다', () => {
    const spring = recommendDesign({ eventAt: march, hasProgram: true })
    const autumn = recommendDesign({ eventAt: october, hasProgram: true })
    expect(spring.themeId).not.toBe(autumn.themeId)
    expect(getTheme(spring.themeId).id).toBe(spring.themeId)
  })

  it('왜 골랐는지 사람 말로 적어 준다 — 이유가 없으면 못 믿으신다', () => {
    expect(recommendDesign({ eventAt: october, hasProgram: true }).why).toContain('가을')
    expect(recommendDesign({ eventAt: march, hasProgram: true }).why).toContain('봄')
  })

  it('순서표가 있으면 순서가 들어간 포스터를 권한다', () => {
    expect(recommendDesign({ eventAt: march, hasProgram: true }).templateId).toBe('poster-program')
  })

  it('순서표가 아직 없으면 순서 없이도 되는 포스터를 권한다', () => {
    const pick = recommendDesign({ eventAt: march, hasProgram: false })
    expect(getTemplate(pick.templateId).needsProgram).toBe(false)
  })

  it('이미 고르신 것이 있으면 건드리지 않는다 — 덮으면 더 놀라신다', () => {
    const pick = recommendDesign({
      eventAt: march,
      hasProgram: true,
      themeId: 'midnight-stage',
      templateId: 'poster-typographic',
    })
    expect(pick.themeId).toBe('midnight-stage')
    expect(pick.templateId).toBe('poster-typographic')
    expect(pick.why).toContain('지난번에 고르신')
  })

  it('권하는 것은 늘 실제로 있는 테마와 양식이다', () => {
    for (let month = 1; month <= 12; month += 1) {
      const at = `2026-${String(month).padStart(2, '0')}-10T09:00:00.000Z`
      const pick = recommendDesign({ eventAt: at, hasProgram: true })
      expect(getTheme(pick.themeId).id, `${month}월`).toBe(pick.themeId)
      expect(getTemplate(pick.templateId).id, `${month}월`).toBe(pick.templateId)
    }
  })

  it('무엇을 골랐는지 한 줄로 보여 준다', () => {
    const pick = recommendDesign({ eventAt: october, hasProgram: true })
    expect(describePick(pick)).toContain('·')
    expect(describePick(pick)).toContain(getTheme(pick.themeId).name)
  })
})

describe('견주어 보실 세 장', () => {
  it('셋을 준다 — 하나면 막히고 100종이면 못 고르신다', () => {
    expect(recommendDesigns({ eventAt: march, hasProgram: true })).toHaveLength(3)
  })

  it('첫 장은 미리 정해 드린 그것이다 — 화면과 설명이 어긋나면 안 된다', () => {
    const input = { eventAt: october, hasProgram: true }
    const [first] = recommendDesigns(input)
    const pick = recommendDesign(input)
    expect(first.themeId).toBe(pick.themeId)
    expect(first.templateId).toBe(pick.templateId)
    expect(first.why).toBe(pick.why)
  })

  it('셋이 서로 다른 테마다 — 같은 그림이 셋이면 고를 것이 없다', () => {
    const ids = recommendDesigns({ eventAt: march, hasProgram: true }).map((s) => s.themeId)
    expect(new Set(ids).size).toBe(3)
  })

  it('셋 다 같은 양식이다 — 달라지는 것은 느낌뿐이라야 견줄 수 있다', () => {
    const picks = recommendDesigns({ eventAt: march, hasProgram: true })
    expect(new Set(picks.map((s) => s.templateId)).size).toBe(1)
  })

  it('담백한 쪽과 화려한 쪽이 함께 있다', () => {
    const kinds = recommendDesigns({ eventAt: march, hasProgram: true }).map((s) => s.kind)
    expect(kinds).toContain('plain')
    expect(kinds).toContain('fancy')
  })

  it('이미 고르신 것이 있으면 그것이 첫 장으로 온다', () => {
    const picks = recommendDesigns({ eventAt: march, hasProgram: true, themeId: 'midnight-stage' })
    expect(picks[0].kind).toBe('chosen')
    expect(picks[0].themeId).toBe('midnight-stage')
    expect(picks).toHaveLength(3)
  })

  it('자리 셋이 늘 같다 — 이대로 · 담백 · 화려. 자리가 바뀌면 아까 그건 어디 갔나가 된다', () => {
    for (const themeId of [null, 'midnight-stage']) {
      const kinds = recommendDesigns({ eventAt: march, hasProgram: true, themeId }).map((s) => s.kind)
      expect(kinds.slice(1), String(themeId)).toEqual(['plain', 'fancy'])
      expect(kinds[0], String(themeId)).toBe(themeId ? 'chosen' : 'season')
    }
  })

  it('카드마다 한마디가 붙는다 — 무엇이 다른지 글로도 알아야 한다', () => {
    for (const pick of recommendDesigns({ eventAt: october, hasProgram: true })) {
      expect(pick.label.length).toBeGreaterThan(1)
      expect(pick.why.length).toBeGreaterThan(4)
    }
  })

  it('어느 달이든 셋이 다 실제로 있는 테마와 양식이다', () => {
    for (let month = 1; month <= 12; month += 1) {
      const at = `2026-${String(month).padStart(2, '0')}-10T09:00:00.000Z`
      for (const pick of recommendDesigns({ eventAt: at, hasProgram: month % 2 === 0 })) {
        expect(getTheme(pick.themeId).id, `${month}월`).toBe(pick.themeId)
        expect(getTemplate(pick.templateId).id, `${month}월`).toBe(pick.templateId)
      }
    }
  })
})
