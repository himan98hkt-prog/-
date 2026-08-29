import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { ORNAMENT_ART, POSTER_ART, STAGE_ART, getPosterArt } from '@/lib/design/art'
import { DESIGN_TEMPLATES, getPack, packTemplates } from '@/lib/design/templates'
import { STAGE_BACKDROPS } from '@/lib/stage/backdrops'

const PUBLIC = join(process.cwd(), 'public')
const ALL = [...POSTER_ART, ...STAGE_ART, ...ORNAMENT_ART]

describe('연주회 그림', () => {
  it('id 가 겹치지 않는다', () => {
    expect(new Set(ALL.map((a) => a.id)).size).toBe(ALL.length)
  })

  it('파일이 실제로 들어 있다 — 없으면 원장님 화면에 빈 네모가 뜬다', () => {
    for (const art of ALL) {
      expect(art.src.startsWith('/art/'), art.id).toBe(true)
      expect(existsSync(join(PUBLIC, art.src)), art.src).toBe(true)
    }
  })

  it('그림은 프로그램 안에 들어 있다 — 밖에서 불러오지 않는다', () => {
    // 인터넷이 끊긴 학원에서도 인쇄물이 나와야 한다
    for (const art of ALL) expect(art.src, art.id).not.toMatch(/^https?:/)
  })

  it('모르는 id 는 첫 그림으로 떨어진다', () => {
    expect(getPosterArt('없는그림').id).toBe(POSTER_ART[0].id)
  })

  it('어두운 그림과 밝은 그림이 모두 있다', () => {
    expect(POSTER_ART.some((a) => a.tone === 'dark')).toBe(true)
    expect(POSTER_ART.some((a) => a.tone === 'light')).toBe(true)
  })

  it('막은 얇게 — 두꺼우면 그림을 고른 뜻이 없다', () => {
    for (const art of POSTER_ART) {
      expect(art.scrim, art.id).toBeGreaterThanOrEqual(0)
      expect(art.scrim, art.id).toBeLessThanOrEqual(0.45)
    }
  })

  it('밝은 그림은 막을 깔지 않는다 — 흰 종이에 그린 것이라 필요가 없다', () => {
    for (const art of POSTER_ART.filter((a) => a.tone === 'light')) {
      expect(art.scrim, art.id).toBe(0)
    }
  })
})

describe('그림 포스터 양식', () => {
  const ids = POSTER_ART.map((a) => a.id)

  it('그림 여덟 장이 모두 양식으로 나와 있다', () => {
    expect(ids).toHaveLength(8)
    const templates = DESIGN_TEMPLATES.filter((t) => t.id.startsWith('art-'))
    expect(templates).toHaveLength(8)
    for (const t of templates) {
      expect(t.category, t.id).toBe('poster')
      expect(t.page, t.id).toBe('a4-portrait')
    }
  })

  it('포스터 갈래 앞쪽에 온다 — 뒤에 묻히면 고르실 일이 없다', () => {
    const posters = DESIGN_TEMPLATES.filter((t) => t.category === 'poster').map((t) => t.id)
    for (const t of posters.filter((id) => id.startsWith('art-'))) {
      expect(posters.indexOf(t), t).toBeLessThan(12)
    }
  })

  it('그림 포스터 한 벌은 용지가 하나다 — 인쇄 대화상자는 용지를 한 번만 정한다', () => {
    const pack = getPack('art')
    expect(pack).toBeTruthy()
    expect(packTemplates(pack!)).toHaveLength(pack!.templates.length)
  })
})

describe('사진 무대 배경', () => {
  it('네 가지가 목록에 있다', () => {
    const photo = STAGE_BACKDROPS.filter((b) => b.id.startsWith('photo-'))
    expect(photo).toHaveLength(4)
    for (const b of photo) expect(b.hint.length).toBeGreaterThan(5)
  })

  it('사진 배경마다 실제 그림이 있다', () => {
    for (const b of STAGE_BACKDROPS.filter((x) => x.id.startsWith('photo-'))) {
      const art = STAGE_ART.find((a) => b.id === `photo-${a.id}` || b.id === 'photo-keys')
      expect(art, b.id).toBeTruthy()
    }
  })
})
