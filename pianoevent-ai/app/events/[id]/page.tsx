import { Camera, CalendarDays, Check, Film, ListChecks, MapPin, Mic2, MonitorPlay, Palette, Send } from 'lucide-react'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { PlanPanel } from '@/components/event/plan-panel'
import { PrepPanel } from '@/components/event/prep-panel'
import { ProgramPanel } from '@/components/event/program-panel'
import { RosterEditor } from '@/components/event/roster-editor'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { formatEventDate } from '@/lib/format'
import { normalizeTimingLog } from '@/lib/ops/timing'
import { resolvePlan } from '@/lib/program/resolve'
import { currentAcademy } from '@/lib/session'
import { getRepository } from '@/lib/store'
import { EVENT_STATUS_LABEL } from '@/lib/types'
import { cn } from '@/lib/utils'

export const dynamic = 'force-dynamic'

const TABS = [
  { key: 'roster', label: '학생 명단' },
  { key: 'program', label: '순서표 · 대본' },
  { key: 'plan', label: '리허설 · 예산 · 좌석' },
  { key: 'prep', label: '진행 준비' },
] as const

/**
 * 처음 쓰는 원장을 위한 3단계 안내.
 * 무엇부터 해야 하는지 몰라 멈추는 지점이 여기라서, 화면 맨 위에 순서를 박아 둔다.
 */
function StepGuide({
  eventId,
  hasStudents,
  hasProgram,
  hasPrint,
}: {
  eventId: string
  hasStudents: boolean
  hasProgram: boolean
  hasPrint: boolean
}) {
  const steps = [
    {
      done: hasStudents,
      title: '① 학생 명단 넣기',
      body: '엑셀 파일을 끌어다 놓으면 됩니다.',
      href: `/events/${eventId}?tab=roster`,
    },
    {
      done: hasProgram,
      title: '② 순서표 · 대본 만들기',
      body: '버튼 한 번이면 순서와 사회자 멘트가 나옵니다.',
      href: `/events/${eventId}?tab=program`,
    },
    {
      done: hasPrint,
      title: '③ 인쇄물 · 초대장 보내기',
      body: '포스터를 뽑고 초대장 링크를 단톡방에 보냅니다.',
      href: `/events/${eventId}/design`,
    },
  ]

  if (hasStudents && hasProgram && hasPrint) return null

  return (
    <ol className="mb-5 grid gap-3 sm:grid-cols-3">
      {steps.map((step) => (
        <li key={step.title}>
          <Link
            href={step.href}
            className={cn(
              'flex h-full gap-2.5 rounded-lg border px-4 py-3 transition-colors',
              step.done ? 'border-accent/40 bg-accent/5' : 'border-border hover:bg-secondary',
            )}
          >
            <span
              className={cn(
                'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px]',
                step.done ? 'bg-accent text-accent-foreground' : 'border border-input text-muted-foreground',
              )}
              aria-hidden
            >
              {step.done ? <Check className="h-3 w-3" /> : ''}
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-medium">{step.title}</span>
              <span className="block text-xs text-muted-foreground">{step.body}</span>
            </span>
          </Link>
        </li>
      ))}
    </ol>
  )
}

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

  const [students, rsvps, siblings] = await Promise.all([
    repo.listStudents(event.id),
    repo.listRsvps(event.id),
    repo.listEvents(event.academy_id),
  ])
  // 명단을 그대로 가져올 수 있는 지난 행사 — 학생이 실제로 있는 것만
  const pastEvents = (
    await Promise.all(
      siblings
        .filter((e) => e.id !== event.id)
        .slice(0, 12)
        .map(async (e) => ({ id: e.id, title: e.title, count: (await repo.listStudents(e.id)).length })),
    )
  ).filter((e) => e.count > 0)
  const { plan } = resolvePlan(students)
  const tab = (['roster', 'program', 'plan', 'prep'] as const).includes(searchParams.tab as never)
    ? (searchParams.tab as 'roster' | 'program' | 'plan' | 'prep')
    : 'roster'

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
            <Link href={`/events/${event.id}/stage`}>
              <Button variant="outline" size="sm">
                <MonitorPlay className="h-4 w-4" aria-hidden />
                무대 화면
              </Button>
            </Link>
            <Link href={`/events/${event.id}/video`}>
              <Button variant="outline" size="sm">
                <Film className="h-4 w-4" aria-hidden />
                감동영상
              </Button>
            </Link>
            <Link href={`/events/${event.id}/photos`}>
              <Button variant="outline" size="sm">
                <Camera className="h-4 w-4" aria-hidden />
                사진 모으기
              </Button>
            </Link>
            <Link href={`/events/${event.id}/live`}>
              <Button variant="outline" size="sm">
                <ListChecks className="h-4 w-4" aria-hidden />
                당일 진행
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

      <StepGuide
        eventId={event.id}
        hasStudents={students.length > 0}
        hasProgram={event.program_source !== null}
        hasPrint={event.status === 'published' || event.design_template !== null}
      />

      {tab === 'roster' && (
        <RosterEditor
          eventId={event.id}
          students={students}
          pastEvents={pastEvents}
          assets={academy.assets ?? []}
          timings={normalizeTimingLog(academy.timing_log)}
        />
      )}
      {tab === 'program' && <ProgramPanel event={event} students={students} />}
      {tab === 'plan' && <PlanPanel academy={academy} event={event} plan={plan} rsvps={rsvps} />}
      {tab === 'prep' && <PrepPanel academy={academy} event={event} plan={plan} />}
    </AppShell>
  )
}
