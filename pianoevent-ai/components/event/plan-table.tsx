import { formatDuration, formatWallClock } from '@/lib/format'
import { STAGE_LABEL, type ProgramBreak, type ProgramItem, type ProgramPlan } from '@/lib/types'

/** 순서표 본문 — 화면과 인쇄가 같은 컴포넌트를 쓴다 */
export function PlanTable({
  plan,
  startISO,
  showScript = false,
  scripts,
}: {
  plan: ProgramPlan
  startISO: string
  showScript?: boolean
  scripts?: Record<string, string | null>
}) {
  const rows: ({ kind: 'item'; item: ProgramItem } | { kind: 'break'; brk: ProgramBreak })[] = []
  const breaksByOrder = new Map(plan.breaks.map((b) => [b.after_order_no, b]))

  for (const item of plan.items) {
    const brk = breaksByOrder.get(item.order_no - 1)
    if (brk) rows.push({ kind: 'break', brk })
    rows.push({ kind: 'item', item })
  }

  let lastStage: string | null = null

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b-2 border-foreground/80 text-left text-xs uppercase tracking-wide text-muted-foreground">
          <th className="w-12 py-2 font-medium">순서</th>
          <th className="w-20 py-2 font-medium">예상 시각</th>
          <th className="py-2 font-medium">연주자 · 곡</th>
          <th className="w-20 py-2 text-right font-medium">연주시간</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => {
          if (row.kind === 'break') {
            return (
              <tr key={`break-${index}`} className="bg-muted/50">
                <td colSpan={4} className="py-2 text-center text-xs font-medium tracking-wide text-muted-foreground">
                  — {row.brk.label} ({formatDuration(row.brk.duration_sec)}) —
                </td>
              </tr>
            )
          }

          const { item } = row
          const stageChanged = item.stage !== lastStage
          lastStage = item.stage

          return (
            <tr key={item.student.id} className="print-avoid-break border-b border-border/70 align-top">
              <td className="py-2.5 tabular-nums text-muted-foreground">{item.order_no}</td>
              <td className="py-2.5 tabular-nums text-muted-foreground">
                {formatWallClock(startISO, item.start_offset_sec)}
              </td>
              <td className="py-2.5">
                {stageChanged && (
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-accent">
                    {STAGE_LABEL[item.stage]}
                  </p>
                )}
                <p className="font-medium">
                  {item.student.student_name}
                  <span className="mx-1.5 text-muted-foreground">·</span>
                  <span className="font-normal">{item.student.piece_title || '(곡명 미입력)'}</span>
                </p>
                {item.student.composer && <p className="text-xs text-muted-foreground">{item.student.composer}</p>}
                {showScript && scripts?.[item.student.id] && (
                  <p className="mt-1.5 whitespace-pre-line border-l-2 border-accent/50 pl-3 text-sm leading-relaxed text-muted-foreground">
                    {scripts[item.student.id]}
                  </p>
                )}
              </td>
              <td className="py-2.5 text-right tabular-nums text-muted-foreground">
                {formatDuration(item.duration_sec)}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

export function PlanSummary({ plan, startISO }: { plan: ProgramPlan; startISO: string }) {
  return (
    <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
      <div>
        <dt className="text-xs text-muted-foreground">연주자</dt>
        <dd className="mt-0.5 text-lg font-semibold tabular-nums">{plan.items.length}명</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">연주 시간 합계</dt>
        <dd className="mt-0.5 text-lg font-semibold tabular-nums">{formatDuration(plan.play_sec)}</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">총 러닝타임</dt>
        <dd className="mt-0.5 text-lg font-semibold tabular-nums">{formatDuration(plan.total_sec)}</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">예상 종료</dt>
        <dd className="mt-0.5 text-lg font-semibold tabular-nums">{formatWallClock(startISO, plan.total_sec)}</dd>
      </div>
    </dl>
  )
}
