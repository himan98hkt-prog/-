import { LogoSlot } from '@/components/design/logo'
import { OrnamentDivider, TrebleClef } from '@/components/design/ornaments'
import { Sheet, type as T } from '@/components/design/sheet'
import { dateParts } from '@/components/design/templates/posters'
import type { DesignContext } from '@/lib/design/context'
import { formatDuration, formatWallClock } from '@/lib/format'
import { STAGE_LABEL } from '@/lib/types'

/** 관객에게 나눠 주는 순서지의 표지 */
export function ProgramCover({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy, plan } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait">
      <div
        style={{
          height: '100%',
          padding: '110px 80px 76px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
        }}
      >
        <LogoSlot ctx={ctx} />
        <p style={{ ...T.label(11), marginTop: 16 }}>{academy.name}</p>
        <p style={{ marginTop: 8, fontSize: 13, letterSpacing: '0.2em', color: 'var(--d-muted)' }}>{copy.subtitle}</p>

        <h1 style={{ ...T.display(46), marginTop: 40 }}>{event.title}</h1>

        <div style={{ marginTop: 26 }}>
          <OrnamentDivider id={theme.ornament} width={220} />
        </div>

        <div style={{ marginTop: 46 }}>
          <TrebleClef size={40} opacity={0.9} />
        </div>

        <p style={{ marginTop: 46, fontSize: 16, fontFamily: 'var(--d-display)' }}>
          {d.year}년 {d.month}월 {d.day}일 {d.weekday}요일 {d.time}
        </p>
        {event.venue && <p style={{ marginTop: 8, fontSize: 15, color: 'var(--d-muted)' }}>{event.venue}</p>}

        {event.greeting && (
          <p style={{ marginTop: 42, maxWidth: 440, ...T.body(14), whiteSpace: 'pre-line' }}>{event.greeting}</p>
        )}

        <div style={{ marginTop: 'auto', fontSize: 11.5, color: 'var(--d-muted)' }}>
          <p>연주자 {plan.items.length}명 · 예상 소요 {formatDuration(plan.total_sec)}</p>
          <p style={{ marginTop: 6 }}>{copy.host}</p>
        </div>
      </div>
    </Sheet>
  )
}

