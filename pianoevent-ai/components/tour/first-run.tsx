'use client'

import { ArrowRight, X } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { TOUR_KEY, TOUR_STEPS, nextStep, prevStep, stepLabel } from '@/lib/tour/steps'

/**
 * 처음 켰을 때 뜨는 안내 쪽지.
 *
 * 덮개(모달)로 만들지 않았다. 화면을 가리면 안내를 보면서 눌러 보실 수가 없고,
 * 컴맹 원장님은 "닫기" 를 찾다가 그냥 창을 닫으신다. 오른쪽 아래에 작게 앉혀 두고
 * 뒤쪽은 그대로 쓰실 수 있게 둔다.
 *
 * 한 번 닫으면 이 브라우저에서는 다시 뜨지 않는다 (설명서에서 다시 여실 수 있다).
 */
export function FirstRun() {
  const [at, setAt] = useState<number | null>(null)

  useEffect(() => {
    try {
      if (window.localStorage.getItem(TOUR_KEY) === 'done') return
    } catch {
      // 사생활 보호 모드 등으로 저장을 못 읽는 브라우저 — 안내는 띄우되 기억은 못 한다
    }
    setAt(0)
  }, [])

  function close() {
    try {
      window.localStorage.setItem(TOUR_KEY, 'done')
    } catch {
      /* 못 적어도 닫히기는 해야 한다 */
    }
    setAt(null)
  }

  if (at === null) return null
  const step = TOUR_STEPS[at]

  return (
    <div
      className="fixed bottom-4 right-4 z-30 w-[min(22rem,calc(100vw-2rem))] rounded-lg border border-border bg-card p-4 shadow-lg no-print"
      role="complementary"
      aria-label="처음 쓰시는 분 안내"
      data-testid="first-run"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold">{step.title}</p>
        <button
          type="button"
          onClick={close}
          aria-label="안내 닫기"
          className="-mr-1 -mt-1 rounded p-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
          data-testid="first-run-close"
        >
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>

      <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
      <p className="mt-2 flex items-center gap-1 text-xs text-accent">
        <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        {step.where}
      </p>

      <div className="mt-3 flex items-center gap-2">
        <span className="mr-auto text-xs tabular-nums text-muted-foreground">{stepLabel(at)}</span>
        {at > 0 && (
          <Button variant="ghost" size="sm" onClick={() => setAt(prevStep(at))}>
            이전
          </Button>
        )}
        <Button
          size="sm"
          onClick={() => {
            const next = nextStep(at)
            if (next < 0) close()
            else setAt(next)
          }}
          data-testid="first-run-next"
        >
          {at === TOUR_STEPS.length - 1 ? '알겠습니다' : '다음'}
        </Button>
      </div>

      <p className="mt-2 text-xs text-muted-foreground">
        언제든{' '}
        <Link href="/help" className="underline underline-offset-2 hover:text-foreground">
          사용설명서
        </Link>
        에서 다시 보실 수 있습니다.
      </p>
    </div>
  )
}
