// 피아노 앱에 붙여 넣는 패치가 실제로 학원 관리노트 키를 여는지 확인한다.
//
// 패치는 브라우저에 그대로 붙여 넣는 스크립트(모듈이 아님)라, 여기서도 같은 방식으로 실행한다.
// 피아노 앱에 이미 있는 licSelfValid / licKey 는 원본 발급기 코드로 흉내 낸다.

import { describe, it, expect, beforeAll } from 'vitest'
import { readFileSync } from 'node:fs'
import { generateKey, checksumOf, formatKey } from '../src/core/license.js'
import { generatePianoKey, pianoKeyForName, isPianoSelfValid } from '../src/core/license-piano.js'

const PATCH = readFileSync('integration/piano/학원관리노트-키-인정-패치.js', 'utf8')

/** 피아노 앱 안(기존 라이선스 코드가 이미 있는 상태)에 패치를 붙인 상황을 만든다 */
function loadPatchedApp({ withExistingCode = true } = {}) {
  const app = {}
  const prelude = withExistingCode
    ? `var licSelfValid = arguments[1]; var licKey = arguments[2];`
    : ''
  // eslint-disable-next-line no-new-func
  const run = new Function('window', 'licSelfValid_', 'licKey_', `
    ${prelude.replace('arguments[1]', 'licSelfValid_').replace('arguments[2]', 'licKey_')}
    ${PATCH}
    return window
  `)
  return run(app, isPianoSelfValid, pianoKeyForName)
}

describe('피아노 앱 패치 — 학원 관리노트 키 인정', () => {
  let app
  beforeAll(() => { app = loadPatchedApp() })

  it('통합키(A)는 Lite·Pro 모두 열린다', () => {
    for (const plan of ['lite', 'pro']) {
      const key = generateKey(plan, 'A')
      expect(app.licAnyValid(key), key).toBe(true)
      expect(app.anVerifyAcademyNoteKey(key).plan).toBe(plan)
    }
  })

  it('피아노 전용 키(K)도 열린다', () => {
    const key = generateKey('pro', 'K')
    expect(app.licAnyValid(key)).toBe(true)
    expect(app.licDescribe(key).source).toContain('피아노 관리노트 전용')
  })

  it('학원 전용 키(M)는 거부하고 이유를 알려 준다', () => {
    const key = generateKey('lite', 'M')
    expect(app.licAnyValid(key)).toBe(false)
    expect(app.licDescribe(key).reason).toContain('학원 관리노트 전용')
  })

  it('제품 문자가 없던 초기 발급분(L/P)도 열린다', () => {
    const body = 'P' + 'ABC1234'
    const key = formatKey(body + checksumOf(body))
    expect(app.licAnyValid(key)).toBe(true)
    expect(app.anVerifyAcademyNoteKey(key).plan).toBe('pro')
  })

  it('기존 피아노 키는 그대로 통과한다 (패치가 기존 동작을 건드리지 않는다)', () => {
    const selfKey = generatePianoKey()
    expect(app.licAnyValid(selfKey)).toBe(true)
    expect(app.licDescribe(selfKey).source).toContain('미리 만든 키')

    const nameKey = pianoKeyForName('아첼음악학원')
    expect(app.licAnyValid(nameKey)).toBe(false)                    // 학원명 없이는 기존과 동일하게 실패
    expect(app.licAnyValid(nameKey, '아첼음악학원')).toBe(true)
    expect(app.licDescribe(nameKey, '아첼음악학원').name).toBe('아첼음악학원')
  })

  it('아무 문자열이나 통과시키지 않는다', () => {
    for (const bad of ['', 'ABCD', 'ABCD-EFGH-JKMN', '1234-5678-9012']) {
      expect(app.licAnyValid(bad), bad).toBe(false)
    }
  })

  it('한 글자만 틀려도 거부한다', () => {
    const key = generateKey('pro', 'A').replace(/-/g, '')
    const broken = key.slice(0, 6) + (key[6] === 'A' ? 'B' : 'A') + key.slice(7)
    expect(app.licAnyValid(broken)).toBe(false)
  })

  it('하이픈·소문자·공백 표기에 관대하다', () => {
    const key = generateKey('lite', 'A')
    expect(app.licAnyValid(key.toLowerCase())).toBe(true)
    expect(app.licAnyValid(key.replace(/-/g, ''))).toBe(true)
    expect(app.licAnyValid(` ${key} `)).toBe(true)
  })

  it('안내문에 적어 둔 확인용 키가 실제로 그렇게 동작한다', () => {
    expect(app.licAnyValid('AL2H-4K7P-KGMK')).toBe(true)
    expect(app.licAnyValid('AP9R-3TQX-71C3')).toBe(true)
    expect(app.licAnyValid('KL5M-8VNC-41GX')).toBe(true)
    expect(app.licAnyValid('ML6Q-2WJD-7PG7')).toBe(false)
  })

  it('기존 라이선스 코드가 없는 곳에 붙여도 죽지 않는다', () => {
    const bare = loadPatchedApp({ withExistingCode: false })
    expect(bare.licAnyValid(generateKey('pro', 'A'))).toBe(true)
    expect(bare.licAnyValid(generatePianoKey())).toBe(false)  // 기존 함수가 없으니 피아노 키는 판정 못 함
  })
})
