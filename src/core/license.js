// 자체검증 인증키(시디키) — 서버 없이 오프라인에서 검증된다.
//
// 형식(v2): 12자 = [제품 1자][플랜 1자][랜덤 6자][체크섬 4자] → 표기는 'XXXX-XXXX-XXXX'
//   제품 문자   A = 통합(피아노 관리노트 + 학원 관리노트 공용)
//              M = 학원 관리노트 전용
//              K = 피아노 관리노트 전용
//   플랜 문자   L = Lite(단일 기기·오프라인)   P = Pro(다기기·실시간 동기화)
//   체크섬     SALT + 본문 8자를 해시한 값의 하위 20비트를 base32 4자로 인코딩
//
// 형식(v1): 12자 = [플랜 1자][랜덤 7자][체크섬 4자]. 초기 발급분 호환을 위해 계속 인정한다.
//
// 두 제품에서 같은 키를 쓰려면: 이 파일을 두 제품에 그대로 넣고 PRODUCT_CODE 만 바꾼다
// (학원 관리노트 = 'M', 피아노 관리노트 = 'K'). 제품 문자가 'A' 인 키는 양쪽 모두에서 열린다.
//
// 주의: SALT 를 바꾸면 이미 발급한 키가 전부 무효가 된다. 출시 후에는 절대 수정하지 말 것.
export const LICENSE_SALT = 'ACADEMY-NOTE::2026::a7f3-kQ9v-Zt2m::v1'

// 피아노학원 관리노트가 이미 팔아 온 키는 그 제품의 규칙 그대로 인정한다.
// (그쪽 앱을 고치지 않아도 두 제품이 같은 키를 쓰게 만드는 길이다 — license-piano.js 참고)
import { verifyPianoKey, PIANO_CHARS } from './license-piano.js'

/** 이 빌드가 어떤 제품인지. 피아노 관리노트에 이식할 때만 'K' 로 바꾼다. */
export const PRODUCT_CODE = 'M'

export const PRODUCTS = {
  A: { code: 'A', label: '통합(피아노+학원)', accepts: ['M', 'K'] },
  M: { code: 'M', label: '학원 관리노트', accepts: ['M'] },
  K: { code: 'K', label: '피아노 관리노트', accepts: ['K'] }
}

/**
 * 다른 salt 로 이미 발급된 키를 계속 인정하기 위한 자리.
 *
 * 피아노 관리노트가 자체 salt 로 키를 팔아 왔다면, 그 salt 를 여기 등록하는 것만으로
 * **이미 판매된 키를 회수하지 않고** 두 제품에서 함께 쓸 수 있다.
 * 새로 발급하는 키는 항상 위의 LICENSE_SALT + 통합키(A) 를 쓴다.
 *
 *   { salt: '피아노 앱의 salt 문자열', product: 'K', label: '피아노 관리노트 기존 발급분',
 *     planOf: (body) => 'lite' | 'pro' }   // planOf 를 주지 않으면 앞 두 자리 규칙을 그대로 적용
 */
export const LEGACY_KEY_SOURCES = []

export const TRIAL_DAYS = 14

// Crockford base32 — 사람이 받아 적을 때 헷갈리는 I, L, O, U 제외
const B32 = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
const PLANS = { L: 'lite', P: 'pro' }

function hash32(str) {
  // FNV-1a 32bit + 최종 확산(avalanche). 암호학적 강도가 아니라 오타 검출이 목적이다.
  let h = 0x811c9dc5
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  h ^= h >>> 15
  h = Math.imul(h, 0x2545f491) >>> 0
  h ^= h >>> 13
  return h >>> 0
}

export function checksumOf(body, salt = LICENSE_SALT) {
  const h = hash32(`${salt}|${body}`)
  let out = ''
  for (let i = 0; i < 4; i++) out = B32[(h >>> (i * 5)) & 31] + out
  return out
}

export function normalizeKey(input) {
  return String(input || '').toUpperCase().replace(/[^0-9A-Z]/g, '')
}

export function formatKey(raw) {
  const k = normalizeKey(raw)
  return k.replace(/(.{4})(?=.)/g, '$1-')
}

function randomChars(n) {
  const buf = new Uint8Array(n)
  globalThis.crypto.getRandomValues(buf)
  let out = ''
  for (const b of buf) out += B32[b % 32]
  return out
}

/**
 * 키 발급.
 * @param {'lite'|'pro'} plan
 * @param {'A'|'M'|'K'} product  기본은 통합('A') — 두 제품에서 모두 열린다
 */
export function generateKey(plan = 'lite', product = 'A') {
  const planChar = plan === 'pro' ? 'P' : 'L'
  const prod = PRODUCTS[product] ? product : 'A'
  const body = prod + planChar + randomChars(6)
  return formatKey(body + checksumOf(body))
}

/**
 * 키 검증. 이 빌드(PRODUCT_CODE)에서 쓸 수 있는 키인지까지 본다.
 * @returns {{ok:true, plan, product, key, version}|{ok:false, reason}}
 */
