import { CalendarDays, MapPin, Mic2, Palette, Send } from 'lucide-react'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { ProgramPanel } from '@/components/event/program-panel'
import { RosterEditor } from '@/components/event/roster-editor'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { formatEventDate } from '@/lib/format'
import { currentAcademy } from '@/lib/session'
import { getRepository } from '@/lib/store'
import { EVENT_STATUS_LABEL } from '@/lib/types'
import { cn } from '@/lib/utils'

export const dynamic = 'force-dynamic'

const TABS = [
  { key: 'roster', label: '학생 명단' },
  { key: 'program', label: '순서표 · 대본' },
] as const

export async function generateMetadata({ params }: { params: { id: string } }) {
  const event = await getRepository().getEvent(params.id)
  return { title: event?.title ?? '행사' }
}

export default async function EventPage({
  params,
  searchParams,
}: {
  params: { id: string }
  searchParams: { tab?: string }
}) {
  const repo = getRepository()
  const [academy, event] = await Promise.all([currentAcademy(), repo.getEvent(params.id)])
  if (!event) notFound()

  const students = await repo.listStudents(event.id)
  const tab = searchParams.tab === 'program' ? 'program' : 'roster'

  return (
    <AppShell academyName={academy.name}>
      <div className="mb-6">
        <Link href="/events" className="text-sm text-muted-foreground hover:text-foreground">
          ← 행사 목록
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">{event.title}</h1>
              <Badge variant={event.status === 'draft' ? 'outline' : 'accent'}>
                {EVENT_STATUS_LABEL[event.status]}
              </Badge>
            </div>
            <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <CalendarDays className="h-3.5 w-3.5" aria-hidden />
                {formatEventDate(event.event_at)}
              </span>
              {event.venue && (
                <span className="flex items-center gap-1.5">
                  <MapPin className="h-3.5 w-3.5" aria-hidden />
                  {event.venue}
                </span>
              )}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href={`/events/${event.id}/script`}>
              <Button variant="outline" size="sm">
                <Mic2 className="h-4 w-4" aria-hidden />
                사회자 대본
              </Button>
            </Link>
            <Link href={`/events/${event.id}/design`}>
              <Button variant="outline" size="sm">
                <Palette className="h-4 w-4" aria-hidden />
                인쇄물 디자인
              </Button>
            </Link>
            <Link href={`/events/${event.id}/invite`}>
              <Button size="sm">
                <Send className="h-4 w-4" aria-hidden />
                초대장 · 참석 집계
              </Button>
            </Link>
          </div>
        </div>
      </div>

      <nav className="mb-5 flex gap-1 border-b border-border">
        {TABS.map((item) => (
          <Link
            key={item.key}
            href={`/events/${event.id}?tab=${item.key}`}
            className={cn(
              '-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors',
              tab === item.key
                ? 'border-accent text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {item.label}
            {item.key === 'roster' && students.length > 0 && (
              <span className="ml-1.5 text-xs text-muted-foreground">{students.length}</span>
            )}
          </Link>
        ))}
      </nav>

      {tab === 'roster' ? (
        <RosterEditor eventId={event.id} students={students} />
      ) : (
        <ProgramPanel event={event} students={students} />
      )}
    </AppShell>
  )
}
