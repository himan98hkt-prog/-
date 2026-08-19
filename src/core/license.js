// 자체검증 라이선스 키 (오프라인 검증).
//
// 형식: 12자 = [플랜 1자][랜덤 7자][체크섬 4자]  → 표기는 4자씩 끊어 'XXXX-XXXX-XXXX'
//   - 플랜 문자: L = Lite, P = Pro
//   - 체크섬: SALT + 본문 8자를 해시한 값의 하위 20비트를 base32(4자)로 인코딩
//
// 주의: SALT는 이 제품 전용 신규 값이다. 구제품(피아노학원 관리노트) 키는 이 salt로 검증되지 않으며
//       그 반대도 성립한다 — 의도된 동작이다. SALT를 바꾸면 이미 판매된 키가 전부 무효가 되므로
//       출시 후에는 절대 수정하지 말 것.
export const LICENSE_SALT = 'ACADEMY-NOTE::2026::a7f3-kQ9v-Zt2m::v1'

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

export function checksumOf(body) {
  const h = hash32(`${LICENSE_SALT}|${body}`)
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

export function generateKey(plan = 'lite') {
  const planChar = plan === 'pro' ? 'P' : 'L'
  const buf = new Uint8Array(7)
  globalThis.crypto.getRandomValues(buf)
  let body = planChar
  for (const b of buf) body += B32[b % 32]
  return formatKey(body + checksumOf(body))
}

export function verifyKey(input) {
  const key = normalizeKey(input)
  if (key.length !== 12) return { ok: false, reason: '키는 12자리입니다 (예: PXXX-XXXX-XXXX)' }
  const body = key.slice(0, 8)
  const sum = key.slice(8)
  const planChar = body[0]
  if (!PLANS[planChar]) return { ok: false, reason: '플랜 문자가 올바르지 않습니다 (L 또는 P로 시작)' }
  for (const ch of body.slice(1) + sum) {
    if (!B32.includes(ch)) return { ok: false, reason: `사용할 수 없는 문자가 있습니다: ${ch}` }
  }
  if (checksumOf(body) !== sum) return { ok: false, reason: '검증번호가 맞지 않습니다. 키를 다시 확인해 주세요' }
  return { ok: true, plan: PLANS[planChar], key: formatKey(key) }
}

// 저장은 원문 대신 해시로 (백업 파일에 키 원문이 남지 않도록)
export function hashKey(input) {
  const k = normalizeKey(input)
  return `h1:${hash32(`${LICENSE_SALT}#${k}`).toString(16).padStart(8, '0')}${hash32(`${k}#${LICENSE_SALT}`).toString(16).padStart(8, '0')}`
}
