import { CalendarDays, MapPin } from 'lucide-react'
import { notFound } from 'next/navigation'
import { LogoSlot } from '@/components/design/logo'
import { OrnamentBackdrop, OrnamentDivider, TrebleClef } from '@/components/design/ornaments'
import { RsvpForm } from '@/components/rsvp/rsvp-form'
import { defaultCopy } from '@/lib/design/context'
import { getTheme, themeVars } from '@/lib/design/themes'
import { formatEventDate } from '@/lib/format'
import { resolvePlan } from '@/lib/program/resolve'
import { getRepository, summarizeRsvps } from '@/lib/store'

export const dynamic = 'force-dynamic'

export async function generateMetadata({ params }: { params: { id: string } }) {
  const event = await getRepository().getEvent(params.id)
  if (!event) return { title: '초대장' }
  return {
    title: event.title,
    description: `${formatEventDate(event.event_at)}${event.venue ? ` · ${event.venue}` : ''}`,
    openGraph: { title: event.title, description: event.venue || '' },
  }
}

/**
 * 학부모가 카카오톡 링크로 여는 공개 초대장.
 * 원장이 고른 인쇄물 테마를 그대로 입어 종이 초대장과 같은 인상을 준다.
 */
export default async function InvitePage({ params }: { params: { id: string } }) {
  const repo = getRepository()
  const event = await repo.getEvent(params.id)
  if (!event) notFound()

  const [academy, students, rsvps] = await Promise.all([
    repo.getAcademy(event.academy_id),
    repo.listStudents(event.id),
    repo.listRsvps(event.id),
  ])
  if (!academy) notFound()

  const { plan, saved } = resolvePlan(students)
  const summary = summarizeRsvps(rsvps)
  const theme = getTheme(event.design_theme ?? academy.design_theme)
  const copy = { ...defaultCopy(academy, event), ...(event.design_copy ?? {}) }
  const photoUrl = event.photo_url ?? academy.photo_url
  const ctx = {
    theme,
    academy,
    event,
    plan,
    copy,
    inviteUrl: `/e/${event.id}`,
    logoUrl: academy.logo_url,
    photoUrl,
    placeholder: false,
  }

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
      <div style={{ margin: '0 auto', maxWidth: 480, position: 'relative', paddingBottom: 56 }}>
        <OrnamentBackdrop id={theme.ornament} />

        {/* 표지 */}
        <section style={{ position: 'relative', padding: '52px 30px 40px', textAlign: 'center' }}>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <LogoSlot ctx={ctx} height={58} />
          </div>

          <p
            style={{
              marginTop: 18,
              fontSize: 12,
              letterSpacing: '0.32em',
              color: 'var(--d-muted)',
            }}
          >
            {academy.name}
          </p>
          <p style={{ marginTop: 8, fontSize: 13, letterSpacing: '0.2em', color: 'var(--d-accent)' }}>
            {copy.subtitle}
          </p>

          <h1
            style={{
              marginTop: 20,
              fontFamily: 'var(--d-display)',
              fontSize: 34,
              fontWeight: 700,
              lineHeight: 1.28,
              letterSpacing: '-0.01em',
            }}
          >
            {event.title}
          </h1>

          <div style={{ marginTop: 20, display: 'flex', justifyContent: 'center' }}>
            <OrnamentDivider id={theme.ornament} width={200} />
          </div>

          {photoUrl ? (
            <div
              style={{
                marginTop: 26,
                borderRadius:
                  theme.photo.shape === 'circle'
                    ? '50%'
                    : theme.photo.shape === 'arch'
                      ? '150px 150px 14px 14px'
                      : theme.photo.shape === 'rounded'
                        ? 18
                        : 0,
                overflow: 'hidden',
                aspectRatio: theme.photo.shape === 'circle' ? '1 / 1' : '4 / 3',
                width: theme.photo.shape === 'circle' ? 240 : '100%',
                marginInline: 'auto',
              }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={photoUrl}
                alt={`${academy.name} 사진`}
                style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
              />
            </div>
          ) : (
            <div style={{ marginTop: 26, display: 'flex', justifyContent: 'center' }}>
              <TrebleClef size={34} opacity={0.9} />
            </div>
          )}

          <div style={{ marginTop: 28, display: 'grid', gap: 8, fontSize: 15 }}>
            <p style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
              <CalendarDays size={15} aria-hidden style={{ color: 'var(--d-accent)' }} />
              {formatEventDate(event.event_at)}
            </p>
            {event.venue && (
              <p
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  color: 'var(--d-muted)',
                }}
              >
                <MapPin size={15} aria-hidden style={{ color: 'var(--d-accent)' }} />
                {event.venue}
              </p>
            )}
          </div>
        </section>

        {/* 인사말 */}
        {event.greeting && (
          <section style={{ padding: '0 34px 40px', textAlign: 'center' }}>
            <p
              style={{
                whiteSpace: 'pre-line',
                fontSize: 15,
                lineHeight: 2,
                color: 'var(--d-muted)',
                fontFamily: 'var(--d-display)',
              }}
            >
              {event.greeting}
            </p>
          </section>
        )}

        {/* 연주 순서 */}
        {saved && plan.items.length > 0 && (
          <section
            style={{
              margin: '0 22px 40px',
              padding: '30px 24px',
              background: 'var(--d-paper-alt)',
              borderRadius: 16,
            }}
          >
            <h2
              style={{
                textAlign: 'center',
                fontFamily: 'var(--d-display)',
                fontSize: 19,
                letterSpacing: '0.08em',
              }}
            >
              연주 순서
            </h2>
            <div style={{ marginTop: 12, display: 'flex', justifyContent: 'center' }}>
              <OrnamentDivider id={theme.ornament} width={140} />
            </div>

            <ol style={{ marginTop: 22, listStyle: 'none', padding: 0, display: 'grid', gap: 14 }}>
              {plan.items.map((item) => (
                <li key={item.student.id} style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
                  <span
                    style={{
                      width: 22,
                      fontSize: 12,
                      fontWeight: 700,
                      color: 'var(--d-accent)',
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    {String(item.order_no).padStart(2, '0')}
                  </span>
                  <span style={{ minWidth: 0 }}>
                    <span style={{ fontSize: 15, fontFamily: 'var(--d-display)' }}>
                      {item.student.student_name}
                    </span>
                    <span style={{ marginLeft: 10, fontSize: 14 }}>{item.student.piece_title}</span>
                    {item.student.composer && (
                      <span style={{ display: 'block', marginTop: 2, fontSize: 12, color: 'var(--d-muted)' }}>
                        {item.student.composer}
                      </span>
                    )}
                  </span>
                </li>
              ))}
            </ol>
          </section>
        )}

        {/* 참석 회신 */}
        <section style={{ padding: '0 22px 40px' }}>
          <div
            style={{
              padding: '30px 24px',
              border: '1px solid var(--d-line)',
              borderRadius: 16,
              background: 'var(--d-paper)',
            }}
          >
            <h2 style={{ textAlign: 'center', fontFamily: 'var(--d-display)', fontSize: 19 }}>
              참석 여부를 알려 주세요
            </h2>
            <p style={{ marginTop: 8, textAlign: 'center', fontSize: 13.5, color: 'var(--d-muted)' }}>
              좌석 준비를 위해 참석 인원을 미리 확인하고 있습니다.
            </p>
            <div style={{ marginTop: 22 }}>
              <RsvpForm eventId={event.id} />
            </div>
          </div>
        </section>

        {/* 응원 메시지 */}
        {summary.messages.length > 0 && (
          <section style={{ padding: '0 22px 40px' }}>
            <h2 style={{ textAlign: 'center', fontFamily: 'var(--d-display)', fontSize: 17 }}>
              응원 메시지 {summary.messages.length}개
            </h2>
            <ul style={{ marginTop: 18, listStyle: 'none', padding: 0, display: 'grid', gap: 10 }}>
              {summary.messages.slice(0, 30).map((m, index) => (
                <li
                  key={`${m.created_at}-${index}`}
                  style={{
                    padding: '14px 16px',
                    borderRadius: 12,
                    background: 'var(--d-paper-alt)',
                    fontSize: 14,
                    lineHeight: 1.7,
                  }}
                >
                  <p>{m.message}</p>
                  <p style={{ marginTop: 6, fontSize: 12, color: 'var(--d-muted)' }}>— {m.name}</p>
                </li>
              ))}
            </ul>
          </section>
        )}

        <footer style={{ padding: '0 22px', textAlign: 'center' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 14 }}>
            <OrnamentDivider id={theme.ornament} width={120} />
          </div>
          <p style={{ fontSize: 12, color: 'var(--d-muted)', lineHeight: 1.9 }}>
            {copy.footnote}
            <br />
            {academy.name}
            {academy.director_name ? ` · 원장 ${academy.director_name}` : ''}
          </p>
        </footer>
      </div>
    </main>
  )
}
