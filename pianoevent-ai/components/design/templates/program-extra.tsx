import { LogoSlot } from '@/components/design/logo'
import { OrnamentDivider, TrebleClef } from '@/components/design/ornaments'
import { Sheet, type as T } from '@/components/design/sheet'
import { dateParts } from '@/components/design/templates/posters'
import type { DesignContext } from '@/lib/design/context'
import { formatDuration, formatWallClock } from '@/lib/format'
import { pieceCommentary } from '@/lib/program/script'
import { STAGE_LABEL } from '@/lib/types'

/**
 * 곡 해설 순서지.
 *
 * 관객이 아는 곡은 몇 곡 없다. 곡목만 적힌 순서지를 받으면 남은 곡 수만 세게 된다.
 * 해설 두 줄이 붙으면 같은 연주가 다르게 들린다 — 원장이 밤새 쓰던 그 두 줄을 붙여 인쇄한다.
 */
export function ProgramNotes({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, plan } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false} flow>
      <div style={{ flex: 1, padding: '54px 58px 42px', display: 'flex', flexDirection: 'column' }}>
        <header style={{ textAlign: 'center', paddingBottom: 16, borderBottom: '2px solid var(--d-accent)' }}>
          <p style={{ ...T.label(10) }}>{academy.name}</p>
          <h1 style={{ ...T.display(28), marginTop: 8 }}>{event.title}</h1>
          <p style={{ marginTop: 7, fontSize: 11.5, color: 'var(--d-muted)' }}>
            {d.year}. {d.month}. {d.day} ({d.weekday}) {d.time}
            {event.venue ? ` · ${event.venue}` : ''}
          </p>
        </header>

        <div style={{ marginTop: 18, flex: 1 }}>
          {plan.items.map((item, index) => {
            const prev = plan.items[index - 1]
            const next = plan.items[index + 1]
            const newStage = !prev || prev.stage !== item.stage
            const samePiece = (a?: typeof item, b?: typeof item) =>
              Boolean(a && b && a.student.piece_title.trim() === b.student.piece_title.trim())
            // 연탄곡은 두 사람이 같은 곡을 친다. 해설을 두 번 싣지 않고 한 줄로 묶는다.
            if (samePiece(prev, item)) return null
            const partners = samePiece(item, next) ? [item, next] : [item]

            return (
              <div key={item.student.id}>
                {newStage && (
                  <p
                    style={{
                      ...T.label(9.5),
                      marginTop: index === 0 ? 0 : 16,
                      marginBottom: 10,
                      color: 'var(--d-accent)',
                    }}
                  >
                    {STAGE_LABEL[item.stage]}
                  </p>
                )}
                <div
                  className="print-avoid-break"
                  style={{
                    display: 'flex',
                    gap: 14,
                    padding: '9px 0',
                    borderBottom: '0.5px solid var(--d-line)',
                  }}
                >
                  <div
                    style={{
                      width: 34,
                      flexShrink: 0,
                      ...T.display(17),
                      color: 'var(--d-accent)',
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    {partners.length > 1
                      ? `${partners[0].order_no}·${partners[1].order_no}`
                      : item.order_no}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontSize: 13.5, fontFamily: 'var(--d-display)', fontWeight: 700 }}>
                      {item.student.piece_title}
                      {item.student.composer && (
                        <span style={{ fontWeight: 400, color: 'var(--d-muted)', fontSize: 11.5 }}>
                          {' '}
                          · {item.student.composer}
                        </span>
                      )}
                    </p>
                    <p style={{ marginTop: 4, fontSize: 10.5, lineHeight: 1.6, color: 'var(--d-muted)' }}>
                      {pieceCommentary(item.student)}
                    </p>
                  </div>
                  <div style={{ width: 92, flexShrink: 0, textAlign: 'right' }}>
                    <p style={{ fontSize: 12.5, fontWeight: 700 }}>
                      {partners.map((p) => p.student.student_name).join(' · ')}
                    </p>
                    <p style={{ marginTop: 3, fontSize: 9.5, color: 'var(--d-muted)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatDuration(item.duration_sec)}
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        <footer style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--d-line)', textAlign: 'center' }}>
          <p style={{ ...T.body(10.5) }}>{ctx.copy.footnote}</p>
        </footer>
      </div>
    </Sheet>
  )
}

/**
 * 3단 접지 프로그램. A4 가로를 세로로 두 번 접으면 세 면이 된다.
 * 인쇄는 한 장, 관객이 받는 건 손에 들어오는 작은 책자다.
 * 접었을 때 맨 위로 오는 면이 표지라서 오른쪽 끝에 둔다.
 */
export function ProgramTrifold({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy, plan } = ctx
  const d = dateParts(event.event_at)

  const panel: React.CSSProperties = {
    flex: 1,
    padding: '52px 34px 40px',
    borderRight: '0.5px dashed var(--d-line)',
    display: 'flex',
    flexDirection: 'column',
    wordBreak: 'keep-all',
  }

  return (
    <Sheet theme={theme} page="a4-landscape" decorated={false}>
      <div style={{ flex: 1, display: 'flex' }}>
        {/* 1면 · 뒷면 — 접었을 때 맨 뒤. 관람 안내와 주최 */}
        <div style={panel}>
          <p style={{ ...T.label(9) }}>관람 안내</p>
          <div style={{ marginTop: 16, ...T.body(11), lineHeight: 2.1 }}>
            <p>· 연주 중에는 휴대전화를 무음으로 해 주세요.</p>
            <p>· 곡이 끝난 뒤 박수로 응원해 주세요.</p>
            <p>· 사진 촬영은 자유롭게, 플래시는 꺼 주세요.</p>
            <p>· 어린 동생은 로비에서 잠시 쉬어 가셔도 됩니다.</p>
            <p>· 연주자석은 앞 두 줄입니다. 비워 주세요.</p>
          </div>

          {event.greeting && (
            <>
              <div style={{ marginTop: 26 }}>
                <OrnamentDivider id={theme.ornament} width={150} />
              </div>
              <p style={{ marginTop: 18, ...T.body(11), whiteSpace: 'pre-line' }}>{event.greeting}</p>
            </>
          )}

          <div style={{ marginTop: 'auto', paddingTop: 20, borderTop: '0.5px solid var(--d-line)' }}>
            <p style={{ ...T.body(10.5) }}>{copy.host}</p>
            {copy.contact && <p style={{ ...T.body(10.5) }}>{copy.contact}</p>}
            <p style={{ marginTop: 6, fontSize: 9.5, color: 'var(--d-muted)' }}>
              참석 회신 · {ctx.inviteUrl.replace(/^https?:\/\//, '')}
            </p>
          </div>
        </div>

        {/* 2면 · 연주 순서 전체 */}
        <div style={panel}>
          <p style={{ ...T.label(9), color: 'var(--d-accent)' }}>연주 순서</p>
          <div style={{ marginTop: 14, flex: 1 }}>
            {plan.items.map((item) => (
              <div
                key={item.student.id}
                style={{
                  display: 'flex',
                  gap: 9,
                  padding: '6.5px 0',
                  borderBottom: '0.5px solid var(--d-line)',
                }}
              >
                <span
                  style={{
                    width: 17,
                    flexShrink: 0,
                    color: 'var(--d-accent)',
                    fontSize: 10.5,
                    fontWeight: 700,
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {item.order_no}
                </span>
                <span style={{ flex: 1, minWidth: 0, fontSize: 10.5, lineHeight: 1.5 }}>
                  <b style={{ fontFamily: 'var(--d-display)' }}>{item.student.student_name}</b>
                  <br />
                  <span style={{ color: 'var(--d-muted)' }}>{item.student.piece_title}</span>
                </span>
                <span style={{ fontSize: 9, color: 'var(--d-muted)', fontVariantNumeric: 'tabular-nums' }}>
                  {formatWallClock(event.event_at, item.start_offset_sec)}
                </span>
              </div>
            ))}
          </div>
          <p style={{ marginTop: 14, fontSize: 9, color: 'var(--d-muted)' }}>
            시각은 예상입니다 · 총 {Math.round(plan.total_sec / 60)}분
          </p>
        </div>

        {/* 3면 · 표지 — 접었을 때 맨 앞 */}
        <div
          style={{
            ...panel,
            borderRight: 'none',
            alignItems: 'center',
            textAlign: 'center',
            background: 'var(--d-paper-alt)',
          }}
        >
          <LogoSlot ctx={ctx} />
          <p style={{ ...T.label(9.5), marginTop: 14 }}>{academy.name}</p>
          <div style={{ marginTop: 26 }}>
            <TrebleClef size={24} opacity={0.85} />
          </div>
          <h1 style={{ ...T.display(28), marginTop: 24 }}>{event.title}</h1>
          {copy.subtitle && <p style={{ marginTop: 10, fontSize: 12, color: 'var(--d-muted)' }}>{copy.subtitle}</p>}
          <div style={{ marginTop: 22 }}>
            <OrnamentDivider id={theme.ornament} width={140} />
          </div>
          <div style={{ marginTop: 'auto' }}>
            <p style={{ ...T.display(38), color: 'var(--d-accent)' }}>
              {d.month}.{d.day}
            </p>
            <p style={{ marginTop: 8, fontSize: 11, color: 'var(--d-muted)' }}>
              {d.year} {d.weekday}요일 {d.time}
            </p>
            {event.venue && <p style={{ marginTop: 12, fontSize: 12.5, fontFamily: 'var(--d-display)' }}>{event.venue}</p>}
          </div>
        </div>
      </div>
    </Sheet>
  )
}
