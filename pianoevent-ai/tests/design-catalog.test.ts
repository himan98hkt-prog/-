import { describe, expect, it } from 'vitest'
import { GET } from '@/app/api/design/catalog/route'
import { DESIGN_TEMPLATES } from '@/lib/design/templates'
import { DESIGN_THEMES } from '@/lib/design/themes'

/**
 * 대비 검사 스크립트가 「무엇을 잴지」를 이 자리에서 읽는다.
 * 여기가 비거나 모양이 바뀌면 검사가 조용히 아무것도 안 재게 된다 —
 * 실패가 없다고 나오는데 사실은 검사를 안 한 것이다. 그게 가장 나쁘다.
 */
describe('디자인 목록 (검사 도구가 읽는 자리)', () => {
  it('양식과 테마를 하나도 빠짐없이 알려 준다', async () => {
    const body = await (GET() as Response).json()
    expect(body.templates).toHaveLength(DESIGN_TEMPLATES.length)
    expect(body.themes).toHaveLength(DESIGN_THEMES.length)
  })

  it('그림 포스터가 전부 들어 있다 — 새로 넣은 그림이 검사에서 빠지면 안 된다', async () => {
    const body = await (GET() as Response).json()
    const art = body.templates.filter((t: { id: string }) => t.id.startsWith('art-'))
    expect(art.length).toBe(DESIGN_TEMPLATES.filter((t) => t.id.startsWith('art-')).length)
    expect(art.length).toBeGreaterThanOrEqual(23)
  })

  it('테마마다 색이 다 들어 있다 — 색만 갈아 끼우며 재기 때문이다', async () => {
    const body = await (GET() as Response).json()
    for (const theme of body.themes) {
      for (const key of ['paper', 'paperAlt', 'ink', 'muted', 'accent', 'accentSoft', 'line', 'band', 'bandInk']) {
        expect(theme.palette[key], `${theme.id}.${key}`).toMatch(/^#[0-9a-fA-F]{6}$/)
      }
      expect(theme.fonts.display).toBeTruthy()
      expect(theme.fonts.body).toBeTruthy()
    }
  })

  it('디자인 상수 말고는 아무것도 나가지 않는다 — 아이 이름·사진이 새면 안 된다', async () => {
    const body = await (GET() as Response).json()
    expect(Object.keys(body).sort()).toEqual(['templates', 'themes'])
    for (const t of body.templates) {
      expect(Object.keys(t).sort()).toEqual(['category', 'id', 'name', 'page'])
    }
    for (const t of body.themes) {
      expect(Object.keys(t).sort()).toEqual(['family', 'fonts', 'id', 'name', 'palette'])
    }
  })
})
