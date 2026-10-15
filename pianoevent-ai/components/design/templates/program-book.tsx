import { LogoSlot } from '@/components/design/logo'
import { OrnamentDivider, TrebleClef } from '@/components/design/ornaments'
import { Sheet, type as T } from '@/components/design/sheet'
import { dateParts } from '@/components/design/templates/posters'
import type { DesignContext } from '@/lib/design/context'
import { formatDuration, formatWallClock } from '@/lib/format'
import { STAGE_LABEL } from '@/lib/types'

/**
 * 책자형·티켓형 인쇄물.
 *
 * 원장님들이 가장 많이 물으신 두 가지다.
 *   · "프로그램을 책자로 만들고 싶은데요" — A4 를 반 접으면 A5 책자가 된다.
 *     그러려면 지면을 **접는 자리에 맞춰** 짜야 한다. 아무 종이나 접으면 글이 접힘선에 물린다.
 *   · "입장권을 여러 장 뽑고 싶은데요" — 한 장에 여러 장을 앉히고 자를 선을 그어야 한다.
 *
 * 여기 있는 것은 전부 **집 프린터 한 대로** 끝나게 짰다. 인쇄소에 맡기실 때는
 * 인쇄물 화면의 [인쇄소용] 을 누르시면 재단선이 함께 나온다.
 */

/** 접는 자리 — 반으로 접는 책자에서 가운데를 알려 주는 옅은 점선 */
function FoldLine({ vertical = true }: { vertical?: boolean }) {
  return (
    <div
      aria-hidden
      style={{
        position: 'absolute',
        ...(vertical
          ? { left: '50%', top: 0, bottom: 0, borderLeft: '1px dashed var(--d-line)' }
          : { top: '50%', left: 0, right: 0, borderTop: '1px dashed var(--d-line)' }),
        opacity: 0.6,
      }}
    />
  )
}

/** 자르는 자리 — 여러 장이 한 종이에 있을 때 */
function CutLine() {
  return <div aria-hidden style={{ borderTop: '1px dashed var(--d-line)', margin: '0' }} />
}

/**
 * A5 책자 겉장 (A4 가로를 반 접습니다).
 * 왼쪽이 뒷면, 오른쪽이 앞면 — 접으면 앞면이 겉으로 온다.
 */
