import { LogoSlot } from '@/components/design/logo'
import { OrnamentDivider, TrebleClef } from '@/components/design/ornaments'
import { Sheet, type as T } from '@/components/design/sheet'
import { dateParts } from '@/components/design/templates/posters'
import type { DesignContext } from '@/lib/design/context'
import { formatWallClock } from '@/lib/format'
import { pieceCommentary } from '@/lib/program/script'

/**
 * 무대 배치도.
 *
 * 대관처에 "피아노를 어디 놓아 주세요"를 말로 설명하다 매번 어긋난다.
 * 종이 한 장으로 보내면 그 통화가 사라진다.
 */
export function StageMap({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event } = ctx
  const d = dateParts(event.event_at)

  const marker = (label: string, note: string, style: React.CSSProperties) => (
    <div
      style={{
        position: 'absolute',
        border: '1.5px solid var(--d-accent)',
        background: 'var(--d-accent-soft)',
        borderRadius: 6,
        padding: '7px 10px',
        textAlign: 'center',
        ...style,
      }}
    >
      <p style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--d-display)' }}>{label}</p>
      <p style={{ marginTop: 2, fontSize: 9, color: 'var(--d-muted)' }}>{note}</p>
    </div>
  )

  return (
    <Sheet theme={theme} page="a4-landscape" decorated={false}>
      <div style={{ flex: 1, padding: '42px 48px 34px', display: 'flex', flexDirection: 'column' }}>
        <header
          style={{
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'space-between',
            paddingBottom: 12,
            borderBottom: '2px solid var(--d-ink)',
          }}
        >
          <div>
            <p style={{ ...T.label(9.5) }}>{academy.name}</p>
            <h1 style={{ ...T.display(23), marginTop: 6 }}>{event.title} · 무대 배치도</h1>
          </div>
          <p style={{ fontSize: 11, color: 'var(--d-muted)', textAlign: 'right' }}>
            {d.year}. {d.month}. {d.day} ({d.weekday}) {d.time}
            {event.venue ? ` · ${event.venue}` : ''}
          </p>
        </header>

        <div
          style={{
            marginTop: 16,
            flex: 1,
            position: 'relative',
            border: '1px solid var(--d-line)',
            background: 'var(--d-paper-alt)',
          }}
        >
          {/* 무대 */}
          <div
            style={{
              position: 'absolute',
              insetInline: '6%',
              top: '6%',
              height: '46%',
              border: '2px solid var(--d-ink)',
              background: 'var(--d-paper)',
            }}
          >
            <p
              style={{
                position: 'absolute',
                top: 8,
                left: 12,
                ...T.label(9),
                color: 'var(--d-ink)',
              }}
            >
              무대
            </p>
            {marker('그랜드 피아노', '뚜껑 객석 방향', { left: '28%', top: '34%', width: 130 })}
            {marker('피아노 의자', '높이 조절 확인', { left: '25%', top: '74%', width: 96 })}
            {marker('사회자', '무대 왼쪽 앞', { left: '8%', top: '20%', width: 84 })}
            {marker('꽃·현수막', '무대 뒤 중앙', { right: '8%', top: '18%', width: 96 })}
            {marker('시상대', '시상 때만', { right: '10%', top: '66%', width: 84 })}
          </div>

          {/* 객석 */}
          <div
            style={{
              position: 'absolute',
              insetInline: '6%',
              bottom: '6%',
              height: '36%',
              border: '1px dashed var(--d-line)',
            }}
          >
            <p style={{ position: 'absolute', top: 8, left: 12, ...T.label(9) }}>객석</p>
            {marker('연주자석', '앞 두 줄 비움', { left: '30%', top: '38%', width: 110 })}
            {marker('접수처', '입구 옆', { left: '6%', bottom: '10%', width: 78 })}
            {marker('촬영 위치', '중앙 통로 뒤', { right: '8%', bottom: '10%', width: 92 })}
          </div>
        </div>

        <footer style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--d-line)', ...T.body(10) }}>
          대관처에 이 종이를 그대로 보내 주세요. 피아노 위치와 뚜껑 방향, 조명 범위만 맞으면 나머지는 당일에
          조정할 수 있습니다.
        </footer>
      </div>
    </Sheet>
  )
}

