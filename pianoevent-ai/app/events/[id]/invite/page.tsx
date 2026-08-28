import { ExternalLink } from 'lucide-react'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { ScreenHeader } from '@/components/flow/screen-header'
import { RsvpDashboard } from '@/components/rsvp/rsvp-dashboard'
import { SharePanel } from '@/components/rsvp/share-panel'
import { PublishToggle } from '@/components/event/publish-toggle'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatEventDate } from '@/lib/format'
import { currentAcademy } from '@/lib/session'
import { getRepository, summarizeRsvps } from '@/lib/store'

export const dynamic = 'force-dynamic'
export const metadata = { title: '초대장 · 참석 집계' }

export default async function InviteAdminPage({ params }: { params: { id: string } }) {
  const repo = getRepository()
  const [academy, event] = await Promise.all([currentAcademy(), repo.getEvent(params.id)])
  if (!event) notFound()

  const [rsvps, students] = await Promise.all([repo.listRsvps(event.id), repo.listStudents(event.id)])

  return (
    <AppShell academyName={academy.name} eventId={event.id}>
      <ScreenHeader
        step="invite"
        eventId={event.id}
        eventTitle={event.title}
        state={{
          hasStudents: students.length > 0,
          hasProgram: event.program_source !== null,
          hasPrint: event.status === 'published' || event.design_template !== null,
        }}
      />

      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <div className="grid gap-5">
          <Card>
            <CardHeader>
              <CardTitle>링크 공유</CardTitle>
              <CardDescription>
                학부모는 로그인 없이 링크만으로 초대장을 열고 참석 여부를 회신합니다.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <SharePanel
                path={`/e/${event.id}`}
                title={`${academy.name} ${event.title}`}
                description={`${formatEventDate(event.event_at)}${event.venue ? ` · ${event.venue}` : ''}`}
              />
              <PublishToggle eventId={event.id} status={event.status} />
            </CardContent>
          </Card>

          <RsvpDashboard eventId={event.id} initialRsvps={rsvps} initialSummary={summarizeRsvps(rsvps)} />
        </div>

        <aside>
          <Card className="sticky top-20">
            <CardHeader>
              <CardTitle>초대장 미리보기</CardTitle>
              <CardDescription>학부모 휴대폰에서 보이는 화면입니다.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <div className="overflow-hidden rounded-lg border border-border">
                <iframe
                  src={`/e/${event.id}`}
                  title="초대장 미리보기"
                  className="h-[520px] w-full"
                  sandbox="allow-scripts allow-same-origin allow-forms"
                />
              </div>
              <Link href={`/e/${event.id}`} target="_blank">
                <Button variant="outline" size="sm" className="w-full">
                  <ExternalLink className="h-4 w-4" aria-hidden />새 창에서 열기
                </Button>
              </Link>
            </CardContent>
          </Card>
        </aside>
      </div>
    </AppShell>
  )
}
