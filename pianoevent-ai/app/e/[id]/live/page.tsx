import { notFound } from 'next/navigation'
import { LiveBoard } from '@/components/ops/live-board'
import { getTheme, themeVars } from '@/lib/design/themes'
import { formatEventDate } from '@/lib/format'
import { normalizeLiveState } from '@/lib/ops/live'
import { resolvePlan } from '@/lib/program/resolve'
import { getRepository } from '@/lib/store'

export const dynamic = 'force-dynamic'

export async function generateMetadata({ params }: { params: { id: string } }) {
  const event = await getRepository().getEvent(params.id)
  return { title: event ? `${event.title} · 진행 상황` : '진행 상황' }
}

/**
 * 따라보기 화면 — 대기실·접수처 스태프가 로그인 없이 여는 곳.
 *
 * 무대 옆에서 넘기면 몇 초 안에 이 화면도 따라 넘어간다. 여기서는 넘길 수 없다 —
 * 두 사람이 서로 넘기면 순서가 엉킨다. 넘기는 사람은 한 명이어야 한다.
 */
export default async function PublicLivePage({ params }: { params: { id: string } }) {
  const repo = getRepository()
  const event = await repo.getEvent(params.id)
  if (!event) notFound()

  const [academy, students] = await Promise.all([repo.getAcademy(event.academy_id), repo.listStudents(event.id)])
  if (!academy) notFound()

  const { plan } = resolvePlan(students)
  const theme = getTheme(event.design_theme ?? academy.design_theme)

  return (
    <main
      style={{
        ...themeVars(theme),
        background: 'var(--d-paper)',
        color: 'var(--d-ink)',
        fontFamily: 'var(--d-body)',
        minHeight: '100vh',
      }}
    >
      <div style={{ margin: '0 auto', maxWidth: 560, padding: '24px 16px 48px' }}>
        <p style={{ fontSize: 12, letterSpacing: '0.24em', color: 'var(--d-muted)' }}>{academy.name}</p>
        <h1 style={{ marginTop: 6, fontFamily: 'var(--d-display)', fontSize: 24, fontWeight: 700 }}>{event.title}</h1>
        <p style={{ marginTop: 4, fontSize: 13, color: 'var(--d-muted)' }}>
          {formatEventDate(event.event_at)} · 진행 상황
        </p>
        <p
          style={{
            margin: '14px 0 18px',
            padding: '10px 12px',
            borderRadius: 10,
            background: 'var(--d-paper-alt)',
            fontSize: 13,
            lineHeight: 1.7,
          }}
        >
          무대 옆에서 순서를 넘기면 이 화면도 <strong>몇 초 안에</strong> 따라 바뀝니다. 이 창을 열어 두세요.
        </p>

        <LiveBoard
          event={event}
          plan={plan}
          initialState={normalizeLiveState(event.live_state, plan.items.length + plan.breaks.length)}
          canLead={false}
        />
      </div>
    </main>
  )
}