/** 무대 뒤에 거는 가로 현수막 시안 (3:1) */
export function BannerHorizontal({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="banner-wide">
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 40,
          padding: '52px 76px',
        }}
      >
        <div style={{ textAlign: 'center', flexShrink: 0 }}>
          <LogoSlot ctx={ctx} height={theme.logo.height + 16} />
          <p style={{ ...T.label(11), marginTop: 12 }}>{academy.name}</p>
        </div>

        <div style={{ flex: 1, textAlign: 'center', minWidth: 0 }}>
          <h1 style={{ ...T.display(62, 800) }}>{event.title}</h1>
          {copy.subtitle && (
            <p style={{ marginTop: 12, fontSize: 20, letterSpacing: '0.22em', color: 'var(--d-accent)' }}>
              {copy.subtitle}
            </p>
          )}
          <div style={{ marginTop: 18, display: 'flex', justifyContent: 'center' }}>
            <OrnamentDivider id={theme.ornament} width={260} />
          </div>
        </div>

        <div style={{ textAlign: 'center', flexShrink: 0 }}>
          <p style={{ ...T.display(50, 800), color: 'var(--d-accent)', lineHeight: 1 }}>
            {d.month}.{d.day}
          </p>
          <p style={{ marginTop: 10, fontSize: 15, letterSpacing: '0.18em', color: 'var(--d-muted)' }}>
            {d.year} {d.weekday}요일 {d.time}
          </p>
          {event.venue && <p style={{ marginTop: 10, fontSize: 17, fontFamily: 'var(--d-display)' }}>{event.venue}</p>}
        </div>
      </div>
    </Sheet>
  )
}

const SIGNS = [
  { big: '접 수 처', sub: '이름을 말씀해 주세요' },
  { big: '객석 입구', sub: '조용히 들어와 주세요' },
  { big: '대기실 →', sub: '연주자만 들어갑니다' },
  { big: '포토존', sub: '연주가 끝나고 이곳에서' },
]

/** 당일 길을 묻는 일을 없애는 안내 표지판 4매 */
export function Signage({ ctx }: { ctx: DesignContext }) {
  const { theme, academy } = ctx

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {SIGNS.map((sign, index) => (
          <div
            key={sign.big}
            className="print-avoid-break"
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              borderBottom: index < SIGNS.length - 1 ? '1px dashed var(--d-line)' : 'none',
              padding: '18px 40px',
            }}
          >
            <p style={{ ...T.display(46, 800), color: 'var(--d-accent)' }}>{sign.big}</p>
            <p style={{ marginTop: 10, fontSize: 15, color: 'var(--d-muted)' }}>{sign.sub}</p>
            <p style={{ marginTop: 12, ...T.label(8.5) }}>{academy.name}</p>
          </div>
        ))}
      </div>
    </Sheet>
  )
}

/** 연주자 소개 카드 — 로비 게시용, 한 장에 4매 */
export function PerformerCards({ ctx, limitSheets }: { ctx: DesignContext; limitSheets?: number }) {
  const { theme, academy, event, plan } = ctx
  const perSheet = 4
  const sheets = Math.max(1, Math.ceil(plan.items.length / perSheet))
  const shown = limitSheets ? Math.min(sheets, limitSheets) : sheets

  return (
    <>
      {Array.from({ length: shown }, (_, sheet) => (
        <Sheet key={sheet} theme={theme} page="a4-portrait" decorated={false}>
          <div style={{ flex: 1, display: 'grid', gridTemplateRows: 'repeat(4, 1fr)' }}>
            {plan.items.slice(sheet * perSheet, (sheet + 1) * perSheet).map((item, index) => (
              <div
                key={item.student.id}
                className="print-avoid-break"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 22,
                  padding: '20px 46px',
                  borderBottom: index < perSheet - 1 ? '1px dashed var(--d-line)' : 'none',
                }}
              >
                <div
                  style={{
                    width: 62,
                    height: 62,
                    flexShrink: 0,
                    borderRadius: '50%',
                    background: 'var(--d-accent-soft)',
                    border: '1.5px solid var(--d-accent)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    ...T.display(24),
                    color: 'var(--d-accent)',
                  }}
                >
                  {item.order_no}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ ...T.display(24) }}>{item.student.student_name}</p>
                  <p style={{ marginTop: 4, fontSize: 13, color: 'var(--d-accent)' }}>
                    {item.student.piece_title}
                    {item.student.composer ? ` · ${item.student.composer}` : ''}
                  </p>
                  <p style={{ marginTop: 6, ...T.body(11) }}>
                    {item.student.note?.trim() || pieceCommentary(item.student)}
                  </p>
                </div>
                <div style={{ flexShrink: 0, textAlign: 'right' }}>
                  <TrebleClef size={16} opacity={0.55} />
                  <p style={{ marginTop: 4, ...T.label(7.5) }}>{academy.name}</p>
                  <p style={{ marginTop: 3, fontSize: 9.5, color: 'var(--d-muted)' }}>
                    {formatWallClock(event.event_at, item.start_offset_sec)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Sheet>
      ))}
    </>
  )
}

