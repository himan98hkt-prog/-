'use client'

import { Check, Loader2, Sparkles, Trash2 } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { Button, buttonVariants } from '@/components/ui/button'
import { SEEN_STEPS, parseSeen, seenStorageKey, unseenSteps } from '@/lib/events/seen'
import { getStep, stepHref, type StepKey } from '@/lib/flow/steps'
import { cn } from '@/lib/utils'

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
  /**
   * 어디까지 보셨는지.
   *
   * 대개 인쇄물 한 번 보시고 닫으신다. 무대 화면과 감동영상이 이 프로그램에서 가장 큰
   * 것인데 거기까지 못 가시는 것이다. 남은 것이 눈에 보이면 끝까지 보신다.
   *
   * 담아 둔 것을 읽는 일이라 화면이 붙은 **뒤에** 한다 — 서버에는 없는 값이다.
   */
  const [seen, setSeen] = useState<StepKey[] | null>(null)

  useEffect(() => {
    try {
      setSeen(parseSeen(window.localStorage.getItem(seenStorageKey(eventId))))
    } catch {
      setSeen([])
    }
  }, [eventId])

  const left = seen === null ? [] : unseenSteps(seen)

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
      {/* 여기까지 보셨습니다 — 남은 것이 보이면 끝까지 보신다 */}
      {seen !== null && (
        <div className="grid gap-1.5" data-testid="demo-seen">
          <p className="text-sm">
            {left.length === 0 ? (
              <strong>구경할 것을 다 보셨습니다.</strong>
            ) : (
              <>
                여기까지 보셨습니다 —{' '}
                <strong>
                  {SEEN_STEPS.length - left.length} / {SEEN_STEPS.length}
                </strong>
                . 아직 안 보신 것이 <strong>{left.length}가지</strong> 있습니다.
              </>
            )}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {SEEN_STEPS.map((key) => {
              const done = seen.includes(key)
              return (
                <Link
                  key={key}
                  href={stepHref(key, eventId)}
                  data-testid={`demo-seen-${key}`}
                  data-seen={done ? 'yes' : 'no'}
                  className={cn(
                    'inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition-colors',
                    done
                      ? 'border-border text-muted-foreground'
                      : 'border-accent bg-background font-medium text-foreground hover:bg-accent/10',
                  )}
                >
                  {done ? <Check className="h-3 w-3" aria-hidden /> : null}
                  {getStep(key).name}
                  {!done && <span className="text-muted-foreground">아직</span>}
                </Link>
              )
            })}
          </div>
        </div>
      )}

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
