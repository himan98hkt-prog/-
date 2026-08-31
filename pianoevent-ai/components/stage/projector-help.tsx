'use client'

import { ChevronDown, Monitor } from 'lucide-react'
import { useState } from 'react'
import { PROJECTOR_GUIDE, PROJECTOR_PACKING, PROJECTOR_WHEN } from '@/lib/ops/projector'
import { cn } from '@/lib/utils'

/**
 * **노트북을 빔프로젝터에 꽂는 법.**
 *
 * 여기서 대부분 멈추신다. 화면은 다 만들어 놓고, 정작 연주회장에서 선을 꽂았는데
 * 스크린에 아무것도 안 나오거나, 원장님 노트북 화면이 그대로(순서표·메신저까지) 나간다.
 *
 * 이건 우리 프로그램이 아니라 **윈도우·맥의 일**이라 화면에서 해 드릴 수가 없다.
 * 그래서 **눌러야 할 자판**만 정확히 적어 둔다. 연주회장에서 이 화면을 열어 두시면 된다.
 *
 * 접어 둔다 — 아는 분께는 군더더기고, 모르는 분께는 이 한 줄이 전부다.
 */
export function ProjectorHelp() {
  const [open, setOpen] = useState(false)

  return (
    <div className="no-print rounded-lg border border-border p-3" data-testid="projector-help">
      <button
        type="button"
        onClick={() => setOpen((on) => !on)}
        aria-expanded={open}
        className="flex w-full items-center gap-1.5 text-left text-sm font-medium"
        data-testid="projector-toggle"
      >
        <Monitor className="h-4 w-4 text-accent" aria-hidden />
        빔프로젝터에 꽂았는데 스크린에 안 나옵니다
        <ChevronDown className={cn('ml-auto h-4 w-4 transition-transform', open && 'rotate-180')} aria-hidden />
      </button>

      {open && (
        <div className="mt-3 grid gap-3 border-t border-border pt-3 text-sm" data-testid="projector-steps">
          {PROJECTOR_GUIDE.map((block) => (
            <div key={block.title}>
              <p className="font-medium">{block.title}</p>
              <ol className="mt-1 grid gap-1 text-muted-foreground">
                {block.steps.map((step, i) => (
                  <li key={step}>
                    {i + 1}. {step}
                  </li>
                ))}
              </ol>
            </div>
          ))}

          <div>
            <p className="font-medium">가방에 넣어 가실 것</p>
            <ul className="mt-1 grid gap-1 text-muted-foreground">
              {PROJECTOR_PACKING.map((item) => (
                <li key={item}>· {item}</li>
              ))}
            </ul>
          </div>

          <p className="rounded-md border border-accent/40 bg-accent/5 px-3 py-2 text-xs">
            <strong>언제 해 보나요</strong> — {PROJECTOR_WHEN}
          </p>
          <p className="text-xs text-muted-foreground">
            {/* 안 나오는 상황에서는 노트북을 못 쓰신다. 그러니 종이가 있어야 한다 */}
            연주회장에서 노트북이 안 켜지면 이 화면도 못 보십니다 — <strong>인쇄물 디자인</strong> 에서{' '}
            <strong>[빔프로젝터 연결 카드]</strong> 를 한 장 뽑아 가방에 넣어 가세요.
          </p>
        </div>
      )}
    </div>
  )
}
