import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { splashHtml } from '../desktop/splash.js'

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
    const html = splashHtml(null)
    expect(html).toContain('피아노이벤트')
    expect(html).toContain('준비하고 있습니다')
    expect(html.startsWith('<!doctype html>')).toBe(true)
  })

  it('첫 화면에 그림을 넣으면 그림이 들어간다', () => {
    expect(splashHtml('data:image/jpeg;base64,AAAA')).toContain('data:image/jpeg;base64,AAAA')
  })

  it('창을 닫으면 서버도 내린다 — 껐는데 뭔가 남아 있으면 안 된다', () => {
    expect(MAIN).toContain("app.on('window-all-closed'")
    expect(MAIN).toContain('stopServer')
  })
})
