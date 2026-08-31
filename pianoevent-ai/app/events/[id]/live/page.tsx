import Link from 'next/link'
import { notFound } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { ScreenHeader } from '@/components/flow/screen-header'
import { LiveBoard } from '@/components/ops/live-board'
import { studentPhotos } from '@/lib/assets'
import { formatEventDate } from '@/lib/format'
import { normalizeLiveState } from '@/lib/ops/live'
import { resolvePlan } from '@/lib/program/resolve'
import { currentAcademy } from '@/lib/session'
import { getRepository } from '@/lib/store'

export const dynamic = 'force-dynamic'
export const metadata = { title: '당일 진행' }

/**
 * 당일 진행 — 무대 옆에 선 사람의 휴대폰 화면.
 * "지금 몇 번째, 다음은 누구" 만 크게. 종이 순서표를 손가락으로 짚지 않아도 된다.
 */
export default async function LivePage({ params }: { params: { id: string } }) {
  const repo = getRepository()
  const [academy, event] = await Promise.all([currentAcademy(), repo.getEvent(params.id)])
  if (!event) notFound()

  const students = await repo.listStudents(event.id)
  const { plan } = resolvePlan(students)
  // 대기실 강사는 이름만 보고 아이를 데려간다 — 얼굴이 함께 있어야 잘못 짚지 않는다
  const photos = studentPhotos(academy.assets ?? [], students)

  return (
    <AppShell academyName={academy.name} eventId={event.id}>
      <ScreenHeader
        step="live"
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
          {formatEventDate(event.event_at)} · 순서 {plan.items.length}개 — 이 화면을 휴대폰으로 여세요.
        </p>
        <p className="mt-2 rounded-md border border-border bg-secondary px-3 py-2 text-sm">
          개회할 때 <strong>[개회 · 시작]</strong> 을 한 번 누르고, 한 곡이 끝날 때마다{' '}
          <strong>[다음 순서로]</strong> 를 누르세요. 예정보다 몇 분 밀렸는지 함께 보여 드립니다 —
          10분 넘게 밀리면 화면이 붉어집니다. 그때 사회자 멘트를 줄이시면 됩니다.
        </p>
      </div>

      <LiveBoard
        event={event}
        plan={plan}
        students={students}
        photos={photos}
        initialState={normalizeLiveState(event.live_state, plan.items.length + plan.breaks.length)}
      />

      <div className="mt-5 grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
        <p className="rounded-md border border-border px-3 py-2.5">
          <strong className="text-foreground">휴대폰으로 여는 법</strong> — 이 주소를 원장님 휴대폰으로 보내
          열어 두시면 됩니다. 화면이 꺼지지 않도록 붙잡아 둡니다(브라우저가 허락하는 경우).
        </p>
        <p className="rounded-md border border-border px-3 py-2.5">
          <strong className="text-foreground">인터넷이 끊겨도</strong> 넘기기는 그대로 됩니다. 진행 상태는 그
          휴대폰에 담기므로 학생 정보가 밖으로 나가지 않습니다.
        </p>
        <p className="rounded-md border border-border px-3 py-2.5">
          <strong className="text-foreground">스태프와 함께 보기</strong> — 아래 <strong>함께 보기</strong> 를 켜고
          대기실·접수처에는 <code>/e/{event.id}/live</code> 를 열어 두시면, 무대 옆에서 넘길 때마다 그 화면들도
          따라 넘어갑니다.
        </p>
        <p className="rounded-md border border-border px-3 py-2.5">
          <strong className="text-foreground">한 번 돌려 보면 다음이 정확해집니다</strong> — 넘긴 시각이 쌓여
          곡마다 <strong>실제로 몇 분 걸렸는지</strong> 남습니다. 리허설에서 한 번 돌려 두고 명단에 반영하시면
          다음 연주회 종료 시각이 이 학원 아이들에 맞게 나옵니다.
        </p>
      </div>
    </AppShell>
  )
}
