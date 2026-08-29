import Link from 'next/link'
import { notFound } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { DesignImport, type PastDesign } from '@/components/design/design-import'
import { DesignStudio } from '@/components/design/design-studio'
import { ScreenHeader } from '@/components/flow/screen-header'
import { defaultCopy, type DesignCopy } from '@/lib/design/context'
import { getTemplate } from '@/lib/design/templates'
import { getTheme } from '@/lib/design/themes'
import { resolvePlan } from '@/lib/program/resolve'
import { currentAcademy } from '@/lib/session'
import { getRepository } from '@/lib/store'

export const dynamic = 'force-dynamic'
export const metadata = { title: '인쇄물 디자인' }

export default async function DesignPage({
  params,
  searchParams,
}: {
  params: { id: string }
  /** 종이에서 QR 을 비추고 오시면 그 장이 골라진 채로 열린다 */
  searchParams: { pick?: string }
}) {
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
    <AppShell academyName={academy.name} eventId={event.id}>
      <ScreenHeader
        step="print"
        eventId={event.id}
        eventTitle={event.title}
        state={{
          hasStudents: students.length > 0,
          hasProgram: event.program_source !== null,
          hasPrint: event.status === 'published' || event.design_template !== null,
        }}
      />

      <p className="mb-5 rounded-md border border-border bg-secondary px-3 py-2 text-sm no-print">
        여기서 고른 테마는 <strong>연주회장 스크린 화면</strong>에도 그대로 쓰입니다 —{' '}
        <Link href={`/events/${event.id}/stage`} className="font-medium underline underline-offset-4">
          무대 화면 열기
        </Link>
      </p>

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
        pickKind={searchParams.pick}
      />
    </AppShell>
  )
}
