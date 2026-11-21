// 어디서나 쓰는 짧은 정렬가능 ID. 시간 접두사 덕분에 IndexedDB 인덱스 스캔이 시간순이 된다.
const ALPHA = '0123456789abcdefghijklmnopqrstuvwxyz'

function rand(n) {
  const buf = new Uint8Array(n)
  globalThis.crypto.getRandomValues(buf)
  let out = ''
  for (const b of buf) out += ALPHA[b % ALPHA.length]
  return out
}

export function uid(prefix = '') {
  const t = Date.now().toString(36).padStart(8, '0')
  return `${prefix}${t}${rand(6)}`
}

export function shortCode(len = 6) {
  // 초대 코드처럼 사람이 받아 적는 값 — 혼동 문자(0/O/1/I) 제외
  const A = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
  const buf = new Uint8Array(len)
  globalThis.crypto.getRandomValues(buf)
  let out = ''
  for (const b of buf) out += A[b % A.length]
  return out
}
