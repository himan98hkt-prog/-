import Link from 'next/link'
import { AppShell } from '@/components/app-shell'
import { studentPhotos } from '@/lib/assets'
import { formatDuration, formatShortDate } from '@/lib/format'
import { countedEvent, historyNote, sortHistory, summarizeHistory, type HistoryRow } from '@/lib/ops/history'
import { normalizeTimingLog, timingSummary } from '@/lib/ops/timing'
import { performerCount } from '@/lib/program/appearances'
import { resolvePlan } from '@/lib/program/resolve'
import { currentAcademy } from '@/lib/session'
import { getRepository, summarizeRsvps } from '@/lib/store'

export const dynamic = 'force-dynamic'
export const metadata = { title: '학원 기록' }

/**
 * 학원 기록 — 해마다 어땠는지 한 장으로.
 * 새로 입력받는 것은 없다. 이미 들어 있는 것을 세어 보여 줄 뿐이다.
 */
export default async function HistoryPage() {
  const repo = getRepository()
  const academy = await currentAcademy()
  const events = await repo.listEvents(academy.id)

  const rows: HistoryRow[] = []
  for (const event of events.slice(0, 24)) {
    const [students, rsvps] = await Promise.all([repo.listStudents(event.id), repo.listRsvps(event.id)])
    const { plan } = resolvePlan(students)
    const performers = performerCount(students)
    if (!countedEvent(event, performers)) continue
    rows.push({
      id: event.id,
      title: event.title,
      event_at: event.event_at,
      performers,
      pieces: students.length,
      planned_sec: plan.total_sec,
      headcount: summarizeRsvps(rsvps).headcount,
      withPhoto: Object.keys(studentPhotos(academy.assets ?? [], students)).length,
    })
  }

  const history = sortHistory(rows)
  const summary = summarizeHistory(history)
  const timings = timingSummary(normalizeTimingLog(academy.timing_log))
  const most = Math.max(1, ...history.map((row) => row.performers))

  return (
    <AppShell academyName={academy.name}>
      <div className="mb-5">
        <h1 className="text-2xl font-bold tracking-tight">학원 기록</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          치른 연주회를 한 장으로 모았습니다. 다음 연주회 규모를 정하실 때 보시면 됩니다.
        </p>
      </div>

      {history.length === 0 ? (
        <p className="rounded-lg border border-border px-4 py-10 text-center text-sm text-muted-foreground">
          아직 쌓인 기록이 없습니다. 연주회를 <strong>초대장 배포</strong> 또는 <strong>종료</strong> 로 두시면
          여기에 남습니다.{' '}
          <Link href="/events" className="underline underline-offset-4">
            행사 목록
          </Link>
        </p>
      ) : (
        <div className="grid gap-5">
          <section className="grid gap-3 rounded-lg border border-accent/40 bg-accent/5 p-4" data-testid="history-top">
            <p className="text-sm">{historyNote(summary)}</p>
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { k: '치른 연주회', v: `${summary.events}회` },
                { k: '연주자 평균', v: `${summary.averagePerformers}명` },
                { k: '가장 많았을 때', v: `${summary.mostPerformers}명` },
                { k: '러닝타임 평균', v: formatDuration(summary.averageSec) },
              ].map((cell) => (
                <div key={cell.k}>
                  <dt className="text-xs text-muted-foreground">{cell.k}</dt>
                  <dd className="text-lg font-semibold tabular-nums">{cell.v}</dd>
                </div>
              ))}
            </dl>
          </section>

          <section className="rounded-lg border border-border" data-testid="history-rows">
            <p className="border-b border-border px-4 py-2 text-sm font-medium">해마다</p>
            <ul>
              {history.map((row) => (
                <li key={row.id} className="border-b border-border/60 px-4 py-3 last:border-0">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <Link href={`/events/${row.id}`} className="font-medium hover:underline">
                      {row.title}
                    </Link>
                    <span className="text-xs text-muted-foreground">{formatShortDate(row.event_at)}</span>
                  </div>
                  {/* 막대 하나가 표 한 장보다 빨리 읽힌다 */}
                  <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-secondary">
                    <div
                      className="h-full bg-accent"
                      style={{ width: `${Math.round((row.performers / most) * 100)}%` }}
                    />
                  </div>
                  <p className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
                    <span className="tabular-nums">
                      연주자 <strong className="text-foreground">{row.performers}명</strong>
                      {row.pieces !== row.performers && ` · ${row.pieces}곡`}
                    </span>
                    <span className="tabular-nums">러닝타임 {formatDuration(row.planned_sec)}</span>
                    {row.headcount > 0 && <span className="tabular-nums">참석 {row.headcount}명</span>}
                    <span className="tabular-nums">사진 {row.withPhoto}명</span>
                  </p>
                </li>
              ))}
            </ul>
          </section>

          {timings.records > 0 && (
            <section className="grid gap-1 rounded-lg border border-border p-4" data-testid="history-timings">
              <p className="text-sm font-medium">무대에서 실제로 걸린 시간</p>
              <p className="text-sm text-muted-foreground">
                아이 <strong className="text-foreground">{timings.people}명</strong>의 기록{' '}
                <strong className="text-foreground">{timings.records}건</strong>이 쌓였습니다. 평균{' '}
                <strong className="text-foreground">{formatDuration(timings.averageSec ?? 0)}</strong>.
              </p>
              <p className="text-xs text-muted-foreground">
                당일 진행 화면에서 순서를 넘기실 때마다 쌓입니다. 다음 연주회 순서표의 종료 시각이 이 값으로
                계산됩니다.
              </p>
            </section>
          )}
        </div>
      )}
    </AppShell>
  )
}
