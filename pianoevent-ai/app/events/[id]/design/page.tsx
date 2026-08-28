import Link from 'next/link'
import { notFound } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { DesignImport, type PastDesign } from '@/components/design/design-import'
import { DesignStudio } from '@/components/design/design-studio'
import { defaultCopy, type DesignCopy } from '@/lib/design/context'
import { getTemplate } from '@/lib/design/templates'
import { getTheme } from '@/lib/design/themes'
import { formatEventDate } from '@/lib/format'
import { resolvePlan } from '@/lib/program/resolve'
import { currentAcademy } from '@/lib/session'
import { getRepository } from '@/lib/store'

export const dynamic = 'force-dynamic'
export const metadata = { title: '인쇄물 디자인' }

export default async function DesignPage({ params }: { params: { id: string } }) {
  const repo = getRepository()
  const [academy, event] = await Promise.all([currentAcademy(), repo.getEvent(params.id)])
  if (!event) notFound()

  const [students, rsvps, siblings] = await Promise.all([
    repo.listStudents(event.id),
    repo.listRsvps(event.id),
    repo.listEvents(event.academy_id),
  ])
  const { plan } = resolvePlan(students)
  const base = defaultCopy(academy, event)
  const copy: DesignCopy = { ...base, ...(event.design_copy ?? {}) }

  // 디자인을 손봐 둔 지난 행사만 — 손대지 않은 행사를 가져와 봐야 기본값이다
  const past: PastDesign[] = siblings
    .filter((item) => item.id !== event.id && (item.design_theme || item.design_template))
    .slice(0, 12)
    .map((item) => ({
      id: item.id,
      title: item.title,
      summary: [
        item.design_theme ? getTheme(item.design_theme).name : null,
        item.design_template ? getTemplate(item.design_template).name : null,
      ]
        .filter(Boolean)
        .join(' · '),
    }))

  return (
    <AppShell academyName={academy.name}>
      <div className="mb-6">
        <Link href={`/events/${event.id}`} className="text-sm text-muted-foreground hover:text-foreground">
          ← {event.title}
        </Link>
        <h1 className="mt-2 text-2xl font-bold tracking-tight">인쇄물 디자인</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          포스터·순서지·입장권·상장까지 한 테마로 맞춥니다. {formatEventDate(event.event_at)}
        </p>
        <p className="mt-3 rounded-md border border-border bg-secondary px-3 py-2 text-sm">
          연주회장 스크린에 띄울 화면도 여기서 만든 테마 그대로 나옵니다 —{' '}
          <Link href={`/events/${event.id}/stage`} className="font-medium underline underline-offset-4">
            무대 화면 열기
          </Link>
        </p>
      </div>

      {past.length > 0 && (
        <div className="mb-5">
          <DesignImport eventId={event.id} past={past} />
        </div>
      )}

      <DesignStudio
        academy={academy}
        event={event}
        plan={plan}
        rsvps={rsvps}
        inviteUrl={`/e/${event.id}`}
        initialCopy={copy}
      />
    </AppShell>
  )
}
