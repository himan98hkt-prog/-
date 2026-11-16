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

export const DEFAULT_PIN = '0000'

/**
 * 혼자 쓰는 원장님에게는 잠금 화면을 띄우지 않는다.
 *
 * 잠금이 뜨는 조건은 "지킬 것이 있을 때" 뿐이다:
 *   · 계정이 둘 이상이다(강사·데스크가 있다) → 누가 쓰는지 알아야 한다
 *   · 원장이 잠금 번호를 직접 정했다(기본값 0000 이 아니다) → 잠그고 싶다는 뜻이다
 * 기본값 0000 을 매번 누르게 하는 것은 보안이 아니라 번거로움일 뿐이라 건너뛴다.
 * (Pro 도 같다. 예전에는 Pro 면 무조건 물었는데, 공용키가 Pro 로 열리면서 1인 학원까지 매번 묻게 됐다)
 */
export function autoLoginIfSolo() {
  if (cache.users.length !== 1) return null
  const [only] = cache.users
  if (only.role !== 'owner') return null
  const plan = getSetting('license')?.plan || 'lite'
  const pinSet = String(only.pin || DEFAULT_PIN) !== DEFAULT_PIN
  if (pinSet && plan === 'pro') return null
  return login(only, { remember: true })
}