function ProgramList({ ctx, compact = false }: { ctx: DesignContext; compact?: boolean }) {
  const { event, plan } = ctx
  let lastStage: string | null = null
  const breaksByOrder = new Map(plan.breaks.map((b) => [b.after_order_no, b]))

  return (
    <ol style={{ listStyle: 'none', margin: 0, padding: 0 }}>
      {plan.items.map((item) => {
        const stageChanged = item.stage !== lastStage
        lastStage = item.stage
        const brk = breaksByOrder.get(item.order_no - 1)

        return (
          <li key={item.student.id}>
            {brk && (
              <div
                style={{
                  margin: '14px 0',
                  padding: '7px 0',
                  textAlign: 'center',
                  fontSize: 11.5,
                  letterSpacing: '0.2em',
                  color: 'var(--d-muted)',
                  borderTop: '0.6px solid var(--d-line)',
                  borderBottom: '0.6px solid var(--d-line)',
                }}
              >
                {brk.label} · {formatDuration(brk.duration_sec)}
              </div>
            )}

            {stageChanged && (
              <p
                style={{
                  marginTop: item.order_no === 1 ? 0 : 20,
                  marginBottom: 8,
                  fontSize: 11,
                  letterSpacing: '0.24em',
                  color: 'var(--d-accent)',
                  fontWeight: 700,
                }}
              >
                {STAGE_LABEL[item.stage]}
              </p>
            )}

            <div
              style={{
                display: 'flex',
                gap: 14,
                alignItems: 'baseline',
                padding: compact ? '6px 0' : '9px 0',
                borderBottom: '0.6px solid var(--d-line)',
              }}
            >
              <span
                style={{
                  width: 22,
                  fontSize: 12,
                  fontWeight: 700,
                  color: 'var(--d-accent)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {item.order_no}
              </span>
              <span style={{ flex: 1, minWidth: 0 }}>
                <span style={{ fontSize: compact ? 13 : 15, fontWeight: 600, fontFamily: 'var(--d-display)' }}>
                  {item.student.student_name}
                </span>
                <span style={{ fontSize: compact ? 12 : 13.5, marginLeft: 10 }}>{item.student.piece_title}</span>
                {item.student.composer && (
                  <span style={{ fontSize: 11.5, color: 'var(--d-muted)', marginLeft: 8 }}>
                    / {item.student.composer}
                  </span>
                )}
              </span>
              {!compact && (
                <span style={{ fontSize: 11, color: 'var(--d-muted)', fontVariantNumeric: 'tabular-nums' }}>
                  {formatWallClock(event.event_at, item.start_offset_sec)}
                </span>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

/** 순서지 내지 */
export function ProgramInner({ ctx }: { ctx: DesignContext }) {
  const { theme, event, copy, plan } = ctx

  return (
    <Sheet theme={theme} page="a4-portrait">
      <div style={{ height: '100%', padding: '70px 72px 56px', display: 'flex', flexDirection: 'column' }}>
        <header
          style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', marginBottom: 26 }}
        >
          <LogoSlot ctx={ctx} height={34} />
          <h2 style={{ ...T.display(28), marginTop: 12 }}>연주 순서</h2>
          <p style={{ marginTop: 8, fontSize: 12, color: 'var(--d-muted)' }}>
            {event.title} · 연주자 {plan.items.length}명
          </p>
          <div style={{ marginTop: 14, display: 'flex', justifyContent: 'center' }}>
            <OrnamentDivider id={theme.ornament} width={170} />
          </div>
        </header>

        <div style={{ flex: 1, overflow: 'hidden' }}>
          <ProgramList ctx={ctx} />
        </div>

        <footer style={{ marginTop: 20, textAlign: 'center', fontSize: 11, color: 'var(--d-muted)' }}>
          {copy.footnote}
        </footer>
      </div>
    </Sheet>
  )
}

/** A4 가로를 반으로 접는 4면 구성 — 왼쪽 뒷면, 오른쪽 표지 */
export function ProgramBifold({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy, plan } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-landscape" decorated={false}>
      <div style={{ height: '100%', display: 'grid', gridTemplateColumns: '1fr 1px 1fr' }}>
        {/* 접었을 때 뒷면 — 순서 요약 */}
        <section style={{ padding: '54px 46px', display: 'flex', flexDirection: 'column' }}>
          <h2 style={{ ...T.display(20), textAlign: 'center' }}>연주 순서</h2>
          <div style={{ marginTop: 14, flex: 1, overflow: 'hidden' }}>
            <ProgramList ctx={ctx} compact />
          </div>
          <p style={{ marginTop: 14, fontSize: 10, color: 'var(--d-muted)', textAlign: 'center' }}>{copy.footnote}</p>
        </section>

        <div style={{ borderLeft: '1px dashed var(--d-line)' }} />

        {/* 접었을 때 표지 */}
        <section
          style={{
            padding: '70px 52px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center',
            background: 'var(--d-paper-alt)',
          }}
        >
          <LogoSlot ctx={ctx} height={46} />
          <p style={{ ...T.label(10), marginTop: 14 }}>{academy.name}</p>
          <h1 style={{ ...T.display(32), marginTop: 22 }}>{event.title}</h1>
          <div style={{ marginTop: 18 }}>
            <OrnamentDivider id={theme.ornament} width={160} />
          </div>
          <div style={{ marginTop: 34 }}>
            <TrebleClef size={30} opacity={0.85} />
          </div>
          <p style={{ marginTop: 34, fontSize: 14, fontFamily: 'var(--d-display)' }}>
            {d.year}. {d.month}. {d.day} ({d.weekday}) {d.time}
          </p>
          {event.venue && <p style={{ marginTop: 6, fontSize: 13, color: 'var(--d-muted)' }}>{event.venue}</p>}
          <p style={{ marginTop: 'auto', fontSize: 10.5, color: 'var(--d-muted)' }}>
            연주자 {plan.items.length}명 · {formatDuration(plan.total_sec)}
          </p>
        </section>
      </div>
    </Sheet>
  )
}
