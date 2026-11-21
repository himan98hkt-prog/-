// 피아노 관리노트 키 규칙 이식 검증.
// 기준값은 첨부받은 판매자 발급기(pambookkey.html)의 코드를 그대로 실행해 뽑은 것이다.
// 이 값이 하나라도 달라지면 이미 판매된 고객 키가 열리지 않는다는 뜻이므로 절대 손대지 말 것.

import { describe, it, expect } from 'vitest'
import {
  PIANO_SALT, PIANO_CHARS, pianoKeyForName, pianoCheckDigits, isPianoSelfValid,
  matchesPianoName, pianoNormalizeName, generatePianoKey, verifyPianoKey, formatPianoKey
} from '../src/core/license-piano.js'

describe('피아노 관리노트 키 — 원본과 같은 값이 나오는가', () => {
  it('salt 와 문자표가 원본과 같다', () => {
    expect(PIANO_SALT).toBe('PAL-x7Qm3vK9nR-accelssam-2026')
    expect(PIANO_CHARS).toBe('ACDEFGHJKLMNPQRTUVWXY34679')
    expect(PIANO_CHARS).toHaveLength(26)
  })

  it('학원명 방식 키가 원본 발급기와 한 글자도 다르지 않다', () => {
    expect(pianoKeyForName('아첼음악학원')).toBe('XVXA-FGGN-97KU')
    expect(pianoKeyForName('가온피아노학원')).toBe('FQQH-9TRV-XTAV')
    expect(pianoKeyForName('아라 잉글리시')).toBe('UTVE-JUVP-7WQ3')
    expect(pianoKeyForName('Test Academy')).toBe('EFLA-64YE-NKG6')
    expect(pianoKeyForName('아첼 음악학원 (강남)')).toBe('RNUP-GUGG-NURQ')
  })

  it('검증코드(자기검증 방식)도 원본과 같다', () => {
    expect(pianoCheckDigits('ACDEFGHJ')).toBe('PYDG')
    expect(pianoCheckDigits('79AK3MCU')).toBe('ADYC')
    expect(pianoCheckDigits('XXXXXXXX')).toBe('AUKD')
  })

  it('원본 안내문에 예시로 적힌 키가 실제로 유효하다', () => {
    expect(isPianoSelfValid('79AK-3MCU-ADYC')).toBe(true)
  })
})

describe('학원명 표기 흔들림', () => {
  it('공백·괄호·가운뎃점·하이픈·대소문자를 흡수한다', () => {
    expect(pianoNormalizeName('아첼 음악학원 (강남)')).toBe('아첼음악학원강남')
    expect(pianoKeyForName('아첼 음악학원 (강남)')).toBe(pianoKeyForName('아첼음악학원강남'))
    expect(pianoKeyForName('Test Academy')).toBe(pianoKeyForName('test-academy'))
  })

  it('이름이 다르면 키도 다르다', () => {
    expect(pianoKeyForName('아첼음악학원')).not.toBe(pianoKeyForName('아첼음악학원2'))
  })
})

describe('키 판정', () => {
  it('자기검증 키는 학원명 없이 통과한다', () => {
    for (let i = 0; i < 200; i++) {
      const key = generatePianoKey()
      expect(isPianoSelfValid(key), key).toBe(true)
      expect(verifyPianoKey(key).mode).toBe('self')
    }
  })

  it('발급한 키는 원본 문자표만 쓴다', () => {
    const key = generatePianoKey().replace(/-/g, '')
    for (const ch of key) expect(PIANO_CHARS).toContain(ch)
  })

  it('학원명 방식 키는 학원명을 넣어야 통과한다', () => {
    const key = pianoKeyForName('아첼음악학원')
    expect(verifyPianoKey(key).ok).toBe(false)
    expect(verifyPianoKey(key, { academyName: '아첼음악학원' })).toMatchObject({ ok: true, mode: 'name' })
    expect(verifyPianoKey(key, { academyName: '다른학원' }).ok).toBe(false)
  })

  it('한 글자만 바꿔도 거부한다', () => {
    const key = generatePianoKey().replace(/-/g, '')
    const broken = key.slice(0, 5) + (key[5] === 'A' ? 'C' : 'A') + key.slice(6)
    expect(isPianoSelfValid(broken)).toBe(false)
  })

  it('자릿수가 다르거나 빈 값은 거부한다', () => {
    for (const bad of ['', 'ABCD', '79AK-3MCU-ADY', '79AK-3MCU-ADYCC']) {
      expect(verifyPianoKey(bad).ok).toBe(false)
    }
  })

  it('하이픈·소문자·공백 표기에 관대하다', () => {
    const key = generatePianoKey()
    expect(isPianoSelfValid(key.toLowerCase())).toBe(true)
    expect(isPianoSelfValid(key.replace(/-/g, ''))).toBe(true)
    expect(isPianoSelfValid(` ${key} `)).toBe(true)
    expect(matchesPianoName(' xvxa fggn 97ku ', '아첼음악학원')).toBe(true)
  })

  it('표기는 4자씩 끊는다', () => {
    expect(formatPianoKey('79ak3mcuadyc')).toBe('79AK-3MCU-ADYC')
  })
})
