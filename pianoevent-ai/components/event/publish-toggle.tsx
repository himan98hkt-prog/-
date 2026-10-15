'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { EVENT_STATUS_LABEL, type EventStatus } from '@/lib/types'

/** 초대장 배포 상태 전환. 종료 처리하면 학부모 회신이 더 들어오지 않는다. */
export function PublishToggle({ eventId, status }: { eventId: string; status: EventStatus }) {
  const router = useRouter()
  const [pending, setPending] = useState(false)

  async function setStatus(next: EventStatus) {
    setPending(true)
    try {
      await fetch(`/api/events/${eventId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: next }),
      })
      router.refresh()
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4 text-sm">
      <span className="text-muted-foreground">현재 상태: {EVENT_STATUS_LABEL[status]}</span>
      {status !== 'published' && status !== 'done' && (
        <Button size="sm" variant="outline" disabled={pending} onClick={() => setStatus('published')}>
          배포 상태로 표시
        </Button>
      )}
      {status !== 'done' && (
        <Button size="sm" variant="ghost" disabled={pending} onClick={() => setStatus('done')}>
          행사 종료 처리
        </Button>
      )}
      {status === 'done' && (
        <Button size="sm" variant="ghost" disabled={pending} onClick={() => setStatus('published')}>
          다시 회신 받기
        </Button>
      )}
    </div>
  )
}
