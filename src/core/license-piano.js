// 피아노학원 관리노트에서 이미 쓰고 있는 인증키 규칙 (판매자 발급기와 동일).
//
// 이 파일은 "우리가 새로 정한 규칙" 이 아니라 **기존 제품의 규칙을 그대로 옮겨 온 것**이다.
// 목적은 하나 — 피아노 관리노트에서 발급해 이미 팔린 키가 학원 관리노트에서도 그대로 열리게 하는 것.
// 따라서 값(salt·문자표·해시식)은 원본과 한 글자도 달라서는 안 된다. 바꾸면 기존 고객 키가 죽는다.
//
// 두 가지 발급 방식이 있다.
//   1) 학원명 방식  : 키 = f(학원명). 같은 학원명이면 언제나 같은 키 → 재발급이 쉽다.
//                    검증하려면 학원명이 필요하다.
//   2) 자기검증 방식: 앞 8자는 무작위, 뒤 4자는 앞 8자에서 계산한 검증코드.
//                    학원명 없이 오프라인에서 진위 판정이 된다. (미리 만들어 두고 결제 순서대로 배정)

export const PIANO_SALT = 'PAL-x7Qm3vK9nR-accelssam-2026'

// 원본 문자표. 우리 쪽 Crockford base32 와 달리 L·U 를 쓰고 0·1·2·5·8 은 쓰지 않는다.
export const PIANO_CHARS = 'ACDEFGHJKLMNPQRTUVWXY34679'

/** 학원명 표기 흔들림(공백·괄호·가운뎃점·마침표·쉼표·하이픈, 대소문자)을 흡수한다 */
export function pianoNormalizeName(s) {
  return String(s || '')
    .replace(/\s+/g, '')
    .replace(/[()（）·.,\-]/g, '')
    .toLowerCase()
}

/** 원본의 2중 해시 — FNV-1a 변형 + 가산/시프트 혼합 */
function pianoHash(str) {
  let h1 = 0x811c9dc5
  let h2 = 0x1000193
  for (let i = 0; i < str.length; i++) {
    const c = str.charCodeAt(i)
    h1 = ((h1 ^ c) * 16777619) >>> 0
    h2 = ((h2 + c * 31) ^ (h2 << 5)) >>> 0
  }
  return [h1, h2]
}

function encode(h1, h2, length) {
  let n = BigInt(h1) * 4294967296n + BigInt(h2)
  const L = BigInt(PIANO_CHARS.length)
  let out = ''
  for (let i = 0; i < length; i++) {
    out += PIANO_CHARS[Number(n % L)]
    n /= L
  }
  return out
}

export function formatPianoKey(raw) {
  const k = String(raw || '').toUpperCase().replace(/[^A-Z0-9]/g, '')
  return `${k.slice(0, 4)}-${k.slice(4, 8)}-${k.slice(8, 12)}`
}

/** 학원명 방식 키 */
export function pianoKeyForName(name) {
  const [h1, h2] = pianoHash(`${PIANO_SALT}|${pianoNormalizeName(name)}|${PIANO_SALT}`)
  return formatPianoKey(encode(h1, h2, 12))
}

/** 자기검증 방식의 뒤 4자 */
export function pianoCheckDigits(head) {
  const [h1, h2] = pianoHash(`${PIANO_SALT}#SV#${String(head).toUpperCase()}`)
  return encode(h1, h2, 4)
}

export function normalizePianoKey(key) {
  return String(key || '').toUpperCase().replace(/[^A-Z0-9]/g, '')
}

/** 자기검증 방식 키인가 (학원명 없이 판정 가능) */
export function isPianoSelfValid(key) {
  const k = normalizePianoKey(key)
  if (k.length !== 12) return false
  return pianoCheckDigits(k.slice(0, 8)) === k.slice(8, 12)
}

/** 학원명 방식 키인가 */
export function matchesPianoName(key, name) {
  if (!name) return false
  return pianoKeyForName(name) === formatPianoKey(key)
}

/** 무작위 자기검증 키 발급 (판매자 도구용) */
export function generatePianoKey() {
  const buf = new Uint8Array(8)
  globalThis.crypto.getRandomValues(buf)
  let head = ''
  for (const b of buf) head += PIANO_CHARS[b % PIANO_CHARS.length]
  return formatPianoKey(head + pianoCheckDigits(head))
}

/**
 * 피아노 관리노트 키 판정.
 * @param {string} key
 * @param {{academyName?:string}} opts  학원명 방식 키를 확인할 때만 필요
 * @returns {{ok:true, mode:'self'|'name', key:string, name?:string}|{ok:false}}
 */
export function verifyPianoKey(key, { academyName } = {}) {
  const k = normalizePianoKey(key)
  if (k.length !== 12) return { ok: false }
  if (isPianoSelfValid(k)) return { ok: true, mode: 'self', key: formatPianoKey(k) }
  if (matchesPianoName(k, academyName)) return { ok: true, mode: 'name', key: formatPianoKey(k), name: academyName }
  return { ok: false }
}
