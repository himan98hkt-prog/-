import { CalendarDays, MapPin, Music } from 'lucide-react'
import { notFound } from 'next/navigation'
import { RsvpForm } from '@/components/rsvp/rsvp-form'
import { formatEventDate } from '@/lib/format'
import { resolvePlan } from '@/lib/program/resolve'
import { getRepository, summarizeRsvps } from '@/lib/store'

export const dynamic = 'force-dynamic'

export async function generateMetadata({ params }: { params: { id: string } }) {
  const event = await getRepository().getEvent(params.id)
  if (!event) return { title: '초대장' }
  return {
    title: event.title,
    description: `${formatEventDate(event.event_at)}${event.venue ? ` · ${event.venue}` : ''}`,
    openGraph: { title: event.title, description: event.venue || '' },
  }
}

/** 학부모가 카카오톡 링크로 여는 공개 초대장. 로그인 없이 열린다. */
export default async function InvitePage({ params }: { params: { id: string } }) {
  const repo = getRepository()
  const event = await repo.getEvent(params.id)
  if (!event) notFound()

  const [academy, students, rsvps] = await Promise.all([
    repo.getAcademy(event.academy_id),
    repo.listStudents(event.id),
    repo.listRsvps(event.id),
  ])
  const { plan, saved } = resolvePlan(students)
  const summary = summarizeRsvps(rsvps)

  return (
    <main className="mx-auto min-h-screen max-w-md bg-background pb-16">
      <section className="bg-primary px-6 py-14 text-center text-primary-foreground">
        <p className="text-xs tracking-[0.35em] opacity-80">{academy?.name ?? ''}</p>
        <h1 className="mt-4 font-serif text-3xl font-bold leading-snug">{event.title}</h1>
        <div className="mt-6 space-y-1.5 text-sm opacity-90">
          <p className="flex items-center justify-center gap-1.5">
            <CalendarDays className="h-4 w-4" aria-hidden />
            {formatEventDate(event.event_at)}
          </p>
          {event.venue && (
            <p className="flex items-center justify-center gap-1.5">
              <MapPin className="h-4 w-4" aria-hidden />
              {event.venue}
            </p>
          )}
        </div>
      </section>

      {event.greeting && (
        <section className="px-6 py-10 text-center">
          <p className="whitespace-pre-line text-[15px] leading-loose text-muted-foreground">{event.greeting}</p>
        </section>
      )}

      {saved && plan.items.length > 0 && (
        <section className="border-y border-border bg-card px-6 py-8">
          <h2 className="flex items-center justify-center gap-2 text-sm font-semibold tracking-wide">
            <Music className="h-4 w-4 text-accent" aria-hidden />
            연주 순서
          </h2>
          <ol className="mt-5 space-y-3">
            {plan.items.map((item) => (
              <li key={item.student.id} className="flex gap-3 text-sm">
                <span className="w-5 shrink-0 tabular-nums text-muted-foreground">{item.order_no}</span>
                <span className="min-w-0">
                  <span className="font-medium">{item.student.student_name}</span>
                  <span className="mx-1.5 text-muted-foreground">·</span>
                  <span className="text-muted-foreground">{item.student.piece_title}</span>
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="px-6 py-10">
        <h2 className="text-center text-base font-semibold">참석 여부를 알려 주세요</h2>
        <p className="mt-1.5 text-center text-sm text-muted-foreground">
          좌석 준비를 위해 참석 인원을 미리 확인하고 있습니다.
        </p>
        <div className="mt-6">
          <RsvpForm eventId={event.id} />
        </div>
      </section>

      {summary.messages.length > 0 && (
        <section className="border-t border-border px-6 py-10">
          <h2 className="text-center text-sm font-semibold tracking-wide">응원 메시지 {summary.messages.length}개</h2>
          <ul className="mt-5 space-y-3">
            {summary.messages.slice(0, 20).map((m, index) => (
              <li key={`${m.created_at}-${index}`} className="rounded-lg border border-border bg-card px-4 py-3 text-sm">
                <p className="leading-relaxed">{m.message}</p>
                <p className="mt-1.5 text-xs text-muted-foreground">— {m.name}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer className="px-6 pt-8 text-center text-xs text-muted-foreground">
        {academy?.name} · PianoEvent AI 로 만든 초대장
      </footer>
    </main>
  )
}
