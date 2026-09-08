'use client'

import { useEffect } from 'react'
import type { StepKey } from '@/lib/flow/steps'
import { addSeen, parseSeen, seenStorageKey } from '@/lib/events/seen'

/**
 * 이 화면을 열어 보셨다고 적어 두는 자리.
 *
 * 그리는 것이 없다. 화면 맨 위 띠(`ScreenHeader`)에 함께 붙여 두어,
 * 어느 화면을 여시든 한 곳에서 적힌다 — 화면마다 손대지 않아도 된다.
 *
 * 이 컴퓨터 안에만 담긴다. 서버로 올리지 않는다.
 */
export function MarkSeen({ eventId, step }: { eventId: string; step: StepKey }) {
  useEffect(() => {
    try {
      const key = seenStorageKey(eventId)
      const next = addSeen(parseSeen(window.localStorage.getItem(key)), step)
      window.localStorage.setItem(key, JSON.stringify(next))
    } catch {
      /* 저장이 막힌 브라우저면 그냥 지나간다 — 구경에 지장이 없다 */
    }
  }, [eventId, step])

  return null
}