/** 응원 메시지 카드 — 학부모가 한 줄 남기고, 아이가 가져간다 */
export function GuestBook({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <div style={{ flex: 1, display: 'grid', gridTemplateRows: 'repeat(4, 1fr)' }}>
        {Array.from({ length: 4 }, (_, index) => (
          <div
            key={index}
            className="print-avoid-break"
            style={{
              display: 'flex',
              flexDirection: 'column',
              padding: '20px 44px',
              borderBottom: index < 3 ? '1px dashed var(--d-line)' : 'none',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
              <p style={{ ...T.display(17) }}>
                <span style={{ color: 'var(--d-accent)' }}>To.</span>{' '}
                <span
                  style={{
                    display: 'inline-block',
                    minWidth: 130,
                    borderBottom: '1px solid var(--d-line)',
                  }}
                />
              </p>
              <p style={{ ...T.label(8) }}>
                {academy.name} · {d.year}.{d.month}.{d.day}
              </p>
            </div>

            <div style={{ marginTop: 12, flex: 1 }}>
              {[0, 1, 2].map((line) => (
                <div key={line} style={{ height: 26, borderBottom: '0.5px solid var(--d-line)' }} />
              ))}
            </div>

            <p style={{ marginTop: 8, textAlign: 'right', ...T.body(10.5) }}>
              From. <span style={{ display: 'inline-block', minWidth: 110, borderBottom: '1px solid var(--d-line)' }} />
            </p>
          </div>
        ))}
      </div>
    </Sheet>
  )
}

/** 감사장 — 대관처·반주자·도움 주신 분께 */
export function ThanksLetter({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-landscape">
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center',
          padding: '58px 96px',
        }}
      >
        <p style={{ ...T.label(11) }}>감 사 장</p>
        <div style={{ marginTop: 22 }}>
          <OrnamentDivider id={theme.ornament} width={220} />
        </div>

        <p style={{ marginTop: 34, ...T.display(30) }}>
          <span
            style={{
              display: 'inline-block',
              minWidth: 240,
              borderBottom: '1.5px solid var(--d-line)',
            }}
          />{' '}
          귀하
        </p>

        <p style={{ marginTop: 32, maxWidth: 560, fontSize: 15, lineHeight: 2.1, fontFamily: 'var(--d-display)' }}>
          {d.year}년 {d.month}월 {d.day}일에 열린 <b>{event.title}</b>가
          <br />
          무사히 마무리될 수 있도록 함께해 주셔서 깊이 감사드립니다.
          <br />
          귀하의 도움으로 아이들이 좋은 무대를 경험했습니다.
        </p>

        <div style={{ marginTop: 'auto', paddingTop: 34 }}>
          <p style={{ fontSize: 13, color: 'var(--d-muted)' }}>
            {d.year}년 {d.month}월 {d.day}일
          </p>
          <p style={{ marginTop: 12, ...T.display(19) }}>{academy.name}</p>
          <p style={{ marginTop: 4, fontSize: 14 }}>원장 {academy.director_name} </p>
        </div>
      </div>
    </Sheet>
  )
}
