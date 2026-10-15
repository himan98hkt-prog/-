import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { splashHtml } from '../desktop/splash.js'
import SHELL_BRAND from '../desktop/brand.js'
import { BRAND } from '@/lib/brand'

const ROOT = join(__dirname, '..')
const MAIN = readFileSync(join(ROOT, 'desktop', 'main.js'), 'utf8')
const BUILDER = readFileSync(join(ROOT, 'electron-builder.yml'), 'utf8')

/**
 * 설치본은 여기서 못 뽑아 본다. 뽑아 보는 데 20분이 걸리고, 잘못은 원장님 컴퓨터에서야
 * 드러난다 — 「설치는 됐는데 안 켜져요」가 가장 나쁜 실패다.
 *
 * 그래서 **껍데기가 부르는 파일이 설치본에 실리는가**만이라도 여기서 본다.
 * 실제로 첫 화면을 따로 떼어 낼 때 이 목록에 넣는 것을 잊어 그대로 나갈 뻔했다.
 */
describe('설치본 껍데기', () => {
  it('main.js 가 부르는 우리 파일이 설치본 목록에 모두 들어 있다', () => {
    const required = [...MAIN.matchAll(/require\('\.\/([\w.-]+)'\)/g)].map((m) => m[1])
    expect(required.length).toBeGreaterThan(0)
    for (const name of required) {
      // 검사용으로만 부르는 것은 배포본에 없어도 된다(있으면 쓰고 없으면 넘어간다)
      if (name.startsWith('_')) continue
      expect(BUILDER.includes(`desktop/${name}`), `${name} 가 electron-builder.yml files 에 없습니다`).toBe(true)
    }
  })

  it('첫 화면은 그림이 없어도 뜬다 — 그림 하나 때문에 프로그램이 안 열리면 안 된다', () => {
    const html = splashHtml(null, null)
    expect(html).toContain(BRAND.name)
    expect(html).toContain(BRAND.maker)
    expect(html).toContain('준비하고 있습니다')
    expect(html.startsWith('<!doctype html>')).toBe(true)
  })

  it('첫 화면에 무대 사진과 로고가 들어간다', () => {
    const html = splashHtml('data:image/jpeg;base64,AAAA', 'data:image/png;base64,BBBB')
    expect(html).toContain('data:image/jpeg;base64,AAAA')
    expect(html).toContain('data:image/png;base64,BBBB')
  })

  it('껍데기와 본체가 같은 상품 이름을 쓴다 — 창 제목만 옛 이름으로 남으면 안 된다', () => {
    expect(SHELL_BRAND.name).toBe(BRAND.name)
    expect(SHELL_BRAND.nameEn).toBe(BRAND.nameEn)
    expect(SHELL_BRAND.maker).toBe(BRAND.maker)
    expect(SHELL_BRAND.slug).toBe(BRAND.slug)
  })

  it('첨부물 청소기가 지금 상품의 설치본을 지키게 되어 있다', () => {
    // 여기 이름을 손으로 적어 두었더니, 상품 이름을 바꾼 날 **새로 올린 설치본을**
    // 옛것으로 보고 지워 버렸다. 빌드는 전부 성공인데 받는 자리에는 옛 파일만 남았다.
    const cleaner = readFileSync(join(ROOT, 'scripts', 'clean-release-assets.mjs'), 'utf8')
    expect(cleaner).toContain('BRAND.slug')
    expect(cleaner).not.toMatch(/startsWith\('[A-Za-z]+-'\)/)
  })

  it('설치본 파일 이름과 상품 이름이 어긋나지 않는다', () => {
    const builder = readFileSync(join(ROOT, 'electron-builder.yml'), 'utf8')
    expect(builder).toContain(`productName: ${BRAND.name}`)
    expect(builder).toContain(`${BRAND.slug}-Setup-Windows`)
  })

  it('창을 닫으면 서버도 내린다 — 껐는데 뭔가 남아 있으면 안 된다', () => {
    expect(MAIN).toContain("app.on('window-all-closed'")
    expect(MAIN).toContain('stopServer')
  })
})
