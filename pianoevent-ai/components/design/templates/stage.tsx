import { LogoSlot } from '@/components/design/logo'
import { OrnamentDivider, TrebleClef } from '@/components/design/ornaments'
import { Sheet, type as T } from '@/components/design/sheet'
import { dateParts } from '@/components/design/templates/posters'
import type { DesignContext } from '@/lib/design/context'
import { formatWallClock } from '@/lib/format'
import { DEFAULT_SEATING_OPTIONS, buildSeating } from '@/lib/ops/seating'

/**
 * 좌석 배치도.
 * 참석 회신은 이미 쌓여 있는데 그걸 좌석으로 바꾸는 건 여전히 손이었다.
 * 가정 단위로 붙여 앉힌 결과를 접수처 벽에 붙일 수 있는 형태로 그린다.
 */
export function SeatingChart({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event } = ctx
  const options = DEFAULT_SEATING_OPTIONS
  const seating = buildSeating(ctx.rsvps ?? [], options)
  const d = dateParts(event.event_at)

  const rows = Array.from({ length: options.rows }, (_, i) => i + 1)
  // 좌석 칸의 폭은 실제 좌석 수에 비례해야 배치도로 쓸 수 있다
  const pct = (seats: number) => `${(seats / options.seats_per_row) * 100}%`

  return (
    <Sheet theme={theme} page="a4-landscape" decorated={false}>
      <div style={{ height: '100%', padding: '42px 48px 34px', display: 'flex', flexDirection: 'column' }}>
        <header style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', paddingBottom: 12, borderBottom: '2px solid var(--d-ink)' }}>
          <div>
            <p style={{ ...T.label(9.5) }}>{academy.name}</p>
            <h1 style={{ ...T.display(23), marginTop: 6 }}>{event.title} · 좌석 배치도</h1>
          </div>
          <p style={{ fontSize: 11, color: 'var(--d-muted)' }}>
            {d.month}. {d.day} ({d.weekday}) · 배정 {seating.assigned_seats}석 / 여유 {seating.free_seats}석
          </p>
        </header>

        <div
          style={{
            marginTop: 14,
            padding: '6px 0',
            background: 'var(--d-band)',
            color: 'var(--d-band-ink)',
            textAlign: 'center',
            fontSize: 12,
            letterSpacing: '0.4em',
          }}
        >
          무 대
        </div>

        <div style={{ marginTop: 12, flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {rows.map((row) => {
            const isPerformer = seating.performer_rows.includes(row)
            const blocks = seating.blocks.filter((b) => b.row === row)

            return (
              <div key={row} style={{ display: 'flex', alignItems: 'stretch', gap: 8, flex: 1, minHeight: 34 }}>
                <div
                  style={{
                    width: 34,
                    flexShrink: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 11,
                    fontWeight: 700,
                    color: 'var(--d-muted)',
                    border: '0.5px solid var(--d-line)',
                  }}
                >
                  {row}열
                </div>
                <div
                  style={{
                    flex: 1,
                    display: 'flex',
                    padding: 3,
                    border: '0.5px solid var(--d-line)',
                    background: isPerformer ? 'var(--d-accent-soft)' : 'transparent',
                    position: 'relative',
                  }}
                >
                  {isPerformer ? (
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', paddingLeft: 8, fontSize: 11, color: 'var(--d-accent)', fontWeight: 700 }}>
                      연주자석 — 순서대로 앉습니다
                    </div>
                  ) : blocks.length === 0 ? (
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', paddingLeft: 8, fontSize: 10, color: 'var(--d-muted)' }}>
                      여유석
                    </div>
                  ) : (
                    blocks.map((block, index) => {
                      const prev = blocks[index - 1]
                      const gap = block.from - (prev ? prev.to + 1 : 1)
                      return (
                        <div key={`${block.row}-${block.from}`} style={{ display: 'contents' }}>
                          {gap > 0 && <div style={{ width: pct(gap) }} aria-hidden />}
                          <div
                            style={{
                              width: pct(block.headcount),
                              padding: '4px 6px',
                              background: 'var(--d-paper-alt)',
                              border: '0.5px solid var(--d-line)',
                              overflow: 'hidden',
                            }}
                          >
                            <div style={{ fontSize: 10.5, fontWeight: 700, whiteSpace: 'nowrap' }}>
                              {block.student_name} 가족
                            </div>
                            <div style={{ fontSize: 8.5, color: 'var(--d-muted)', whiteSpace: 'nowrap' }}>
                              {block.from}~{block.to}번 · {block.headcount}석
                            </div>
                          </div>
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            )
          })}
        </div>

        <footer style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--d-line)', fontSize: 9.5, color: 'var(--d-muted)' }}>
          {seating.overflow.length > 0
            ? `미배정 ${seating.overflow.length}가정 — ${seating.overflow.map((o) => `${o.student_name}(${o.headcount})`).join(', ')}`
            : '전 가정 배정 완료 · 당일 방문 가족은 여유석으로 안내해 주세요.'}
        </footer>
      </div>
    </Sheet>
  )
}

/**
 * 무대 뒤 대기 순서판.
 * 원장이 무대 뒤에서 "다음 누구!" 를 외치던 일을 종이가 대신한다.
 * 글씨가 커야 아이들이 멀리서 자기 차례를 본다.
 */
export function BackstageBoard({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, plan } = ctx

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false} flow>
      <div style={{ flex: 1, padding: '44px 46px 34px', display: 'flex', flexDirection: 'column' }}>
        <header style={{ textAlign: 'center', paddingBottom: 12, borderBottom: '3px solid var(--d-accent)' }}>
          <p style={{ ...T.label(10) }}>{academy.name}</p>
          <h1 style={{ ...T.display(30), marginTop: 6 }}>대기 순서</h1>
          <p style={{ marginTop: 6, fontSize: 12, color: 'var(--d-muted)' }}>
            자기 차례 두 번 앞에서 무대 옆으로 와 주세요
          </p>
        </header>

        <div style={{ marginTop: 12, flex: 1, display: 'flex', flexDirection: 'column' }}>
          {plan.items.map((item) => (
            <div
              key={item.student.id}
              className="print-avoid-break"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                padding: '7px 0',
                borderBottom: '0.5px solid var(--d-line)',
              }}
            >
              <div
                style={{
                  width: 42,
                  height: 42,
                  flexShrink: 0,
                  borderRadius: '50%',
                  background: 'var(--d-accent)',
                  color: 'var(--d-paper)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  ...T.display(19),
                }}
              >
                {item.order_no}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ ...T.display(21) }}>{item.student.student_name}</p>
                <p style={{ marginTop: 2, fontSize: 11, color: 'var(--d-muted)' }}>{item.student.piece_title}</p>
              </div>
              <div style={{ textAlign: 'right', fontSize: 14, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                {formatWallClock(event.event_at, item.start_offset_sec)}
              </div>
            </div>
          ))}
        </div>

        <footer style={{ marginTop: 10, textAlign: 'center', fontSize: 11, color: 'var(--d-muted)' }}>
          시각은 예상입니다. 앞 순서가 빨라질 수 있으니 미리 준비해 주세요.
        </footer>
      </div>
    </Sheet>
  )
}

/** 포토존 보드 — 연주가 끝나고 사진 찍는 자리에 세운다 */
export function PhotoZone({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-landscape">
      <div
        style={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center',
          padding: '60px 80px',
        }}
      >
        <LogoSlot ctx={ctx} height={theme.logo.height + 14} />
        <p style={{ ...T.label(13), marginTop: 18 }}>{academy.name}</p>

        <h1 style={{ ...T.display(62, 800), marginTop: 26 }}>{event.title}</h1>
        {copy.subtitle && (
          <p style={{ marginTop: 14, fontSize: 19, letterSpacing: '0.22em', color: 'var(--d-accent)' }}>{copy.subtitle}</p>
        )}

        <div style={{ marginTop: 28 }}>
          <OrnamentDivider id={theme.ornament} width={320} />
        </div>

        <p style={{ marginTop: 28, ...T.display(30), color: 'var(--d-accent)' }}>
          {d.year}. {d.month}. {d.day}
        </p>
        {event.venue && <p style={{ marginTop: 12, fontSize: 17, color: 'var(--d-muted)' }}>{event.venue}</p>}

        <div style={{ marginTop: 26 }}>
          <TrebleClef size={26} opacity={0.85} />
        </div>
      </div>
    </Sheet>
  )
}

/**
 * 시상 명단.
 * 호명 순서와 상장 종류를 미리 적어 두지 않으면 시상 시간이 두 배로 늘어난다.
 */
export function AwardSheet({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, plan } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false} flow>
      <div style={{ flex: 1, padding: '50px 54px 38px', display: 'flex', flexDirection: 'column' }}>
        <header style={{ textAlign: 'center', paddingBottom: 14, borderBottom: '2px solid var(--d-ink)' }}>
          <p style={{ ...T.label(10) }}>{academy.name}</p>
          <h1 style={{ ...T.display(26), marginTop: 8 }}>{event.title} · 시상 명단</h1>
          <p style={{ marginTop: 6, fontSize: 11, color: 'var(--d-muted)' }}>
            {d.year}. {d.month}. {d.day} · 호명 순서대로 무대 앞으로 나옵니다
          </p>
        </header>

        <table style={{ width: '100%', marginTop: 16, borderCollapse: 'collapse', fontSize: 11.5 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--d-line)', textAlign: 'left', color: 'var(--d-muted)' }}>
              <th style={{ width: 34, padding: '6px 0', fontWeight: 500 }}>호명</th>
              <th style={{ width: 96, padding: '6px 0', fontWeight: 500 }}>이름</th>
              <th style={{ padding: '6px 0', fontWeight: 500 }}>상장 종류</th>
              <th style={{ width: 88, padding: '6px 0', fontWeight: 500 }}>부상</th>
              <th style={{ width: 26, padding: '6px 0', fontWeight: 500 }}>✓</th>
            </tr>
          </thead>
          <tbody>
            {plan.items.map((item, index) => (
              <tr key={item.student.id} className="print-avoid-break" style={{ borderBottom: '0.5px solid var(--d-line)' }}>
                <td style={{ padding: '7px 0', fontWeight: 700, color: 'var(--d-accent)', fontVariantNumeric: 'tabular-nums' }}>
                  {index + 1}
                </td>
                <td style={{ padding: '7px 0', fontWeight: 700, fontFamily: 'var(--d-display)' }}>
                  {item.student.student_name}
                </td>
                <td style={{ padding: '7px 0', color: 'var(--d-muted)' }}>참가 상장</td>
                <td style={{ padding: '7px 0' }} />
                <td style={{ padding: '7px 0' }}>
                  <span style={{ display: 'inline-block', width: 12, height: 12, border: '1px solid var(--d-line)' }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <footer style={{ marginTop: 'auto', paddingTop: 12, borderTop: '1px solid var(--d-line)', ...T.body(10) }}>
          상장 종류와 부상 칸은 비워 두었습니다. 원장님이 손으로 채우시면 됩니다.
          <br />
          호명 뒤 3초를 기다렸다가 다음 이름을 부르면 사진이 흔들리지 않습니다.
        </footer>
      </div>
    </Sheet>
  )
}
