import { describe, it, expect } from 'vitest'
import { generateKey, verifyKey, normalizeKey, formatKey, checksumOf, hashKey, LICENSE_SALT } from '../src/core/license.js'

describe('라이선스 키', () => {
  it('발급한 키는 항상 검증을 통과한다', () => {
    for (let i = 0; i < 300; i++) {
      const plan = i % 2 ? 'pro' : 'lite'
      const key = generateKey(plan)
      const res = verifyKey(key)
      expect(res.ok, `${key} 검증 실패`).toBe(true)
      expect(res.plan).toBe(plan)
    }
  })

  it('플랜 문자로 Lite/Pro 를 구분한다', () => {
    expect(normalizeKey(generateKey('lite'))[0]).toBe('L')
    expect(normalizeKey(generateKey('pro'))[0]).toBe('P')
  })

  it('표기 형식(대소문자·하이픈)에 관대하다', () => {
    const key = generateKey('pro')
    expect(verifyKey(key.toLowerCase()).ok).toBe(true)
    expect(verifyKey(key.replace(/-/g, '')).ok).toBe(true)
    expect(verifyKey(` ${key} `).ok).toBe(true)
  })

  it('한 글자만 틀려도 거부한다 (체크섬)', () => {
    const key = normalizeKey(generateKey('pro'))
    let rejected = 0
    const B32 = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
    for (let i = 1; i < 12; i++) {
      for (const ch of B32) {
        if (key[i] === ch) continue
        const broken = key.slice(0, i) + ch + key.slice(i + 1)
        if (!verifyKey(broken).ok) rejected++
      }
    }
    // 4자 체크섬(20비트)이라 이론상 극소수 충돌은 가능하지만 99% 이상 잡아야 한다
    const total = 11 * 31
    expect(rejected / total).toBeGreaterThan(0.99)
  })

  it('아무 문자열이나 통과시키지 않는다', () => {
    for (const bad of ['', 'ABCD', 'ABCD-EFGH-IJKL', '1234-5678-9012', 'XXXX-XXXX-XXXX']) {
      expect(verifyKey(bad).ok).toBe(false)
    }
  })

  it('플랜 문자가 L/P 가 아니면 거부한다', () => {
    const key = normalizeKey(generateKey('pro'))
    const body = 'X' + key.slice(1, 8)
    expect(verifyKey(body + checksumOf(body)).ok).toBe(false)
  })

  it('12자리를 4자씩 끊어 표기한다', () => {
    expect(formatKey('PABCDEFG1234')).toBe('PABC-DEFG-1234')
  })

  it('salt 가 다르면 체크섬이 달라진다 (구제품 키와 비호환)', () => {
    expect(LICENSE_SALT).toContain('ACADEMY-NOTE')
    expect(checksumOf('PABCDEFG')).toHaveLength(4)
    expect(checksumOf('PABCDEFG')).not.toBe(checksumOf('LABCDEFG'))
  })

  it('키 해시는 결정적이고 원문을 노출하지 않는다', () => {
    const key = generateKey('pro')
    expect(hashKey(key)).toBe(hashKey(key.toLowerCase()))
    expect(hashKey(key)).not.toContain(normalizeKey(key))
  })
})
