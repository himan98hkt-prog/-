import { describe, it, expect } from 'vitest'
import { extractKey, keyFromLocation, generateKey, verifyKey } from '../src/core/license.js'
import { generatePianoKey, pianoKeyForName } from '../src/core/license-piano.js'
import { buyUrl, trialNotice, STORE } from '../src/core/store.js'

describe('인증키 찾아내기 — 손으로 옮겨 적지 않아도 되게', () => {
  it('메일 본문을 통째로 붙여 넣어도 키를 찾는다', () => {
    const key = generateKey('pro', 'A')
    const mail = `김원장님, 구매해 주셔서 감사합니다.\n\n내 인증키\n${key}\n\n눌러서 바로 시작하기\n주문 wc:1001:11:1`
    expect(extractKey(mail)).toBe(key)
  })

  it('피아노 관리노트 키(공용키)도 찾는다', () => {
    const key = generatePianoKey()
    expect(extractKey(`인증키는 ${key} 입니다. 감사합니다.`)).toBe(key)
  })

  it('글 속에 비슷한 모양이 섞여 있어도 진짜 키를 고른다', () => {
    const key = generateKey('lite', 'M')
    expect(extractKey(`주문번호 2026-1116-0042 / 연락처 0101-2345-6789 / 인증키 ${key}`)).toBe(key)
  })

  it('하이픈 없이 붙여 써도, 소문자여도 된다', () => {
    const key = generateKey('pro', 'A')
    expect(extractKey(key.replace(/-/g, '').toLowerCase())).toBe(key)
    expect(extractKey(`키: ${key.toLowerCase()}`)).toBe(key)
  })

  it('키 바로 뒤에 글자가 붙어 있어도 찾는다', () => {
    const key = generateKey('pro', 'A')
    expect(extractKey(`${key}입니다`)).toBe(key)
  })

  it('학원명이 있어야 풀리는 키는 모양만 보고 돌려준다 (검증은 학원명을 받은 뒤에)', () => {
    const key = pianoKeyForName('아첼음악학원')
    expect(verifyKey(key).ok).toBe(false)
    expect(extractKey(`인증키: ${key}`)).toBe(key)
    expect(extractKey(`인증키: ${key}`, { academyName: '아첼음악학원' })).toBe(key)
  })

  it('키가 없으면 빈 문자열', () => {
    expect(extractKey('안녕하세요 문의드립니다')).toBe('')
    expect(extractKey('')).toBe('')
  })
})

describe('메일의 "눌러서 바로 시작하기" 주소', () => {
  it('#key= 로 온 키를 읽는다 (플러그인이 만드는 형식)', () => {
    expect(keyFromLocation({ hash: '#key=AP9R-3TQX-71C3' })).toEqual({ key: 'AP9R-3TQX-71C3', name: '' })
  })

  it('?key= 와 학원명도 읽는다', () => {
    const res = keyFromLocation({ search: `?key=xvxa-fggn-97ku&name=${encodeURIComponent('아첼음악학원')}` })
    expect(res).toEqual({ key: 'XVXA-FGGN-97KU', name: '아첼음악학원' })
  })

  it('화면 이동용 주소(#attendance 등)는 키로 보지 않는다', () => {
    expect(keyFromLocation({ hash: '#attendance' })).toBeNull()
    expect(keyFromLocation({ hash: '', search: '' })).toBeNull()
    expect(keyFromLocation({ hash: '#key=짧음' })).toBeNull()
  })
})

describe('구매 안내', () => {
  it('구매 주소에 어느 화면에서 눌렀는지 남긴다', () => {
    const url = new URL(buyUrl('trial'))
    expect(url.origin + url.pathname).toBe(new URL(STORE.buyUrl).origin + new URL(STORE.buyUrl).pathname)
    expect(url.searchParams.get('from')).toBe('app-trial')
  })

  it('체험이 끝나 갈수록 말투가 분명해진다', () => {
    expect(trialNotice(12).tone).toBe('info')
    expect(trialNotice(3).tone).toBe('warn')
    expect(trialNotice(1).tone).toBe('danger')
    expect(trialNotice(12).text).toContain('12일')
    expect(trialNotice(1).text).toContain('오늘')
  })

  it('어느 단계든 "자료는 그대로 이어진다"는 것을 알린다', () => {
    for (const d of [14, 3, 1]) expect(trialNotice(d).text).toContain('그대로')
  })
})
