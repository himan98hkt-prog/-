import { OrnamentDivider } from '@/components/design/ornaments'
import { Sheet, type as T } from '@/components/design/sheet'
import { dateParts } from '@/components/design/templates/posters'
import type { DesignContext } from '@/lib/design/context'
import { formatWallClock } from '@/lib/format'
import { buildChecklist } from '@/lib/ops/checklist'
import { buildCueSheet, cueSheetSpanMin, type CueItem } from '@/lib/ops/cuesheet'

const KIND_LABEL: Record<CueItem['kind'], string> = {
  prep: '준비',
  stage: '무대',
  close: '마무리',
}

/** 당일 진행표 — 사회자·스태프가 손에 들고 다니는 종이 */
export function CueSheet({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, plan } = ctx
  const items = buildCueSheet(event, plan)
  const span = cueSheetSpanMin(items)
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false} flow>
      <div style={{ flex: 1, padding: '52px 54px 40px', display: 'flex', flexDirection: 'column' }}>
        <header style={{ textAlign: 'center', paddingBottom: 14, borderBottom: '2px solid var(--d-ink)' }}>
          <p style={{ ...T.label(10) }}>{academy.name}</p>
          <h1 style={{ ...T.display(26), marginTop: 8 }}>{event.title} · 당일 진행표</h1>
          <p style={{ marginTop: 7, fontSize: 11.5, color: 'var(--d-muted)' }}>
            {d.year}. {d.month}. {d.day} ({d.weekday}) 개회 {d.time}
            {event.venue ? ` · ${event.venue}` : ''} · 총 {Math.round(span / 60)}시간 진행
          </p>
        </header>

        <table style={{ width: '100%', marginTop: 16, borderCollapse: 'collapse', fontSize: 10.5 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--d-line)', textAlign: 'left', color: 'var(--d-muted)' }}>
              <th style={{ width: 62, padding: '5px 0', fontWeight: 500 }}>시각</th>
              <th style={{ width: 34, padding: '5px 0', fontWeight: 500 }}>소요</th>
              <th style={{ width: 40, padding: '5px 0', fontWeight: 500 }}>구분</th>
              <th style={{ padding: '5px 0', fontWeight: 500 }}>내용</th>
              <th style={{ width: 44, padding: '5px 0', fontWeight: 500 }}>담당</th>
              <th style={{ width: 26, padding: '5px 0', fontWeight: 500 }}>✓</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, index) => (
              <tr
                key={`${item.offset_min}-${index}`}
                className="print-avoid-break"
                style={{
                  borderBottom: '0.5px solid var(--d-line)',
                  background: item.kind === 'stage' ? 'transparent' : 'var(--d-paper-alt)',
                }}
              >
                <td style={{ padding: '5px 0', fontVariantNumeric: 'tabular-nums', fontWeight: 700 }}>
                  {formatWallClock(event.event_at, item.offset_min * 60)}
                </td>
                <td style={{ padding: '5px 0', color: 'var(--d-muted)', fontVariantNumeric: 'tabular-nums' }}>
                  {item.duration_min}분
                </td>
                <td style={{ padding: '5px 0', fontSize: 9.5, color: 'var(--d-accent)' }}>{KIND_LABEL[item.kind]}</td>
                <td style={{ padding: '5px 6px 5px 0' }}>
                  <span style={{ fontWeight: 600 }}>{item.title}</span>
                  <span style={{ display: 'block', fontSize: 9.5, color: 'var(--d-muted)', lineHeight: 1.5 }}>
                    {item.detail}
                  </span>
                </td>
                <td style={{ padding: '5px 0', fontSize: 9.5 }}>{item.owner}</td>
                <td style={{ padding: '5px 0' }}>
                  <span
                    style={{
                      display: 'inline-block',
                      width: 11,
                      height: 11,
                      border: '1px solid var(--d-line)',
                      borderRadius: 2,
                    }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <footer style={{ marginTop: 'auto', paddingTop: 14, fontSize: 9.5, color: 'var(--d-muted)' }}>
          비상 연락 __________________ · 대관 담당 __________________ · 촬영 담당 __________________
        </footer>
      </div>
    </Sheet>
  )
}

/** 준비 체크리스트 — D-30 부터 종료 후까지 */
export function ChecklistSheet({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event } = ctx
  const groups = buildChecklist(event)
  const half = Math.ceil(groups.length / 2)
  const columns = [groups.slice(0, half), groups.slice(half)]

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false} flow>
      <div style={{ flex: 1, padding: '52px 50px 40px', display: 'flex', flexDirection: 'column' }}>
        <header style={{ textAlign: 'center' }}>
          <p style={{ ...T.label(10) }}>{academy.name}</p>
          <h1 style={{ ...T.display(26), marginTop: 8 }}>{event.title} · 준비 체크리스트</h1>
          <div style={{ marginTop: 12, display: 'flex', justifyContent: 'center' }}>
            <OrnamentDivider id={theme.ornament} width={160} />
          </div>
        </header>

        <div style={{ marginTop: 20, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 26px', flex: 1 }}>
          {columns.map((column, index) => (
            <div key={index}>
              {column.map((group) => (
                <section key={group.id} className="print-avoid-break" style={{ marginBottom: 18 }}>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'baseline',
                      justifyContent: 'space-between',
                      paddingBottom: 5,
                      borderBottom: '1px solid var(--d-ink)',
                    }}
                  >
                    <h2 style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--d-display)' }}>{group.label}</h2>
                    <span style={{ fontSize: 9.5, color: 'var(--d-muted)' }}>{group.date}</span>
                  </div>

                  <ul style={{ listStyle: 'none', margin: '8px 0 0', padding: 0 }}>
                    {group.tasks.map((task) => (
                      <li key={task.id} style={{ display: 'flex', gap: 7, marginBottom: 7 }}>
                        <span
                          style={{
                            marginTop: 2,
                            width: 10,
                            height: 10,
                            flexShrink: 0,
                            border: `1px solid ${task.critical ? 'var(--d-accent)' : 'var(--d-line)'}`,
                            borderRadius: 2,
                          }}
                        />
                        <span style={{ minWidth: 0 }}>
                          <span style={{ fontSize: 10.5, fontWeight: task.critical ? 700 : 500 }}>
                            {task.title}
                            {task.critical && <span style={{ color: 'var(--d-accent)' }}> ★</span>}
                          </span>
                          <span style={{ display: 'block', fontSize: 9, color: 'var(--d-muted)', lineHeight: 1.5 }}>
                            {task.detail}
                          </span>
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          ))}
        </div>

        <footer style={{ marginTop: 'auto', paddingTop: 10, fontSize: 9, color: 'var(--d-muted)', textAlign: 'center' }}>
          ★ 표시는 특히 자주 빠뜨리는 항목입니다.
        </footer>
      </div>
    </Sheet>
  )
}
