import Link from 'next/link'
import { notFound } from 'next/navigation'
import { CopyButton } from '@/components/copy-button'
import { PrintButton } from '@/components/print-button'
import { formatEventDate, formatWallClock } from '@/lib/format'
import { resolvePlan } from '@/lib/program/resolve'
import { buildMcScript } from '@/lib/program/script'
import { getRepository } from '@/lib/store'

export const dynamic = 'force-dynamic'
export const metadata = { title: '사회자 대본' }

export default async function ScriptPage({ params }: { params: { id: string } }) {
  const repo = getRepository()
  const event = await repo.getEvent(params.id)
  if (!event) notFound()

  const [academy, students] = await Promise.all([repo.getAcademy(event.academy_id), repo.listStudents(event.id)])
  const { plan } = resolvePlan(students)
  const fallback = buildMcScript(plan, {
    eventTitle: event.title,
    academyName: academy?.name ?? '피아노학원',
  })

  const opening = event.mc_opening ?? fallback.opening
  const closing = event.mc_closing ?? fallback.closing
  const scriptFor = (id: string) => students.find((s) => s.id === id)?.mc_script ?? fallback.byStudentId[id] ?? ''

  const fullText = [
    `[오프닝]\n${opening}`,
    ...plan.items.map(
      (item) => `[${item.order_no}. ${item.student.student_name} — ${item.student.piece_title}]\n${scriptFor(item.student.id)}`,
    ),
    `[클로징]\n${closing}`,
  ].join('\n\n')

  return (
    <div className="min-h-screen bg-muted/40 py-8 print:bg-white print:py-0">
      <div className="mx-auto flex max-w-[820px] flex-wrap items-center justify-between gap-2 px-4 pb-4 no-print">
        <Link href={`/events/${event.id}`} className="text-sm text-muted-foreground hover:text-foreground">
          ← {event.title}
        </Link>
        <div className="flex gap-2">
          <CopyButton text={fullText} label="전체 대본 복사" />
          <PrintButton label="대본 인쇄" />
        </div>
      </div>

      <article className="print-page mx-auto max-w-[820px] bg-white px-12 py-12 shadow-sm">
        <header className="border-b border-border pb-5">
          <h1 className="font-serif text-2xl font-bold tracking-tight">{event.title} · 사회자 대본</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {formatEventDate(event.event_at)}
            {event.venue ? ` · ${event.venue}` : ''} · 총 {plan.items.length}곡
          </p>
        </header>

        <section className="print-avoid-break mt-8">
          <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">오프닝</h2>
          <p className="mt-2 whitespace-pre-line text-[15px] leading-loose">{opening}</p>
        </section>

        <ol className="mt-8 space-y-6">
          {plan.items.map((item) => (
            <li key={item.student.id} className="print-avoid-break border-t border-border pt-5">
              <div className="flex items-baseline justify-between gap-3">
                <h3 className="font-semibold">
                  {item.order_no}. {item.student.student_name}
                  <span className="ml-2 font-normal text-muted-foreground">
                    {item.student.piece_title}
                    {item.student.composer ? ` / ${item.student.composer}` : ''}
                  </span>
                </h3>
                <span className="whitespace-nowrap text-xs tabular-nums text-muted-foreground">
                  {formatWallClock(event.event_at, item.start_offset_sec)}
                </span>
              </div>
              <p className="mt-2 whitespace-pre-line text-[15px] leading-loose">{scriptFor(item.student.id)}</p>
            </li>
          ))}
        </ol>

        <section className="print-avoid-break mt-8 border-t border-border pt-5">
          <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">클로징</h2>
          <p className="mt-2 whitespace-pre-line text-[15px] leading-loose">{closing}</p>
        </section>
      </article>
    </div>
  )
}
