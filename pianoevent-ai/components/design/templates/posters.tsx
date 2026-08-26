import { LogoSlot } from '@/components/design/logo'
import { OrnamentDivider, TrebleClef } from '@/components/design/ornaments'
import { Sheet, type as T } from '@/components/design/sheet'
import type { DesignContext } from '@/lib/design/context'
import { formatEventDate, formatShortDate, formatWallClock } from '@/lib/format'

const WEEKDAY = ['일', '월', '화', '수', '목', '금', '토']

function dateParts(iso: string) {
  const short = formatShortDate(iso) // 2026.09.16
  const [year, month, day] = short.split('.')
  const full = formatEventDate(iso) // 2026년 9월 16일 (수) 오후 3:00
  const weekday = full.match(/\(([^)]+)\)/)?.[1] ?? WEEKDAY[new Date(iso).getDay()]
  const time = full.split(') ')[1] ?? ''
  return { year, month, day, weekday, time, full }
}

/** 가운데 정렬 클래식 포스터 */
export function PosterClassic({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy, plan } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait">
      <div
        style={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          padding: '86px 84px 68px',
        }}
      >
        <LogoSlot ctx={ctx} />

        <p style={{ ...T.label(12), marginTop: 18, marginBottom: 18 }}>{academy.name}</p>

        <TrebleClef size={30} opacity={0.9} />

        <h1 style={{ ...T.display(52), marginTop: 26 }}>{event.title}</h1>
        {copy.subtitle && (
          <p style={{ marginTop: 14, fontSize: 17, letterSpacing: '0.18em', color: 'var(--d-muted)' }}>
            {copy.subtitle}
          </p>
        )}

        <div style={{ marginTop: 30 }}>
          <OrnamentDivider id={theme.ornament} width={240} />
        </div>

        <div style={{ marginTop: 44, display: 'flex', alignItems: 'flex-end', gap: 22 }}>
          <div style={{ ...T.display(84, 700), color: 'var(--d-accent)' }}>{d.month}</div>
          <div style={{ width: 1, height: 74, background: 'var(--d-line)' }} />
          <div style={{ ...T.display(84, 700), color: 'var(--d-accent)' }}>{d.day}</div>
        </div>
        <p style={{ marginTop: 10, fontSize: 15, letterSpacing: '0.24em', color: 'var(--d-muted)' }}>
          {d.year} · {d.weekday}요일 {d.time}
        </p>

        {event.venue && (
          <p style={{ marginTop: 26, fontSize: 19, fontFamily: 'var(--d-display)' }}>{event.venue}</p>
        )}

        {event.greeting && (
          <p
            style={{
              marginTop: 36,
              maxWidth: 460,
              ...T.body(14),
              whiteSpace: 'pre-line',
            }}
          >
            {event.greeting}
          </p>
        )}

        {/* 아래 절반이 비지 않도록 출연 정보와 안내를 채운다 */}
        <div style={{ marginTop: 'auto', width: '100%', paddingTop: 40 }}>
          {plan.items.length > 0 && (
            <p style={{ marginBottom: 18, fontSize: 13, letterSpacing: '0.06em', color: 'var(--d-muted)' }}>
              {plan.items
                .slice(0, 14)
                .map((item) => item.student.student_name)
                .join(' · ')}
              {plan.items.length > 14 ? ' 외' : ''}
            </p>
          )}
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 18 }}>
            <OrnamentDivider id={theme.ornament} width={160} />
          </div>
          <p style={{ fontSize: 11.5, color: 'var(--d-muted)', marginBottom: 16 }}>{copy.footnote}</p>
          <div style={{ height: 1, background: 'var(--d-line)', marginBottom: 14 }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--d-muted)' }}>
            <span>{copy.host}</span>
            <span>{copy.contact}</span>
          </div>
        </div>
      </div>
    </Sheet>
  )
}

