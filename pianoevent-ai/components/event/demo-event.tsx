'use client'

import { Loader2, Sparkles } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { Button } from '@/components/ui/button'

/**
 * "구경용 행사 만들기".
 *
 * 처음 켜시면 목록이 비어 있어, 무엇을 눌러도 볼 것이 없다. 그래서 이 프로그램이
 * 무엇을 해 주는지 끝까지 못 보신 채 닫으신다.
 *
 * 한 번 누르면 아이 · 곡 · 사진 · 순서가 다 채워진 행사가 하나 생긴다.
 * 인쇄물부터 감동영상까지 그 자리에서 다 보시고, 마음에 드시면 진짜 행사를 만드시면 된다.
 * 지우는 것도 쉽다고 이름에 적어 두었다.
 */
export function DemoEventButton({ empty = false }: { empty?: boolean }) {
  const router = useRouter()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function make() {
    setBusy(true)
    setError(null)
    try {
      const res = await fetch('/api/events/demo', { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '만들지 못했습니다.')
      router.push(`/events/${data.event.id}`)
      router.refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : '만들지 못했습니다.')
      setBusy(false)
    }
  }

  return (
    <div className={empty ? 'grid justify-items-center gap-2' : 'grid gap-2'} data-testid="demo-event">
      <Button variant={empty ? 'default' : 'outline'} size="sm" onClick={make} disabled={busy}>
        {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Sparkles className="h-4 w-4" aria-hidden />}
        {busy ? '만들고 있습니다…' : '구경용 행사 만들기'}
      </Button>
      <p className="text-xs text-muted-foreground">
        아이 10명 · 곡 · 사진 · 순서까지 채워진 행사가 하나 생깁니다. 인쇄물과 감동영상까지 눌러 보시고{' '}
        <strong>그냥 지우시면 됩니다.</strong>
      </p>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  )
}
