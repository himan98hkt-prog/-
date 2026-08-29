import { printSummary } from '@/lib/print/paper'

/**
 * 뽑기 직전 마지막 확인.
 *
 * 인쇄 창의 낱말은 브라우저마다 다르고, 원장님은 그 창에서 무엇을 봐야 하는지 모르신다.
 * 그래서 누르시기 **전에** 넷을 큰 글씨로 세워 둔다 — 종이 · 장수 · 색 · 양면.
 * 인쇄 창에서 이 넷만 같은지 보시면 된다.
 */
export function PrintSummary({
  paperLabel,
  sheets,
  copies = 1,
  duplex = false,
  grayOk = false,
}: {
  paperLabel: string
  sheets: number
  copies?: number
  duplex?: boolean
  grayOk?: boolean
}) {
  const rows = printSummary({ paperLabel, sheets, copies, duplex, grayOk })

  return (
    <div
      className="mt-2 rounded-md border border-accent/40 bg-accent/5 px-3 py-2"
      data-testid="print-summary"
    >
      <p className="text-xs font-medium text-muted-foreground">뽑기 전에 이것만 보세요</p>
      <dl className="mt-1 flex flex-wrap gap-x-5 gap-y-1">
        {rows.map((row) => (
          <div key={row.what} className="flex items-baseline gap-1.5">
            <dt className="text-xs text-muted-foreground">{row.what}</dt>
            <dd className="text-base font-semibold leading-tight">{row.value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-1 text-xs text-muted-foreground">
        인쇄 창에서도 이 넷이 같은지만 보시면 됩니다. 다르면 인쇄 창에서 고치세요.
      </p>
    </div>
  )
}
