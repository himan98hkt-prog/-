import { REQUIRED_STEPS, isDone, stepTone, type FlowState } from '@/lib/flow/steps'

/**
 * 이 행사가 몇 단계까지 왔는지 — 아주 작게.
 *
 * 행사 목록에서 여러 행사를 함께 준비하실 때, 어느 것이 급한지 한눈에 아셔야 한다.
 * 목록에 글을 늘리면 그것대로 안 읽으시므로 **점 세 개**로만 말한다.
 */
export function ProgressDots({ state, showLabel = true }: { state: FlowState; showLabel?: boolean }) {
  const done = REQUIRED_STEPS.filter((s) => isDone(s.key, state)).length
  const all = done === REQUIRED_STEPS.length

  return (
    <span className="flex items-center gap-1.5" data-testid="progress-dots" data-done={done}>
      <span className="flex items-center gap-1" aria-hidden>
        {REQUIRED_STEPS.map((step) => {
          const finished = isDone(step.key, state)
          const tone = stepTone(step.key)
          return (
            <span
              key={step.key}
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: finished ? tone.band : 'hsl(0 0% 84%)' }}
              title={`${step.no}. ${step.name}${finished ? ' — 끝났습니다' : ''}`}
            />
          )
        })}
      </span>
      {showLabel && (
        <span className="text-xs text-muted-foreground">
          {all ? '준비 끝' : `${done} / ${REQUIRED_STEPS.length}`}
        </span>
      )}
      <span className="sr-only">
        꼭 하셔야 하는 {REQUIRED_STEPS.length}가지 중 {done}가지를 끝내셨습니다.
      </span>
    </span>
  )
}
