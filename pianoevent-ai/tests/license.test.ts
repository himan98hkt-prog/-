import { beforeEach, describe, expect, it } from 'vitest'
import { PLAN_LABEL, checkKey, formatKey, makeKey, normalizeKey, type LicensePlan } from '@/lib/license/key'

/**
 * 인증키는 **돈을 받고 나서** 원장님이 손으로 치시는 것이다.
 * 여기서 걸러야 하는 실패는 둘이다 —
 *   ① 제대로 산 분의 키가 안 열리는 것 (환불 문의로 바로 이어진다)
 *   ② 만들어 낸 가짜 키가 열리는 것 (파는 물건이 아니게 된다)
 */
const NOW = new Date('2026-09-01T00:00:00Z')

beforeEach(() => {
  process.env.RECITAL_LICENSE_SECRET = 'test-secret'
})

describe('인증키', () => {
  it('만든 키가 그대로 열린다', () => {
    for (const plan of ['life', 'year', 'trial'] as LicensePlan[]) {
      const key = makeKey({ plan, expiresAt: plan === 'life' ? null : new Date('2027-01-01T00:00:00Z'), serial: 7 })
      const got = checkKey(key, NOW)
      expect(got.ok, `${plan} ${key}`).toBe(true)
      expect(got.plan).toBe(plan)
      expect(got.serial).toBe(7)
      expect(PLAN_LABEL[plan]).toBeTruthy()
    }
  })

  it('스무 글자에 RM- 이 붙는다 — 손으로 치실 수 있는 길이다', () => {
    const key = makeKey({ plan: 'year', expiresAt: new Date('2027-01-01T00:00:00Z'), serial: 1 })
    expect(key.startsWith('RM-')).toBe(true)
    expect(normalizeKey(key)).toHaveLength(20)
    expect(key.split('-')).toHaveLength(5)
  })

  it('소문자·하이픈 빠짐·헷갈리는 글자를 알아서 받는다', () => {
    const key = makeKey({ plan: 'life', expiresAt: null, serial: 42 })
    const body = normalizeKey(key)
    expect(checkKey(key.toLowerCase(), NOW).ok).toBe(true)
    expect(checkKey(body, NOW).ok).toBe(true)
    expect(checkKey(`  ${key}  `, NOW).ok).toBe(true)
    // O 를 0 으로, I·L 을 1 로, U 를 V 로 — 눈으로 헷갈리는 것만 바로잡는다
    expect(checkKey(body.replace(/0/g, 'O').replace(/1/g, 'l'), NOW).ok).toBe(true)
  })

  it('한 글자만 바꿔도 걸러진다', () => {
    const key = makeKey({ plan: 'year', expiresAt: new Date('2027-01-01T00:00:00Z'), serial: 3 })
    const body = normalizeKey(key)
    let changed = 0
    for (let i = 0; i < body.length; i += 1) {
      const other = body[i] === '2' ? '3' : '2'
      const broken = `${body.slice(0, i)}${other}${body.slice(i + 1)}`
      if (broken === body) continue
      changed += 1
      expect(checkKey(broken, NOW).ok, broken).toBe(false)
    }
    expect(changed).toBeGreaterThan(15)
  })

  it('비밀이 다르면 열리지 않는다 — 저장소를 봐도 키를 찍어 낼 수 없다', () => {
    const key = makeKey({ plan: 'life', expiresAt: null, serial: 1 })
    process.env.RECITAL_LICENSE_SECRET = 'another-secret'
    expect(checkKey(key, NOW).ok).toBe(false)
  })

  it('기간이 지난 키는 언제 끝났는지 말해 준다', () => {
    const key = makeKey({ plan: 'year', expiresAt: new Date('2026-06-01T00:00:00Z'), serial: 9 })
    const got = checkKey(key, NOW)
    expect(got.ok).toBe(false)
    expect(got.reason).toContain('2026년 6월 1일')
  })

  it('평생 키는 만료가 없다', () => {
    const key = makeKey({ plan: 'life', expiresAt: null, serial: 5 })
    const got = checkKey(key, new Date('2099-01-01T00:00:00Z'))
    expect(got.ok).toBe(true)
    expect(got.expiresAt).toBeNull()
  })

  it('아무 글자나 넣으면 무엇이 잘못됐는지 알려 준다', () => {
    expect(checkKey('RM-1234', NOW).reason).toContain('스무 글자')
    expect(checkKey('RM-11111-11111-11111-11111', NOW).reason).toContain('발급한 것이 아닙니다')
  })

  it('보기 좋게 다섯 자씩 끊는다', () => {
    expect(formatKey('ABCDEFGHJKMNPQRSTVWX')).toBe('RM-ABCDE-FGHJK-MNPQR-STVWX')
  })
})
