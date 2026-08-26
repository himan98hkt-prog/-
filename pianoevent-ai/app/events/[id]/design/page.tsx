import Link from 'next/link'
import { notFound } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { DesignStudio } from '@/components/design/design-studio'
import { defaultCopy, type DesignCopy } from '@/lib/design/context'
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

  const students = await repo.listStudents(event.id)
  const { plan } = resolvePlan(students)
  const base = defaultCopy(academy, event)
  const copy: DesignCopy = { ...base, ...(event.design_copy ?? {}) }

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
      </div>

      <DesignStudio
        academy={academy}
        event={event}
        plan={plan}
        inviteUrl={`/e/${event.id}`}
        initialCopy={copy}
      />
    </AppShell>
  )
}
