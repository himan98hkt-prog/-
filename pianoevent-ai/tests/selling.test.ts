import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
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
const embed = readFileSync('web/상세페이지-붙여넣기.html', 'utf8')
const detail = readFileSync('web/download/recital-manager-detail.html', 'utf8')

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

  it('상품 편집 화면에 붙여넣는 글 셋도 함께 담긴다', () => {
    // 따로 드리면 「어느 것이 최신인지」가 금방 어긋난다
    for (const file of ['상세페이지-붙여넣기.html', '상품요약설명-붙여넣기.html', '커리큘럼-붙여넣기.html']) {
      expect(packer).toContain(file)
    }
  })

  it('폴더 없이 납작하게, 한글 이름이 깨지지 않게 묶는다', () => {
    /*
     * 예전에는 `zip -j` 를 쓰는지만 봤다 — **연장을 본 것이지 결과를 본 것이 아니다.**
     * 실제로 봐야 하는 것은 둘이다:
     *   · 압축 안에 폴더가 없어야 한다(푼 자리에 파일이 그대로 나와야 하므로)
     *   · 이름이 UTF-8 이라고 적혀 있어야 한다(`zip -j` 는 그 표시를 안 붙여 한글이 깨진다)
     */
    const zip = join(process.cwd(), 'web', 'recital-upload.zip')
    if (!existsSync(zip)) return // 아직 안 만들었으면 건너뛴다 (npm run pack:web)
    const bytes = readFileSync(zip)
    const names: string[] = []
    let utf8 = true
    for (let i = 0; i + 30 < bytes.length; i += 1) {
      if (bytes.readUInt32LE(i) !== 0x04034b50) continue
      const flag = bytes.readUInt16LE(i + 6)
      const len = bytes.readUInt16LE(i + 26)
      names.push(bytes.subarray(i + 30, i + 30 + len).toString('utf8'))
      if ((flag & 0x0800) === 0) utf8 = false
    }
    expect(names.length).toBeGreaterThan(4)
    expect(names.some((n) => n.includes('/'))).toBe(false)
    expect(utf8).toBe(true)
    expect(names).toContain('상세페이지-붙여넣기.html')
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

  it('상세페이지가 화면 끝까지 늘어나지 않고 가운데 선다', () => {
    // 예전 코드가 clientWidth 로 늘리고 음수 여백으로 당겨 1920px 에서 글이 퍼졌다
    expect(embed).not.toContain('clientWidth')
    expect(embed).not.toContain('marginLeft')
    expect(embed).toContain('margin:0 auto')
    expect(embed).toContain('max-width')
  })

  it('붙여넣을 코드에 스크립트가 없다', () => {
    // 워드프레스가 <script> 를 지워서 상세페이지가 600px 에서 잘린 적이 있다.
    // 주석 안의 <script> 는 설명글이므로 빼고 본다
    expect(embed.replace(/<!--[\s\S]*?-->/g, '')).not.toMatch(/<script/i)
  })

  it('상세페이지가 제 높이를 스스로 맞춘다', () => {
    // 같은 도메인이라 자기를 담은 틀을 직접 잡을 수 있다 — 상품 쪽 코드가 필요 없다
    expect(detail).toContain('window.frameElement')
    // 틀 높이를 따라 커지는 scrollHeight 로 재면 한 번 커진 높이가 안 줄어든다
    expect(detail).toContain('kids[i].offsetTop')
    expect(detail).toContain('accel-recital-measure')
  })

  it('커리큘럼에 받는 단추와 설명서 링크가 있다', () => {
    expect(curriculum).toContain('https://accelssam.com/download/')
    expect(curriculum).toContain('https://accelssam.com/download/guide.html')
    expect(curriculum).toContain('구매 후 이렇게 받으십니다')
  })
})
