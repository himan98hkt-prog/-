import { CalendarDays, MapPin, Plus, Users } from 'lucide-react'
import Link from 'next/link'
import { AppShell } from '@/components/app-shell'
import { EventImport } from '@/components/event/event-transfer'
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
          <CardContent className="py-16 text-center">
            <p className="text-sm text-muted-foreground">등록된 행사가 없습니다.</p>
            <Link href="/events/new" className="mt-4 inline-block">
              <Button variant="outline">첫 행사 만들기</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <ul className="grid gap-3">
          {events.map((event, index) => (
            <li key={event.id}>
              <Link href={`/events/${event.id}`}>
                <Card className="transition-shadow hover:shadow-md">
                  <CardContent className="flex flex-wrap items-center justify-between gap-4 py-4">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="truncate font-semibold">{event.title}</h2>
                        <Badge variant={event.status === 'draft' ? 'outline' : 'accent'}>
                          {EVENT_STATUS_LABEL[event.status]}
                        </Badge>
                        {event.theme && <Badge variant="default">{SEASON_LABEL[event.theme]}</Badge>}
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
      <div className="mt-6">
        <EventImport />
      </div>
    </AppShell>
  )
}