export function BookletCover({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-landscape">
      <div style={{ position: 'absolute', inset: 0, display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
        <FoldLine />

        {/* 뒷면 — 접었을 때 뒤로 간다. 문의와 안내를 여기 둔다 */}
        <div
          style={{
            padding: '64px 56px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'flex-end',
            gap: 14,
            background: 'var(--d-paper-alt)',
          }}
        >
          <OrnamentDivider id={theme.ornament} width={160} />
          {copy.footnote ? <p style={{ ...T.body(12) }}>{copy.footnote}</p> : null}
          {copy.contact ? (
            <p style={{ ...T.body(12), color: 'var(--d-ink)' }}>문의 · {copy.contact}</p>
          ) : null}
          <p style={{ ...T.label(9) }}>{copy.host || academy.name}</p>
        </div>

        {/* 앞면 */}
        <div
          style={{
            padding: '58px 54px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            textAlign: 'center',
            gap: 14,
          }}
        >
          <LogoSlot ctx={ctx} height={54} />
          <p style={{ ...T.label(10) }}>{academy.name}</p>
          <TrebleClef size={34} />
          <h1 style={{ ...T.display(34) }}>{event.title}</h1>
          {copy.subtitle ? <p style={{ ...T.body(13) }}>{copy.subtitle}</p> : null}
          <OrnamentDivider id={theme.ornament} width={190} />
          <p style={{ fontSize: 15, fontWeight: 600 }}>
            {d.year}. {d.month}. {d.day} ({d.weekday}) {d.time}
          </p>
          {event.venue ? <p style={{ ...T.body(12) }}>{event.venue}</p> : null}
        </div>
      </div>
    </Sheet>
  )
}

/**
 * A5 책자 속장 (A4 가로를 반 접습니다).
 * 왼쪽에 인사말, 오른쪽에 순서. 겉장과 등을 맞대어 인쇄하시면 책자가 된다.
 */
export function BookletInner({ ctx }: { ctx: DesignContext }) {
  const { theme, event, plan, copy } = ctx

  return (
    <Sheet theme={theme} page="a4-landscape">
      <div style={{ position: 'absolute', inset: 0, display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
        <FoldLine />

        <div style={{ padding: '52px 50px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p style={{ ...T.label(10), color: 'var(--d-accent)' }}>인사말</p>
          <OrnamentDivider id={theme.ornament} width={120} />
          <p style={{ ...T.body(12.5), whiteSpace: 'pre-line', color: 'var(--d-ink)' }}>
            {event.greeting || copy.subtitle || ''}
          </p>
        </div>

        <div style={{ padding: '52px 50px', display: 'flex', flexDirection: 'column' }}>
          <p style={{ ...T.label(10), color: 'var(--d-accent)' }}>연주 순서</p>
          <ol style={{ marginTop: 12, display: 'grid', gap: 7 }}>
            {plan.items.map((item) => (
              <li key={item.student.id} style={{ display: 'flex', gap: 10, alignItems: 'baseline' }}>
                <span
                  style={{
                    width: 20,
                    fontSize: 11,
                    fontWeight: 700,
                    color: 'var(--d-accent)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {item.order_no}
                </span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ fontSize: 12.5, fontWeight: 600 }}>{item.student.student_name}</span>
                  <span style={{ fontSize: 11.5, color: 'var(--d-muted)' }}> · {item.student.piece_title}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </Sheet>
  )
}

/** 곡목만 크게 — 어르신 손님이 많은 연주회에 (A5 한 장) */
export function ProgramLarge({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, plan } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false} flow>
      <div style={{ flex: 1, padding: '40px 40px 34px', display: 'flex', flexDirection: 'column' }}>
        <header style={{ textAlign: 'center', paddingBottom: 12, borderBottom: '2px solid var(--d-accent)' }}>
          <p style={{ ...T.label(9) }}>{academy.name}</p>
          <h1 style={{ ...T.display(22), marginTop: 6 }}>{event.title}</h1>
          <p style={{ marginTop: 5, fontSize: 11, color: 'var(--d-muted)' }}>
            {d.year}. {d.month}. {d.day} {d.time}
          </p>
        </header>
        <ol style={{ marginTop: 16, display: 'grid', gap: 11 }}>
          {plan.items.map((item) => (
            <li key={item.student.id} style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
              <span
                style={{
                  width: 26,
                  fontSize: 16,
                  fontWeight: 700,
                  color: 'var(--d-accent)',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {item.order_no}
              </span>
              <span style={{ flex: 1, minWidth: 0 }}>
                {/* 어르신이 읽으실 것이라 이름과 곡을 줄을 나눠 크게 */}
                <span style={{ display: 'block', fontSize: 17, fontWeight: 700 }}>{item.student.student_name}</span>
                <span style={{ display: 'block', fontSize: 14, color: 'var(--d-muted)' }}>
                  {item.student.piece_title}
                </span>
              </span>
            </li>
          ))}
        </ol>
      </div>
    </Sheet>
  )
}

/** 순서 + 메모 칸 — 관객이 아이마다 한 줄 적어 가시게 */
export function ProgramMemo({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, plan } = ctx

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false} flow>
      <div style={{ flex: 1, padding: '48px 52px 38px' }}>
        <header style={{ paddingBottom: 12, borderBottom: '2px solid var(--d-accent)' }}>
          <h1 style={{ ...T.display(24) }}>{event.title}</h1>
          <p style={{ marginTop: 5, fontSize: 11, color: 'var(--d-muted)' }}>
            {academy.name} · 마음에 남는 연주에 한 줄 적어 보세요
          </p>
        </header>
        <ol style={{ marginTop: 16, display: 'grid', gap: 4 }}>
          {plan.items.map((item) => (
            <li key={item.student.id} style={{ paddingBottom: 4 }}>
              <div style={{ display: 'flex', gap: 10, alignItems: 'baseline' }}>
                <span
                  style={{
                    width: 20,
                    fontSize: 11,
                    fontWeight: 700,
                    color: 'var(--d-accent)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {item.order_no}
                </span>
                <span style={{ fontSize: 12.5, fontWeight: 600 }}>{item.student.student_name}</span>
                <span style={{ fontSize: 11.5, color: 'var(--d-muted)' }}>{item.student.piece_title}</span>
              </div>
              <div style={{ marginTop: 3, marginLeft: 30, borderBottom: '1px dotted var(--d-line)', height: 17 }} />
            </li>
          ))}
        </ol>
      </div>
    </Sheet>
  )
}

/** 입장권 여러 장 — A4 한 장에 넉 장, 자르는 선 포함 */
export function TicketSheet({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', gridTemplateRows: 'repeat(4, 1fr)' }}>
        {[0, 1, 2, 3].map((n) => (
          <div key={n} style={{ display: 'flex', flexDirection: 'column' }}>
            {n > 0 && <CutLine />}
            <div
              style={{
                flex: 1,
                display: 'grid',
                gridTemplateColumns: '1fr 128px',
                alignItems: 'center',
                padding: '0 42px',
                gap: 16,
              }}
            >
              <div>
                <p style={{ ...T.label(8) }}>{copy.host || academy.name}</p>
                <h2 style={{ ...T.display(20), marginTop: 4 }}>{event.title}</h2>
                <p style={{ marginTop: 5, fontSize: 11, color: 'var(--d-muted)' }}>
                  {d.year}. {d.month}. {d.day} ({d.weekday}) {d.time}
                  {event.venue ? ` · ${event.venue}` : ''}
                </p>
              </div>
              {/* 오른쪽 반쪽은 받는 자리 — 접수처에서 떼어 두시면 참석 수가 셉니다 */}
              <div
                style={{
                  borderLeft: '1px dashed var(--d-line)',
                  height: '72%',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6,
                }}
              >
                <LogoSlot ctx={ctx} height={26} />
                <p style={{ ...T.label(7) }}>입장권</p>
                <p style={{ fontSize: 9, color: 'var(--d-muted)' }}>접수처 제출</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Sheet>
  )
}

/** 좌석권 — 자리 번호를 크게 적는 칸이 있는 입장권 (한 장에 여섯 장) */
export function SeatTicketSheet({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'grid',
          gridTemplateRows: 'repeat(6, 1fr)',
        }}
      >
        {[0, 1, 2, 3, 4, 5].map((n) => (
          <div key={n} style={{ display: 'flex', flexDirection: 'column' }}>
            {n > 0 && <CutLine />}
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 18, padding: '0 40px' }}>
              <div
                style={{
                  width: 78,
                  height: 78,
                  border: '2px solid var(--d-accent)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <span style={{ ...T.label(7) }}>좌석</span>
                {/* 손으로 적으실 칸 — 좌석을 미리 정하지 않는 학원이 훨씬 많다 */}
                <span style={{ fontSize: 26, color: 'var(--d-line)' }}>&nbsp;</span>
              </div>
              <div style={{ minWidth: 0 }}>
                <p style={{ ...T.label(8) }}>{academy.name}</p>
                <h2 style={{ ...T.display(17), marginTop: 3 }}>{event.title}</h2>
                <p style={{ marginTop: 4, fontSize: 10.5, color: 'var(--d-muted)' }}>
                  {d.month}. {d.day} ({d.weekday}) {d.time}
                  {event.venue ? ` · ${event.venue}` : ''}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Sheet>
  )
}

/** 연주자 이름표 — 대기실 의자에 붙이는 것 (한 장에 여덟 장) */
export function PerformerTags({ ctx }: { ctx: DesignContext }) {
  const { theme, plan } = ctx
  const perSheet = 8

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false} flow>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gridAutoRows: `${Math.round(1123 / (perSheet / 2))}px`,
        }}
      >
        {plan.items.map((item) => (
          <div
            key={item.student.id}
            className="print-avoid-break"
            style={{
              border: '1px dashed var(--d-line)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              gap: 6,
              padding: 16,
            }}
          >
            <span style={{ ...T.label(8), color: 'var(--d-accent)' }}>{item.order_no}번째</span>
            <span style={{ ...T.display(26) }}>{item.student.student_name}</span>
            <span style={{ fontSize: 12, color: 'var(--d-muted)' }}>{item.student.piece_title}</span>
          </div>
        ))}
      </div>
    </Sheet>
  )
}

/** 무대 순서 알림 카드 — 무대 옆 스태프가 손에 드는 것 (한 장에 여섯 장) */
export function StageCueCards({ ctx }: { ctx: DesignContext }) {
  const { theme, event, plan } = ctx

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false} flow>
      <div style={{ display: 'grid', gridAutoRows: `${Math.round(1123 / 6)}px` }}>
        {plan.items.map((item) => (
          <div
            key={item.student.id}
            className="print-avoid-break"
            style={{
              borderBottom: '1px dashed var(--d-line)',
              display: 'flex',
              alignItems: 'center',
              gap: 20,
              padding: '0 44px',
            }}
          >
            <span
              style={{
                ...T.display(40),
                color: 'var(--d-accent)',
                fontVariantNumeric: 'tabular-nums',
                width: 70,
                flexShrink: 0,
              }}
            >
              {item.order_no}
            </span>
            <span style={{ minWidth: 0, flex: 1 }}>
              <span style={{ display: 'block', ...T.display(22) }}>{item.student.student_name}</span>
              <span style={{ display: 'block', fontSize: 13, color: 'var(--d-muted)' }}>
                {item.student.piece_title}
                {item.student.composer ? ` / ${item.student.composer}` : ''}
              </span>
            </span>
            <span style={{ textAlign: 'right', flexShrink: 0 }}>
              <span style={{ display: 'block', fontSize: 15, fontWeight: 700 }}>
                {formatWallClock(event.event_at, item.start_offset_sec)}
              </span>
              <span style={{ display: 'block', fontSize: 11, color: 'var(--d-muted)' }}>
                {formatDuration(item.student.duration_sec ?? 0)}
              </span>
            </span>
          </div>
        ))}
      </div>
    </Sheet>
  )
}

/** 감사 인사 책갈피 — 돌아가시는 길에 나눠 드리는 것 (한 장에 넉 장) */
export function ThankYouBookmarks({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)' }}>
        {[0, 1, 2, 3].map((n) => (
          <div
            key={n}
            style={{
              borderLeft: n > 0 ? '1px dashed var(--d-line)' : undefined,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '46px 18px',
              textAlign: 'center',
              gap: 12,
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
              <LogoSlot ctx={ctx} height={32} />
              <TrebleClef size={22} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
              <p style={{ ...T.display(15) }}>{event.title}</p>
              <OrnamentDivider id={theme.ornament} width={70} />
              <p style={{ fontSize: 10, color: 'var(--d-muted)', lineHeight: 1.7 }}>
                함께해 주셔서 고맙습니다
              </p>
            </div>
            <p style={{ ...T.label(7) }}>
              {academy.name} · {d.year}. {d.month}
            </p>
          </div>
        ))}
      </div>
    </Sheet>
  )
}

/** 부별 표지 — 1부·2부 사이에 스크린 대신 세워 두는 판 */
export function StageDivider({ ctx }: { ctx: DesignContext }) {
  const { theme, event, plan } = ctx
  const stages = [...new Set(plan.items.map((item) => item.stage))]

  return (
    <Sheet theme={theme} page="a4-landscape">
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center',
          gap: 18,
          padding: 64,
        }}
      >
        <p style={{ ...T.label(11), color: 'var(--d-accent)' }}>{event.title}</p>
        <h1 style={{ ...T.display(64) }}>{stages[0] ? STAGE_LABEL[stages[0]] : '1부'}</h1>
        <OrnamentDivider id={theme.ornament} width={260} />
        <p style={{ ...T.body(14) }}>
          부가 바뀔 때 이 종이를 바꿔 세우시면 됩니다. 부마다 한 장씩 뽑아 두세요.
        </p>
      </div>
    </Sheet>
  )
}
