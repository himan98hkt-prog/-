import { describe, expect, it } from 'vitest'
import { describePick, eventMonth, recommendDesign } from '@/lib/design/recommend'
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
