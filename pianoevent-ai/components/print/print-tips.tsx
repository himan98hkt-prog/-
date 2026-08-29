'use client'

import { ChevronDown, FileCheck2, Printer } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { printNow } from '@/components/print/print-now'
import { PrintSummary } from '@/components/print/print-summary'
import { DUPLEX_HINT, PRINT_CHECKLIST, totalSheets } from '@/lib/print/paper'
import { cn } from '@/lib/utils'

/**
 * 인쇄물 화면처럼 **이미 종이 모양 그대로** 그려지는 곳에 붙이는 띠.
 *
 * 미리보기는 화면이 곧 미리보기라 필요 없다. 필요한 것은 나머지 둘 —
 * 종이가 몇 장 나오는지, 인쇄 창에서 무엇을 만지는지.
 */
export function PrintTips({
  what,
  paperLabel,
  sheets,
  approx = false,
  duplex = false,
}: {
  what: string
  paperLabel: string
  sheets: number
  /** 글 길이에 따라 한두 장 더 나올 수 있는 인쇄물이면 켠다 — 딱 떨어지는 척하지 않는다 */
  approx?: boolean
  /** 양면으로 뽑아야 뜻이 있는 인쇄물인가 (반 접는 책자) */
  duplex?: boolean
}) {
  const [howto, setHowto] = useState(false)
  const [copies, setCopies] = useState(1)

  return (
    <div className="rounded-lg border border-border bg-card p-3 no-print" data-testid="print-bar" data-sheets={sheets}>
      <div className="flex flex-wrap items-center gap-2">
        <p className="mr-auto text-sm">
          <strong>{what}</strong> · {paperLabel} · <span data-testid="print-sheets">종이 {sheets}장{approx ? ' 안팎' : ''}</span>
          {copies > 1 && (
            <span className="text-muted-foreground">
              {' '}
              · {copies}부면 {totalSheets(sheets, copies)}장
            </span>
          )}
        </p>

        <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
          부수
          <input
            type="number"
            min={1}
            max={500}
            value={copies}
            onChange={(e) => setCopies(Math.max(1, Math.min(500, Number(e.target.value) || 1)))}
            className="h-8 w-16 rounded-md border border-border bg-background px-2 text-sm"
            aria-label="몇 부 뽑으실지"
          />
        </label>

        {/* 설정이 맞는지는 결국 한 장 뽑아 봐야 아신다. 종이 한 장이 100장을 살린다 */}
        <Button variant="outline" size="sm" onClick={() => printNow(true)} data-testid="print-first">
          <FileCheck2 className="h-4 w-4" aria-hidden />
          첫 장만 뽑아 보기
        </Button>

        <Button size="sm" onClick={() => printNow()} data-testid="print-now">
          <Printer className="h-4 w-4" aria-hidden />
          인쇄 · PDF 저장
        </Button>
      </div>

      {/* 뽑기 직전 마지막 한 줄 — 종이·장수·색·양면 */}
      <PrintSummary paperLabel={paperLabel} sheets={sheets} copies={copies} duplex={duplex} />

      {/* 책자는 양면으로 뽑아야 뜻이 있다. 넘기는 방향까지 틀리면 접었을 때 속장이 뒤집힌다 */}
      {duplex && (
        <p
          className="mt-2 rounded-md border border-accent/40 bg-accent/5 px-3 py-2 text-xs"
          data-testid="duplex-hint"
        >
          <strong>{DUPLEX_HINT.what}</strong> — 인쇄 창에서 <strong>&quot;양면 인쇄&quot;</strong> 를 켜고{' '}
          <strong>&quot;짧은 쪽 넘기기&quot;</strong> 를 고르세요. &quot;긴 쪽&quot; 으로 두면 뒷장이 거꾸로 찍혀
          접었을 때 속장이 뒤집힙니다. 뽑으신 뒤 <strong>반으로 접으면</strong> A5 책자가 됩니다.
        </p>
      )}

      <button
        type="button"
        onClick={() => setHowto((on) => !on)}
        className="mt-2 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        aria-expanded={howto}
        data-testid="print-howto-toggle"
      >
        <ChevronDown className={cn('h-3.5 w-3.5 transition-transform', howto && 'rotate-180')} aria-hidden />
        인쇄 창이 뜨면 무엇을 만지나요?
      </button>
      {howto && (
        <dl className="mt-2 grid gap-1.5 border-t border-border pt-2 text-xs" data-testid="print-howto">
          {PRINT_CHECKLIST.map((item) => (
            <div key={item.what} className="sm:flex sm:gap-2">
              <dt className="shrink-0 font-medium sm:w-28">{item.what}</dt>
              <dd className="text-muted-foreground">{item.how}</dd>
            </div>
          ))}
          <p className="pt-1 text-muted-foreground">
            브라우저마다 낱말이 조금씩 다릅니다. 없으면 <strong>더보기</strong> 안을 보세요.
          </p>
        </dl>
      )}
    </div>
  )
}
