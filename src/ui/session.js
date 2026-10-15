// 로그인 세션 — PIN 4자리. Lite 는 단일 기기라 원장 계정 자동 로그인이 기본,
// Pro 는 기기마다 누가 쓰는지가 중요하므로 항상 PIN 을 묻는다.

import { cache, getSetting } from '../data/repo.js'

const KEY = 'academy-note:session'

export function currentUser() {
  try {
    const raw = sessionStorage.getItem(KEY) || localStorage.getItem(KEY)
    if (!raw) return null
    const { userId } = JSON.parse(raw)
    return cache.userById.get(userId) || null
  } catch {
    return null
  }
}

export function login(user, { remember = false } = {}) {
  const payload = JSON.stringify({ userId: user.id, at: Date.now() })
  sessionStorage.setItem(KEY, payload)
  if (remember) localStorage.setItem(KEY, payload)
  else localStorage.removeItem(KEY)
  return user
}

export function logout() {
  sessionStorage.removeItem(KEY)
  localStorage.removeItem(KEY)
}

export function findByPin(pin) {
  return cache.users.find((u) => String(u.pin || '') === String(pin))
}

/** Lite + 사용자 1명(원장)뿐이면 로그인 화면을 건너뛴다 */
export function autoLoginIfSolo() {
  const plan = getSetting('license')?.plan || 'lite'
  if (plan === 'pro') return null
  const owners = cache.users.filter((u) => u.role === 'owner')
  if (cache.users.length === 1 && owners.length === 1) return login(owners[0], { remember: true })
  return null
}
