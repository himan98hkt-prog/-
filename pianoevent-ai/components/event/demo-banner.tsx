'use client'

import { Loader2, Sparkles, Trash2 } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { Button, buttonVariants } from '@/components/ui/button'

/**
 * 구경용 행사 위에 붙는 띠.
 *
 * 구경은 끝이 있어야 한다. 다 보시고 나면 두 가지 중 하나를 하시게 되는데,
 * 그 둘이 화면 어디에도 없었다 —
 *
 *   1. **이제 진짜 행사를 만든다** (여기까지 오신 분이 하실 일)
 *   2. **구경용을 지운다** (목록이 깨끗해야 다음에 안 헷갈리신다)
 *
 * 지울 때 확인 문구를 치게 하지 않는다. 지어낸 자료뿐이라 잃을 것이 없고,
 * 겁을 주면 안 지우신 채로 계속 두신다.
 */
export function DemoBanner({ eventId }: { eventId: string }) {
  const router = useRouter()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function remove() {
    setBusy(true)
    setError(null)
    try {
      const res = await fetch(`/api/events/${eventId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error((await res.json()).error ?? '지우지 못했습니다.')
      router.push('/events')
      router.refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : '지우지 못했습니다.')
      setBusy(false)
    }
  }

  return (
    <section
      className="mb-5 grid gap-2 rounded-lg border border-accent/40 bg-accent/5 p-3"
      data-testid="demo-banner"
    >
      <p className="text-sm font-medium">
        <Sparkles className="mr-1 inline h-4 w-4 text-accent" aria-hidden />
        구경용 행사입니다
      </p>
      <p className="text-sm text-muted-foreground">
        여기 있는 아이 이름 · 연주곡 · 사진은 <strong>지어낸 것</strong>입니다. 마음껏 눌러 보시고
        인쇄물도 뽑아 보세요. 무엇을 하셔도 학원 자료에는 아무 일도 생기지 않습니다.
      </p>
      <div className="flex flex-wrap gap-2">
        {/* 다 보신 분이 다음에 하실 일 — 여기서 바로 짚어 드린다 */}
        <Link href="/events/new" className={buttonVariants({ size: 'sm' })} data-testid="demo-to-real">
          이제 진짜 행사 만들기
        </Link>
        <Button variant="outline" size="sm" onClick={remove} disabled={busy} data-testid="demo-delete">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Trash2 className="h-4 w-4" aria-hidden />}
          {busy ? '지우는 중…' : '구경 끝났습니다 — 이 행사 지우기'}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        지우셔도 이 단추는 행사 목록에 그대로 있습니다. 언제든 다시 만들어 보실 수 있습니다.
      </p>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </section>
  )
}
