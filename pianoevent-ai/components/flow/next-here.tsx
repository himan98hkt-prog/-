'use client'

import { ArrowRight, Check, Loader2 } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { getStep, stepHref, stepTone, type StepKey } from '@/lib/flow/steps'

/**
 * "다음 것도 지금 여기서 하시겠어요?"
 *
 * 화면을 옮기는 것 자체가 부담이다. 명단을 다 넣으시고 나면 다음은 순서표인데,
 * 그러려면 위로 올라가 다른 화면을 찾아 눌러야 한다. 그 사이에 멈추신다.
 *
 * 그래서 **하시던 자리에서** 다음 것을 끝내 드린다. 단추 하나다.
 * 끝나면 그 화면으로 모셔다 드린다 — 결과를 보셔야 하니까.
 */
export function NextHere({
  step,
  eventId,
  label,
  hint,
  run,
}: {
  /** 여기서 끝내 드릴 다음 단계 */
  step: StepKey
  eventId: string
  /** 단추에 적을 말 */
  label: string
  hint: string
  /** 실제로 하는 일. 끝나면 그 화면으로 옮겨 간다 */
  run: () => Promise<void>
}) {
  const router = useRouter()
  const next = getStep(step)
  const tone = stepTone(step)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  async function go() {
    setBusy(true)
    setError(null)
    try {
      await run()
      setDone(true)
      router.push(stepHref(step, eventId))
      router.refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : '하지 못했습니다. 다시 눌러 보세요.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section
      className="grid gap-2 rounded-xl border p-4 no-print"
      style={{ background: tone.bg, borderColor: tone.soft }}
      data-testid="next-here"
      data-step={step}
    >
      <p className="text-sm font-semibold" style={{ color: tone.ink }}>
        다 되셨습니다. 다음은 <strong>{next.no ? `${next.no}. ` : ''}{next.name}</strong> 입니다.
      </p>
      <p className="text-sm text-muted-foreground">{hint}</p>

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={go} disabled={busy || done} style={{ background: tone.band }} data-testid="next-here-go">
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : done ? (
            <Check className="h-4 w-4" aria-hidden />
          ) : (
            <ArrowRight className="h-4 w-4" aria-hidden />
          )}
          {busy ? '만들고 있습니다…' : done ? '됐습니다' : label}
        </Button>
        <span className="text-xs text-muted-foreground">
          화면을 옮기지 않으셔도 됩니다 — 여기서 끝내고 결과를 보여 드립니다.
        </span>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
    </section>
  )
}