export function verifyKey(input, {
  productCode = PRODUCT_CODE,
  legacySources = LEGACY_KEY_SOURCES,
  academyName = null,
  pianoPlan = 'lite'
} = {}) {
  const key = normalizeKey(input)
  if (!key) return { ok: false, reason: '인증키를 입력해 주세요' }
  if (key.length !== 12) return { ok: false, reason: `인증키는 12자리입니다 (현재 ${key.length}자)` }

  const body = key.slice(0, 8)
  const sum = key.slice(8)

  // 1) 우리 형식
  if (checksumOf(body) === sum) return classify(key, body, productCode)

  // 2) 피아노 관리노트에서 발급된 키 — 자기검증 방식은 학원명 없이, 학원명 방식은 학원명과 함께
  const piano = verifyPianoKey(key, { academyName })
  if (piano.ok) {
    return {
      ok: true,
      plan: pianoPlan === 'pro' ? 'pro' : 'lite',
      product: 'K',
      key: piano.key,
      version: 0,
      scheme: 'piano',
      source: piano.mode === 'name' ? `피아노 관리노트 · 학원명 방식(${piano.name})` : '피아노 관리노트 발급분',
      academyName: piano.name || null
    }
  }

  // 다른 salt 로 발급된 기존 키(예: 피아노 관리노트가 먼저 팔아 온 키)
  for (const src of legacySources) {
    if (!src?.salt || checksumOf(body, src.salt) !== sum) continue
    const plan = src.planOf ? src.planOf(body) : (PLANS[body[1]] || PLANS[body[0]] || 'lite')
    const product = PRODUCTS[src.product] || PRODUCTS.A
    if (!product.accepts.includes(productCode)) {
      return { ok: false, reason: `${product.label} 전용 키입니다. 이 제품에서는 사용할 수 없습니다` }
    }
    return { ok: true, plan, product: product.code, key: formatKey(key), version: 0, source: src.label || 'legacy' }
  }

  // 어느 규칙에도 맞지 않았다 — 오타인지 형식 자체가 다른지 구분해 알려 준다
  const allowed = new Set([...B32, ...PIANO_CHARS])
  for (const ch of key) {
    if (!allowed.has(ch)) return { ok: false, reason: `쓸 수 없는 문자가 있습니다: ${ch}` }
  }
  return {
    ok: false,
    reason: academyName
      ? '검증번호가 맞지 않습니다. 키와 학원명을 다시 확인해 주세요'
      : '검증번호가 맞지 않습니다. 피아노 관리노트에서 학원명으로 받은 키라면 학원명도 함께 넣어 주세요'
  }
}

/** 체크섬이 맞은 키의 제품·플랜을 읽는다 */
function classify(key, body, productCode) {
  const head = body[0]
  // v1: 첫 글자가 플랜 문자(L/P) — 제품 구분이 없던 초기 발급분
  if (PLANS[head] && !PRODUCTS[head]) {
    return { ok: true, plan: PLANS[head], product: 'A', key: formatKey(key), version: 1, source: 'primary' }
  }
  const product = PRODUCTS[head]
  if (!product) return { ok: false, reason: '제품 문자가 올바르지 않습니다 (A·M·K 또는 L·P 로 시작)' }
  const plan = PLANS[body[1]]
  if (!plan) return { ok: false, reason: '플랜 문자가 올바르지 않습니다 (두 번째 자리는 L 또는 P)' }
  if (!product.accepts.includes(productCode)) {
    return { ok: false, reason: `${product.label} 전용 키입니다. 이 제품에서는 사용할 수 없습니다` }
  }
  return { ok: true, plan, product: head, key: formatKey(key), version: 2, source: 'primary' }
}

// 저장은 원문 대신 해시로 (백업 파일에 키 원문이 남지 않도록)
export function hashKey(input) {
  const k = normalizeKey(input)
  return `h1:${hash32(`${LICENSE_SALT}#${k}`).toString(16).padStart(8, '0')}${hash32(`${k}#${LICENSE_SALT}`).toString(16).padStart(8, '0')}`
}

/** 설치 기기 지문 — 지원 문의 시 "몇 번 기기" 를 확인하는 용도 (개인정보 없음) */
export function deviceFingerprint(seed = '') {
  const env = [
    seed,
    globalThis.navigator?.userAgent || '',
    globalThis.screen ? `${screen.width}x${screen.height}` : '',
    Intl.DateTimeFormat().resolvedOptions().timeZone || ''
  ].join('|')
  return hash32(env).toString(32).toUpperCase().padStart(7, '0').slice(-6)
}

const DAY = 86400000

/**
 * 체험 상태 계산 (순수 함수).
 * @param {{startedAt?:string, today?:string|Date, days?:number}} opts
 */
export function trialStatus({ startedAt, today = new Date(), days = TRIAL_DAYS } = {}) {
  if (!startedAt) return { active: false, started: false, daysLeft: days, expired: false }
  const start = new Date(startedAt).getTime()
  const now = today instanceof Date ? today.getTime() : new Date(today).getTime()
  const used = Math.floor((now - start) / DAY)
  const daysLeft = Math.max(0, days - used)
  return { active: daysLeft > 0, started: true, daysLeft, expired: daysLeft <= 0 }
}
