import { describe, it, expect } from 'vitest'
import {
  generateKey, verifyKey, normalizeKey, formatKey, checksumOf, hashKey,
  LICENSE_SALT, PRODUCT_CODE, trialStatus, deviceFingerprint
} from '../src/core/license.js'

describe('인증키(시디키)', () => {
  it('발급한 키는 항상 검증을 통과한다', () => {
    for (let i = 0; i < 300; i++) {
      const plan = i % 2 ? 'pro' : 'lite'
      const key = generateKey(plan)
      const res = verifyKey(key)
      expect(res.ok, `${key} 검증 실패`).toBe(true)
      expect(res.plan).toBe(plan)
    }
  })

  it('제품 문자와 플랜 문자를 앞 두 자리에 담는다', () => {
    expect(normalizeKey(generateKey('lite', 'A')).slice(0, 2)).toBe('AL')
    expect(normalizeKey(generateKey('pro', 'A')).slice(0, 2)).toBe('AP')
    expect(normalizeKey(generateKey('pro', 'M')).slice(0, 2)).toBe('MP')
  })

  it('통합키(A)는 두 제품 모두에서 열린다', () => {
    const key = generateKey('pro', 'A')
    expect(verifyKey(key, { productCode: 'M' }).ok).toBe(true)
    expect(verifyKey(key, { productCode: 'K' }).ok).toBe(true)
  })

  it('다른 제품 전용 키는 거부하고 이유를 알려 준다', () => {
    const pianoOnly = generateKey('lite', 'K')
    const res = verifyKey(pianoOnly, { productCode: 'M' })
    expect(res.ok).toBe(false)
    expect(res.reason).toContain('피아노 관리노트')
    expect(verifyKey(pianoOnly, { productCode: 'K' }).ok).toBe(true)
  })

  it('이 빌드는 학원 관리노트(M) 로 설정되어 있다', () => {
    expect(PRODUCT_CODE).toBe('M')
    expect(verifyKey(generateKey('lite', 'M')).ok).toBe(true)
  })

  it('제품 문자가 없던 초기 발급분(v1)도 계속 인정한다', () => {
    for (const planChar of ['L', 'P']) {
      const body = planChar + 'ABC1234'
      const res = verifyKey(body + checksumOf(body))
      expect(res.ok).toBe(true)
      expect(res.version).toBe(1)
      expect(res.plan).toBe(planChar === 'P' ? 'pro' : 'lite')
    }
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
    const body = 'AX' + normalizeKey(generateKey('pro')).slice(2, 8)
    expect(verifyKey(body + checksumOf(body)).ok).toBe(false)
  })

  it('12자리를 4자씩 끊어 표기한다', () => {
    expect(formatKey('APBCDEFG1234')).toBe('APBC-DEFG-1234')
  })

  it('salt 는 제품 고정값이고 체크섬은 본문마다 달라진다', () => {
    expect(LICENSE_SALT).toContain('ACADEMY-NOTE')
    expect(checksumOf('APBCDEFG')).toHaveLength(4)
    expect(checksumOf('APBCDEFG')).not.toBe(checksumOf('ALBCDEFG'))
  })

  it('키 해시는 결정적이고 원문을 노출하지 않는다', () => {
    const key = generateKey('pro')
    expect(hashKey(key)).toBe(hashKey(key.toLowerCase()))
    expect(hashKey(key)).not.toContain(normalizeKey(key))
  })

  it('기기번호는 같은 설치에서 항상 같고 설치마다 다르다', () => {
    expect(deviceFingerprint('inst-1')).toBe(deviceFingerprint('inst-1'))
    expect(deviceFingerprint('inst-1')).not.toBe(deviceFingerprint('inst-2'))
    expect(deviceFingerprint('inst-1')).toHaveLength(6)
  })
})

describe('체험 기간', () => {
  const start = '2026-03-01T00:00:00.000Z'

  it('시작 전에는 체험이 아니다', () => {
    expect(trialStatus({}).started).toBe(false)
    expect(trialStatus({}).active).toBe(false)
  })

  it('시작 직후에는 전체 기간이 남는다', () => {
    const t = trialStatus({ startedAt: start, today: '2026-03-01T09:00:00.000Z' })
    expect(t.active).toBe(true)
    expect(t.daysLeft).toBe(14)
  })

  it('하루씩 줄고 기간이 지나면 만료된다', () => {
    expect(trialStatus({ startedAt: start, today: '2026-03-10T00:00:00.000Z' }).daysLeft).toBe(5)
    const done = trialStatus({ startedAt: start, today: '2026-03-16T00:00:00.000Z' })
    expect(done.active).toBe(false)
    expect(done.expired).toBe(true)
    expect(done.daysLeft).toBe(0)
  })
})
