import { CalendarDays, MapPin, Plus, Users } from 'lucide-react'
import Link from 'next/link'
import { AppShell } from '@/components/app-shell'
import { isDemoEvent } from '@/lib/events/demo-seed'
import { DemoEventButton } from '@/components/event/demo-event'
import { EventImport } from '@/components/event/event-transfer'
import { ProgressDots } from '@/components/flow/progress-dots'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { formatEventDate } from '@/lib/format'
import { currentAcademy } from '@/lib/session'
import { getRepository } from '@/lib/store'
import { EVENT_STATUS_LABEL, SEASON_LABEL } from '@/lib/types'

export const dynamic = 'force-dynamic'
export const metadata = { title: '행사' }

export default async function EventsPage() {
  const academy = await currentAcademy()
  const repo = getRepository()
  const events = await repo.listEvents(academy.id)
  const counts = await Promise.all(events.map(async (e) => (await repo.listStudents(e.id)).length))
  // 목록에서 여러 행사를 함께 보실 때 어느 것이 급한지 아셔야 한다
  const flows = events.map((event, index) => ({
    hasStudents: counts[index] > 0,
    hasProgram: event.program_source !== null,
    hasPrint: event.status === 'published' || event.design_template !== null,
  }))

  return (
    <AppShell academyName={academy.name}>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">행사</h1>
          <p className="mt-1 text-sm text-muted-foreground">정기 연주회와 시즌 특강을 한곳에서 관리합니다.</p>
        </div>
        <Link href="/events/new">
          <Button>
            <Plus className="h-4 w-4" aria-hidden />새 행사
          </Button>
        </Link>
      </div>

      {events.length === 0 ? (
        <Card>
          <CardContent className="grid justify-items-center gap-5 py-14 text-center">
            <div>
              <p className="text-sm text-muted-foreground">아직 행사가 없습니다.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                무엇을 해 주는 프로그램인지 <strong className="text-foreground">먼저 구경해 보세요.</strong>
              </p>
            </div>

            {/* 빈 화면에서 시작하면 무엇을 눌러도 볼 것이 없다 */}
            <DemoEventButton empty />

            <div className="border-t border-border pt-4">
              <p className="mb-2 text-xs text-muted-foreground">바로 시작하실 준비가 되셨으면</p>
              <Link href="/events/new">
                <Button variant="outline" size="sm">
                  첫 행사 만들기
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      ) : (
        <ul className="stagger grid gap-3">
          {events.map((event, index) => (
            <li key={event.id}>
              <Link href={`/events/${event.id}`}>
                <Card interactive className="press">
                  <CardContent className="flex flex-wrap items-center justify-between gap-4 py-4">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="truncate font-semibold">{event.title}</h2>
                        <Badge variant={event.status === 'draft' ? 'outline' : 'accent'}>
                          {EVENT_STATUS_LABEL[event.status]}
                        </Badge>
                        {event.theme && <Badge variant="default">{SEASON_LABEL[event.theme]}</Badge>}
                        {/* 진짜 행사와 섞이면 안 된다. 목록에서 한눈에 갈라져 보여야 한다 */}
                        {isDemoEvent(event.title) && <Badge variant="outline">구경용</Badge>}
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
                        <span className="flex items-center gap-1.5">
                          <Users className="h-3.5 w-3.5" aria-hidden />
                          연주자 {counts[index]}명
                        </span>
                        <ProgressDots state={flows[index]} />
                      </div>
                    </div>
                    <span className="text-sm text-muted-foreground">열기 →</span>
                  </CardContent>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {/* 다른 컴퓨터에서 하시던 행사를 그대로 여실 수 있게 */}
      <div className="mt-6 grid gap-4">
        <EventImport />
        {events.length > 0 && (
          <div className="rounded-lg border border-border bg-card p-4">
            <DemoEventButton />
          </div>
        )}
      </div>
    </AppShell>
  )
}
