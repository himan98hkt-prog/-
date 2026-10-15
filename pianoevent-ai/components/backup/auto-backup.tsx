'use client'

import { useEffect } from 'react'
import { BACKUP_MARK, needsBackup } from '@/lib/events/backup'

/**
 * 하루에 한 번, 조용히 떠 둔다.
 *
 * 원장님께 묻지 않는다. "백업하시겠습니까" 는 컴맹 원장님께 해서는 안 되는 질문이다 —
 * 무엇을 묻는지 모르시고, 모르면 [아니오] 를 누르신다.
 *
 * 화면에 아무것도 띄우지 않는다. 잘 되든 안 되든 원장님이 하실 일이 없기 때문이다.
 * 떠 둔 것은 **설정 화면**에서 보실 수 있고, 거기서 되살리실 수 있다.
 */
export function AutoBackup() {
  useEffect(() => {
    let last: string | null = null
    try {
      last = window.localStorage.getItem(BACKUP_MARK)
    } catch {
      // 저장을 못 읽는 브라우저 — 그러면 열 때마다 한 번씩 뜬다. 그래도 없는 것보다 낫다.
    }
    if (!needsBackup(last)) return

    // 화면이 다 그려진 뒤에 조용히. 원장님이 기다리실 일이 아니다.
    const timer = window.setTimeout(() => {
      fetch('/api/backup', { method: 'POST' })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (!data) return
          try {
            window.localStorage.setItem(BACKUP_MARK, new Date().toISOString())
          } catch {
            /* 못 적어도 오늘 몫은 이미 떴다 */
          }
        })
        .catch(() => {
          /* 못 떠도 원장님이 하실 일은 없다. 내일 다시 뜬다 */
        })
    }, 2500)

    return () => window.clearTimeout(timer)
  }, [])

  return null
}