/** 큰 날짜와 비대칭 여백의 편집형 포스터 */
export function PosterModern({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div
          style={{
            background: 'var(--d-band)',
            color: 'var(--d-band-ink)',
            padding: '30px 64px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
          }}
        >
          <span style={{ fontSize: 13, letterSpacing: '0.3em' }}>{academy.name}</span>
          <span style={{ fontSize: 13, letterSpacing: '0.2em' }}>{copy.subtitle}</span>
        </div>

        <div style={{ padding: '52px 64px 0', flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div style={{ marginBottom: 26 }}>
            <LogoSlot ctx={ctx} align="start" />
          </div>

          <h1 style={{ ...T.display(62), maxWidth: 560 }}>{event.title}</h1>

          <div style={{ marginTop: 46, display: 'flex', alignItems: 'flex-start', gap: 30 }}>
            <div style={{ ...T.display(150, 800), color: 'var(--d-accent)', lineHeight: 0.86 }}>{d.day}</div>
            <div style={{ paddingTop: 12 }}>
              <p style={{ ...T.display(24) }}>
                {d.year}. {d.month}
              </p>
              <p style={{ marginTop: 8, fontSize: 16, color: 'var(--d-muted)' }}>
                {d.weekday}요일 {d.time}
              </p>
              {event.venue && <p style={{ marginTop: 18, fontSize: 18 }}>{event.venue}</p>}
            </div>
          </div>

          <div style={{ marginTop: 44, height: 4, width: 120, background: 'var(--d-accent)' }} />

          {event.greeting && (
            <p style={{ marginTop: 34, maxWidth: 520, ...T.body(15), whiteSpace: 'pre-line' }}>{event.greeting}</p>
          )}

          <div style={{ marginTop: 'auto', paddingBottom: 44 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
              <div style={{ fontSize: 12, color: 'var(--d-muted)', lineHeight: 1.8 }}>
                <div>{copy.host}</div>
                {copy.contact && <div>{copy.contact}</div>}
              </div>
              <TrebleClef size={26} opacity={0.75} />
            </div>
          </div>
        </div>
      </div>
    </Sheet>
  )
}

/** 포스터 한 장에 출연진까지 담는 안내형 */
export function PosterProgram({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, plan, copy } = ctx
  const d = dateParts(event.event_at)
  const items = plan.items
  const half = Math.ceil(items.length / 2)
  const columns = [items.slice(0, half), items.slice(half)]

  return (
    <Sheet theme={theme} page="a4-portrait">
      <div style={{ height: '100%', padding: '78px 64px 60px', display: 'flex', flexDirection: 'column' }}>
        <header style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
          <LogoSlot ctx={ctx} height={44} />
          <p style={{ ...T.label(11), marginTop: 12, marginBottom: 14 }}>{academy.name}</p>
          <h1 style={{ ...T.display(44) }}>{event.title}</h1>
          <p style={{ marginTop: 12, fontSize: 14, letterSpacing: '0.14em', color: 'var(--d-muted)' }}>
            {d.year}. {d.month}. {d.day} ({d.weekday}) {d.time}
            {event.venue ? ` · ${event.venue}` : ''}
          </p>
          <div style={{ marginTop: 20, display: 'flex', justifyContent: 'center' }}>
            <OrnamentDivider id={theme.ornament} width={200} />
          </div>
        </header>

        <div style={{ marginTop: 34, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 34px', flex: 1 }}>
          {columns.map((column, index) => (
            <ol key={index} style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {column.map((item) => (
                <li
                  key={item.student.id}
                  style={{
                    display: 'flex',
                    gap: 10,
                    padding: '7px 0',
                    borderBottom: '0.6px solid var(--d-line)',
                    alignItems: 'baseline',
                  }}
                >
                  <span
                    style={{
                      width: 20,
                      fontSize: 11,
                      fontVariantNumeric: 'tabular-nums',
                      color: 'var(--d-accent)',
                      fontWeight: 700,
                    }}
                  >
                    {item.order_no}
                  </span>
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{item.student.student_name}</span>
                    <span style={{ fontSize: 12, color: 'var(--d-muted)', marginLeft: 7 }}>
                      {item.student.piece_title}
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          ))}
        </div>

        <footer style={{ marginTop: 22, textAlign: 'center' }}>
          <p style={{ fontSize: 11.5, color: 'var(--d-muted)' }}>{copy.footnote}</p>
          <p style={{ marginTop: 10, fontSize: 11, color: 'var(--d-muted)' }}>
            {copy.host}
            {copy.contact ? ` · ${copy.contact}` : ''}
          </p>
        </footer>
      </div>
    </Sheet>
  )
}

export { dateParts, formatWallClock }
