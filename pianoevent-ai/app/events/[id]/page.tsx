import { CalendarDays, MapPin } from 'lucide-react'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { EventHub } from '@/components/flow/event-hub'
import { ScreenHeader } from '@/components/flow/screen-header'
import { PlanPanel } from '@/components/event/plan-panel'
import { PrepPanel } from '@/components/event/prep-panel'
import { ProgramPanel } from '@/components/event/program-panel'
import { RosterEditor } from '@/components/event/roster-editor'
import { Badge } from '@/components/ui/badge'
import { formatEventDate } from '@/lib/format'
import { normalizeTimingLog } from '@/lib/ops/timing'
import { resolvePlan } from '@/lib/program/resolve'
import { currentAcademy } from '@/lib/session'
import { getRepository } from '@/lib/store'
import { EVENT_STATUS_LABEL } from '@/lib/types'

export const dynamic = 'force-dynamic'

/**
 * 행사 화면은 **차례 안내(hub)** 로 열린다.
 * 갈 곳을 열한 개 늘어놓는 대신, 지금 하실 것 하나를 크게 보여 준다.
 */
const PANELS = ['roster', 'program', 'plan', 'prep'] as const
type Panel = (typeof PANELS)[number]

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
  const tab: Panel | 'hub' = PANELS.includes(searchParams.tab as Panel)
    ? (searchParams.tab as Panel)
    : 'hub'
  /**
   * 어디까지 하셨는지.
   *
   * 곁들이는 "설정을 저장하셨는가 · 회신이 왔는가 · 사진이 붙었는가" 처럼
   * **실제로 남은 자국**으로만 본다. 열어만 보신 것을 했다고 하면 안 된다.
   */
  const flow = {
    hasStudents: students.length > 0,
    hasProgram: event.program_source !== null,
    hasPrint: event.status === 'published' || event.design_template !== null,
    hasInvite: rsvps.length > 0,
    hasStage: event.stage_prefs !== null,
    hasVideo: event.video_prefs !== null || event.video_url !== null,
    hasPhotos: students.some((s) => s.photo_asset_id || (s.photo_asset_ids?.length ?? 0) > 0),
    hasLive: event.live_state !== null,
  }

  return (
    <AppShell academyName={academy.name} eventId={event.id}>
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
        </div>
      </div>

      {tab === 'hub' ? (
        <EventHub eventId={event.id} state={flow} />
      ) : (
        <>
          <ScreenHeader step={tab} eventId={event.id} state={flow} />

          {tab === 'roster' && (
            <RosterEditor
              eventId={event.id}
              students={students}
              pastEvents={pastEvents}
              assets={academy.assets ?? []}
              timings={normalizeTimingLog(academy.timing_log)}
              hasProgram={flow.hasProgram}
            />
          )}
          {tab === 'program' && <ProgramPanel event={event} students={students} hasPrint={flow.hasPrint} />}
          {tab === 'plan' && <PlanPanel academy={academy} event={event} plan={plan} rsvps={rsvps} />}
          {tab === 'prep' && <PrepPanel academy={academy} event={event} plan={plan} />}
        </>
      )}
    </AppShell>
  )
}
