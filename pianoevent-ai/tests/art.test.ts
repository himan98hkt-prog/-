import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { APP_ART, GOLD_FLECKS, GOLD_FOIL, ORNAMENT_ART, POSTER_ART, STAGE_ART, TEXTURE_ART, getPosterArt } from '@/lib/design/art'
import { artIdOf } from '@/lib/design/art-template'
import { DESIGN_TEMPLATES, getPack, packTemplates } from '@/lib/design/templates'
import { STAGE_BACKDROPS } from '@/lib/stage/backdrops'

const PUBLIC = join(process.cwd(), 'public')
const ALL = [...POSTER_ART, ...STAGE_ART, ...ORNAMENT_ART]
const TEXTURES = [...Object.values(TEXTURE_ART), GOLD_FOIL, GOLD_FLECKS]

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

  it('사진 · 일러스트 · 선화 세 갈래가 모두 있다', () => {
    // 한쪽으로 쏠리면 고르는 뜻이 없다. 사진만 있으면 AI 티가 나고, 그림만 있으면 가볍다
    expect(POSTER_ART.filter((a) => a.tone === 'dark').length).toBeGreaterThanOrEqual(5)
    expect(POSTER_ART.filter((a) => a.tone === 'light').length).toBeGreaterThanOrEqual(5)
    expect(POSTER_ART.filter((a) => a.tone === 'line').length).toBeGreaterThanOrEqual(3)
  })

  it('선화는 테마 색으로 칠할 것이라 PNG 다 — JPEG 는 검정이 뭉개져 마스크가 지저분해진다', () => {
    for (const art of POSTER_ART.filter((a) => a.tone === 'line')) {
      expect(art.src.endsWith('.png'), art.id).toBe(true)
    }
  })

  it('막은 얇게 — 두꺼우면 그림을 고른 뜻이 없다', () => {
    for (const art of POSTER_ART.filter((a) => a.scrimTone !== 'light' && a.tone !== 'line')) {
      expect(art.scrim, art.id).toBeGreaterThanOrEqual(0)
      expect(art.scrim, art.id).toBeLessThanOrEqual(0.45)
    }
  })

  it('흰 종이에 그린 수채는 막을 깔지 않는다 — 필요가 없다', () => {
    for (const art of POSTER_ART.filter((a) => a.tone === 'light' && a.fill !== 'cover')) {
      expect(art.scrim, art.id).toBe(0)
    }
  })

  it('밝은 사진에는 흰 막을 깐다 — 검은 막을 깔면 사진을 고른 뜻이 사라진다', () => {
    for (const art of POSTER_ART.filter((a) => a.tone === 'light' && a.fill === 'cover')) {
      expect(art.scrimTone, art.id).toBe('light')
      expect(art.scrim, art.id).toBeGreaterThan(0)
    }
  })

  it('바탕 질감과 금박도 프로그램 안에 들어 있다', () => {
    for (const src of TEXTURES) {
      expect(src.startsWith('/art/'), src).toBe(true)
      expect(existsSync(join(PUBLIC, src)), src).toBe(true)
    }
  })

  it('금테두리 상장이 있다 — 시상이 있는 연주회용', () => {
    const gold = DESIGN_TEMPLATES.find((t) => t.id === 'certificate-gold')
    expect(gold).toBeTruthy()
    expect(gold!.page).toBe('a4-landscape')
    expect(gold!.perStudent).toBe(true)
  })
})

describe('그림 포스터 양식', () => {
  const ids = POSTER_ART.map((a) => a.id)

  it('그림마다 양식이 하나씩 나와 있다', () => {
    expect(ids).toHaveLength(31)
    const templates = DESIGN_TEMPLATES.filter((t) => t.id.startsWith('art-'))
    expect(templates).toHaveLength(31)
    for (const t of templates) {
      expect(t.category, t.id).toBe('poster')
      expect(t.page, t.id).toBe('a4-portrait')
    }
  })

  it('양식마다 진짜 그림이 붙는다 — 빠지면 조용히 다른 그림이 뽑힌다', () => {
    // 예전에는 양식 id 를 `switch` 에 한 줄씩 적었다. 한 줄을 빠뜨리면 원장님이 고르신 것과
    // **다른 포스터**가 뽑히는데, 화면에서는 그것이 잘못이라는 표시가 전혀 없다.
    for (const t of DESIGN_TEMPLATES.filter((x) => x.id.startsWith('art-'))) {
      const artId = artIdOf(t.id)
      expect(artId, t.id).toBeTruthy()
      expect(POSTER_ART.some((a) => a.id === artId), `${t.id} → ${artId}`).toBe(true)
    }
  })

  it('그림 포스터가 아닌 양식은 그림으로 새지 않는다', () => {
    for (const t of DESIGN_TEMPLATES.filter((x) => !x.id.startsWith('art-'))) {
      expect(artIdOf(t.id), t.id).toBeNull()
    }
  })

  it('포스터 갈래 앞쪽에 온다 — 뒤에 묻히면 고르실 일이 없다', () => {
    const posters = DESIGN_TEMPLATES.filter((t) => t.category === 'poster').map((t) => t.id)
    for (const t of posters.filter((id) => id.startsWith('art-'))) {
      expect(posters.indexOf(t), t).toBeLessThan(35)
    }
  })

  it('그림 포스터 한 벌은 용지가 하나다 — 인쇄 대화상자는 용지를 한 번만 정한다', () => {
    const pack = getPack('art')
    expect(pack).toBeTruthy()
    expect(packTemplates(pack!)).toHaveLength(pack!.templates.length)
  })
})

describe('프로그램 화면용 그림', () => {
  it('네 장이 모두 들어 있다 — 히어로 · 아이콘 · 설치 배너 · 시작 화면', () => {
    for (const src of Object.values(APP_ART)) {
      expect(src.startsWith('/art/app/'), src).toBe(true)
      expect(existsSync(join(PUBLIC, src)), src).toBe(true)
    }
  })

  it('프로그램 아이콘이 설치본에도 같이 들어간다', () => {
    // 바탕화면에 놓이는 아이콘이 제품의 첫인상이다
    expect(existsSync(join(process.cwd(), 'desktop', 'icon.png'))).toBe(true)
    expect(existsSync(join(process.cwd(), 'desktop', 'installer', 'sidebar.bmp'))).toBe(true)
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
