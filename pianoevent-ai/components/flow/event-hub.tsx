import { ArrowRight, Check } from 'lucide-react'
import Link from 'next/link'
import {
  EXTRA_STEPS,
  REQUIRED_STEPS,
  isDone,
  progress,
  stepHref,
  stepTone,
  type FlowState,
} from '@/lib/flow/steps'
import { cn } from '@/lib/utils'

/**
 * 행사 화면 맨 위 — "무엇부터 하나요" 에 대한 답.
 *
 * 예전에는 여기 갈 곳이 열한 군데였다. 탭 네 개에 단추 일곱 개, 크기도 색도 같았다.
 * 원장님 눈에는 **열한 개가 다 똑같이 중요해 보인다.** 그래서 아무것도 못 고르신다.
 *
 * 이제는 둘로 가른다.
 *   위 — 꼭 하셔야 하는 **세 가지**. 크게, 색으로, 지금 할 것 하나만 도드라지게.
 *   아래 — 하시면 좋은 것들. 작게, 접어서.
 *
 * 크기 차이가 곧 설명이다.
 */
export function EventHub({ eventId, state }: { eventId: string; state: FlowState }) {
  const bar = progress(state)

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">
          {bar.allDone ? '연주회 준비가 끝났습니다' : `이 세 가지만 하시면 됩니다`}
        </h2>
        <p className="text-sm text-muted-foreground">
          {bar.allDone ? '아래는 하시면 더 좋은 것들입니다.' : `지금 ${bar.done} / ${bar.total} 끝나셨습니다.`}
        </p>
      </div>

      <ol className="stagger grid gap-3 sm:grid-cols-3" data-testid="event-hub">
        {REQUIRED_STEPS.map((step) => {
          const finished = isDone(step.key, state)
          const now = bar.next?.key === step.key
          const tone = stepTone(step.key)
          return (
            <li key={step.key}>
              <Link
                href={stepHref(step.key, eventId)}
                className={cn(
                  'surface-lift press nudge flex h-full flex-col rounded-xl border p-4',
                  now && 'shadow-md ring-2',
                )}
                style={{
                  background: finished ? '#fff' : tone.bg,
                  borderColor: now ? tone.band : tone.soft,
                  // 지금 할 것 하나만 눈에 들어와야 한다
                  ...(now ? ({ '--tw-ring-color': tone.band } as never) : {}),
                }}
                data-testid={`hub-${step.key}`}
                data-now={now ? 'yes' : 'no'}
              >
                <span className="flex items-center gap-2">
                  <span
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
                    style={{ background: finished ? tone.band : now ? tone.band : 'hsl(0 0% 76%)' }}
                  >
                    {finished ? <Check className="h-4 w-4" aria-hidden /> : step.no}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate font-semibold" style={{ color: tone.ink }}>
                      {step.name}
                    </span>
                    {now && (
                      <span className="text-xs font-medium" style={{ color: tone.band }}>
                        지금 하실 차례입니다
                      </span>
                    )}
                    {finished && <span className="text-xs text-muted-foreground">끝났습니다</span>}
                  </span>
                </span>
                <span className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.why}</span>
                <span
                  className="mt-3 inline-flex items-center gap-1 text-sm font-medium"
                  style={{ color: tone.band }}
                >
                  {finished ? '다시 보기' : '여기서 하기'}
                  <ArrowRight className="h-4 w-4" aria-hidden />
                </span>
              </Link>
            </li>
          )
        })}
      </ol>

      <details className="rounded-xl border border-border bg-card" data-testid="event-extras">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium">
          하시면 더 좋은 것 {EXTRA_STEPS.length}가지 — 초대장 · 무대 화면 · 감동영상 …
          <span className="ml-1 font-normal text-muted-foreground">(안 하셔도 연주회는 됩니다)</span>
        </summary>
        <ul className="grid gap-2 border-t border-border p-3 sm:grid-cols-2">
          {EXTRA_STEPS.map((step) => {
            const tone = stepTone(step.key)
            // 안 하셔도 되는 것이지만, 해 두신 것을 또 하러 들어가시는 일은 없어야 한다
            const finished = isDone(step.key, state)
            return (
              <li key={step.key}>
                <Link
                  href={stepHref(step.key, eventId)}
                  className="surface-lift press flex h-full flex-col rounded-lg border border-border px-3 py-2.5 hover:bg-secondary"
                  data-testid={`extra-${step.key}`}
                  data-done={finished ? 'yes' : 'no'}
                >
                  <span className="flex items-center gap-2 text-sm font-medium">
                    {finished ? (
                      <span
                        className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-white"
                        style={{ background: tone.band }}
                        aria-hidden
                      >
                        <Check className="h-3 w-3" />
                      </span>
                    ) : (
                      <span
                        className="h-2.5 w-2.5 shrink-0 rounded-full"
                        style={{ background: tone.band }}
                        aria-hidden
                      />
                    )}
                    {step.name}
                    {finished && (
                      <span className="ml-auto shrink-0 text-xs font-normal" style={{ color: tone.ink }}>
                        해 두셨습니다
                      </span>
                    )}
                  </span>
                  <span className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{step.why}</span>
                </Link>
              </li>
            )
          })}
        </ul>
      </details>
    </div>
  )
}
