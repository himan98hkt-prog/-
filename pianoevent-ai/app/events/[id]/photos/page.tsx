import Link from 'next/link'
import { notFound } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { ScreenHeader } from '@/components/flow/screen-header'
import { PhotoCollect } from '@/components/event/photo-collect'
import { formatEventDate } from '@/lib/format'
import { currentAcademy } from '@/lib/session'
import { getRepository } from '@/lib/store'

export const dynamic = 'force-dynamic'
export const metadata = { title: '사진 모으기' }

/**
 * 당일 사진 모으기 — 리허설에서 찍은 사진을 그 자리에서 넣는다.
 * 그날 저녁 감동영상에 들어가야 값이 있는 사진이다.
 */
export default async function PhotosPage({ params }: { params: { id: string } }) {
  const repo = getRepository()
  const [academy, event] = await Promise.all([currentAcademy(), repo.getEvent(params.id)])
  if (!event) notFound()

  const students = await repo.listStudents(event.id)

  return (
    <AppShell academyName={academy.name} eventId={event.id}>
      <ScreenHeader
        step="photos"
        eventId={event.id}
        eventTitle={event.title}
        state={{
          hasStudents: students.length > 0,
          hasProgram: event.program_source !== null,
          hasPrint: event.status === 'published' || event.design_template !== null,
        }}
      />

      <div className="mb-5">
        <p className="mt-1 text-sm text-muted-foreground">
          {formatEventDate(event.event_at)} — 이 화면을 휴대폰으로 여세요.
        </p>
        <p className="mt-2 rounded-md border border-border bg-secondary px-3 py-2 text-sm">
          아이 이름 옆 <strong>사진기</strong>를 누르면 바로 찍어 넣고, <strong>앨범</strong>을 누르면 갤러리에서
          고릅니다. 리허설에서 찍은 사진이 <strong>그날 저녁 감동영상</strong>에 그대로 들어갑니다.
        </p>
      </div>

      {students.length === 0 ? (
        <p className="rounded-lg border border-border px-4 py-10 text-center text-sm text-muted-foreground">
          명단이 아직 없습니다. 명단을 먼저 넣어 주세요.
        </p>
      ) : (
        <PhotoCollect eventId={event.id} students={students} assets={academy.assets ?? []} />
      )}
    </AppShell>
  )
}
