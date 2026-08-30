import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

/**
 * 파는 데 필요한 것들이 서로 맞물려 있는지 지킨다.
 *
 * 여기서 막고 싶은 사고는 두 가지다.
 *   ① 비밀값이 든 발급기가 저장소에 올라가는 것 — 올라가면 누구나 키를 찍어 낸다
 *   ② 업로드 묶음에서 쪽 하나가 빠지는 것 — 링크가 끊긴 채 팔리게 된다
 */

const keygen = readFileSync('web/keygen/recital-keygen.html', 'utf8')
const packer = readFileSync('scripts/pack-web.mjs', 'utf8')
const download = readFileSync('web/download/index.html', 'utf8')
const guide = readFileSync('web/download/guide.html', 'utf8')
const curriculum = readFileSync('web/커리큘럼-붙여넣기.html', 'utf8')
const workflow = readFileSync('../.github/workflows/pianoevent-installer.yml', 'utf8')

describe('인증키 발급기', () => {
  it('저장소에 있는 판에는 비밀값이 들어 있지 않다', () => {
    expect(keygen).toContain('const SECRET = "__RECITAL_LICENSE_SECRET__"')
  })

  it('프로그램과 같은 규칙을 쓴다', () => {
    // 글자표·이용형태 번호·기준일이 lib/license/key.ts 와 어긋나면 키가 안 열린다
    expect(keygen).toContain('0123456789ABCDEFGHJKMNPQRSTVWXYZ')
    expect(keygen).toContain('life:0')
    expect(keygen).toContain('year:1')
    expect(keygen).toContain('trial:2')
    expect(keygen).toContain('Date.UTC(2026,0,1)')
    expect(keygen).toContain('RM-')
  })

  it('올리지 말라는 경고가 들어 있다', () => {
    expect(keygen).toMatch(/절대 (공유|올리)/)
  })

  it('설치본과 대조할 지문을 띄운다', () => {
    // 프로그램의 secretFingerprint() 와 같은 셈이라야 두 지문이 맞는다
    expect(keygen).toContain('recital-fingerprint|')
    expect(keygen).toContain('id="fp"')
  })
})

describe('비밀 없이 뽑히는 설치본', () => {
  it('설치본 만들기가 비밀을 먼저 확인한다', () => {
    expect(workflow).toContain('scripts/check-license-secret.mjs')
    // 확인이 빌드보다 **앞에** 있어야 5분을 버리지 않는다
    expect(workflow.indexOf('check-license-secret')).toBeLessThan(workflow.indexOf('npm run desktop'))
  })

  it('비밀이 없으면 멈춘다 (경고만 하고 넘어가지 않는다)', async () => {
    const { usingDevSecret } = await import('../lib/license/key.ts')
    const before = process.env.RECITAL_LICENSE_SECRET
    delete process.env.RECITAL_LICENSE_SECRET
    expect(usingDevSecret()).toBe(true)
    process.env.RECITAL_LICENSE_SECRET = 'x'
    expect(usingDevSecret()).toBe(false)
    if (before === undefined) delete process.env.RECITAL_LICENSE_SECRET
    else process.env.RECITAL_LICENSE_SECRET = before
  })

  it('지문은 비밀이 다르면 달라진다', async () => {
    const { secretFingerprint } = await import('../lib/license/key.ts')
    const before = process.env.RECITAL_LICENSE_SECRET
    process.env.RECITAL_LICENSE_SECRET = 'aaa'
    const a = secretFingerprint()
    process.env.RECITAL_LICENSE_SECRET = 'bbb'
    expect(secretFingerprint()).not.toBe(a)
    expect(a).toMatch(/^[0-9A-F]{8}$/)
    if (before === undefined) delete process.env.RECITAL_LICENSE_SECRET
    else process.env.RECITAL_LICENSE_SECRET = before
  })
})

describe('홈페이지에 올리는 묶음', () => {
  it('받는 자리·사용설명서·상세페이지가 모두 담긴다', () => {
    for (const file of ['index.html', 'guide.html', 'recital-manager-detail.html', '.htaccess']) {
      expect(packer).toContain(`'${file}'`)
    }
  })

  it('폴더 없이 납작하게 묶는다', () => {
    expect(packer).toContain("'-j'")
  })
})

describe('고객이 보는 쪽', () => {
  it('받는 자리에서 사용설명서로 갈 수 있다', () => {
    expect(download).toContain('guide.html')
  })

  it('사용설명서에서 받는 자리로 돌아올 수 있다', () => {
    expect(guide).toContain('index.html')
  })

  it('사용설명서에 설치·인증·문제 해결이 모두 있다', () => {
    for (const part of ['설치하기', '인증키 넣기', '이럴 때는 이렇게', 'RM-XXXXX-XXXXX-XXXXX-XXXXX']) {
      expect(guide).toContain(part)
    }
  })

  it('커리큘럼에 받는 단추와 설명서 링크가 있다', () => {
    expect(curriculum).toContain('https://accelssam.com/download/')
    expect(curriculum).toContain('https://accelssam.com/download/guide.html')
    expect(curriculum).toContain('구매 후 이렇게 받으십니다')
  })
})
