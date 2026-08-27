import { OrnamentDivider } from '@/components/design/ornaments'
import { Sheet, type as T } from '@/components/design/sheet'
import { dateParts } from '@/components/design/templates/posters'
import type { DesignContext } from '@/lib/design/context'
import { formatWallClock } from '@/lib/format'
import { buildBudget, DEFAULT_BUDGET_ITEMS, formatWon, BASIS_LABEL } from '@/lib/ops/budget'
import { buildRehearsal } from '@/lib/ops/rehearsal'
import { buildSeating, seatLabel } from '@/lib/ops/seating'

/** 인쇄 문서 공통 머리말 — 진행 문서는 장식을 걷고 정보 밀도를 올린다 */
function DocHeader({ ctx, title, note }: { ctx: DesignContext; title: string; note?: string }) {
  const { academy, event } = ctx
  const d = dateParts(event.event_at)

  return (
    <header style={{ paddingBottom: 13, borderBottom: '2px solid var(--d-ink)' }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
        <div>
          <p style={{ ...T.label(9.5) }}>{academy.name}</p>
          <h1 style={{ ...T.display(24), marginTop: 6 }}>{title}</h1>
        </div>
        <p style={{ fontSize: 10.5, color: 'var(--d-muted)', textAlign: 'right' }}>
          {event.title}
          <br />
          {d.year}. {d.month}. {d.day} ({d.weekday}) {d.time}
          {event.venue ? ` · ${event.venue}` : ''}
        </p>
      </div>
      {note && <p style={{ marginTop: 8, fontSize: 10.5, color: 'var(--d-muted)' }}>{note}</p>}
    </header>
  )
}

/**
 * 사회자 대본.
 * 무대 옆은 어둡다. 화면으로 읽을 수 없으니 종이로 나가야 하고, 글씨가 커야 한다.
 */
export function McScriptSheet({ ctx }: { ctx: DesignContext }) {
  const { theme, event, plan } = ctx

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false} flow>
      <div style={{ flex: 1, padding: '48px 54px 38px', display: 'flex', flexDirection: 'column' }}>
        <DocHeader ctx={ctx} title="사회자 대본" note="굵은 글씨는 그대로 읽으시고, 회색 글씨는 진행 지시입니다." />

        {event.mc_opening && (
          <section style={{ marginTop: 18 }} className="print-avoid-break">
            <p style={{ ...T.label(9.5), color: 'var(--d-accent)' }}>오프닝</p>
            <p style={{ marginTop: 8, fontSize: 13.5, lineHeight: 1.85, whiteSpace: 'pre-line' }}>{event.mc_opening}</p>
          </section>
        )}

        <section style={{ marginTop: 20, flex: 1 }}>
          <p style={{ ...T.label(9.5), color: 'var(--d-accent)' }}>연주 순서</p>
          {plan.items.map((item) => (
            <div
              key={item.student.id}
              className="print-avoid-break"
              style={{ marginTop: 13, paddingBottom: 11, borderBottom: '0.5px solid var(--d-line)' }}
            >
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                <span style={{ ...T.display(16), color: 'var(--d-accent)', fontVariantNumeric: 'tabular-nums' }}>
                  {item.order_no}
                </span>
                <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--d-display)' }}>
                  {item.student.student_name}
                </span>
                <span style={{ fontSize: 11, color: 'var(--d-muted)' }}>
                  {item.student.piece_title}
                  {item.student.composer ? ` · ${item.student.composer}` : ''}
                </span>
                <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--d-muted)', fontVariantNumeric: 'tabular-nums' }}>
                  {formatWallClock(event.event_at, item.start_offset_sec)}
                </span>
              </div>
              <p style={{ marginTop: 6, fontSize: 12.5, lineHeight: 1.85, whiteSpace: 'pre-line' }}>
                {item.student.mc_script || '(멘트가 아직 없습니다 — 순서표 화면에서 대본을 만들어 주세요)'}
              </p>
            </div>
          ))}
        </section>

        {event.mc_closing && (
          <section style={{ marginTop: 16 }} className="print-avoid-break">
            <p style={{ ...T.label(9.5), color: 'var(--d-accent)' }}>클로징</p>
            <p style={{ marginTop: 8, fontSize: 13.5, lineHeight: 1.85, whiteSpace: 'pre-line' }}>{event.mc_closing}</p>
          </section>
        )}
      </div>
    </Sheet>
  )
}

/**
 * 리허설 시간표.
 * 조 단위 소집 시각과 학생별 무대 시각 — 당일 아침 원장 머릿속에서 벌어지던 계산.
 */
export function RehearsalSheet({ ctx }: { ctx: DesignContext }) {
  const { theme, event, plan } = ctx
  const r = buildRehearsal(plan)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false} flow>
      <div style={{ flex: 1, padding: '48px 54px 38px', display: 'flex', flexDirection: 'column' }}>
        <DocHeader
          ctx={ctx}
          title="리허설 시간표"
          note={`${r.slots.length}명 · ${r.groups.length}개 조 · 리허설 ${formatWallClock(event.event_at, r.start_offset_sec)} ~ ${formatWallClock(event.event_at, r.end_offset_sec)}`}
        />

        <section style={{ marginTop: 16 }}>
          <p style={{ ...T.label(9.5), color: 'var(--d-accent)', marginBottom: 8 }}>조별 소집</p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {r.groups.map((group) => (
              <div
                key={group.group}
                style={{
                  flex: '1 1 150px',
                  padding: '9px 11px',
                  border: '1px solid var(--d-line)',
                  background: 'var(--d-paper-alt)',
                }}
              >
                <p style={{ fontSize: 11, fontWeight: 700 }}>
                  {group.group}조 · {formatWallClock(event.event_at, group.call_offset_sec)} 도착
                </p>
                <p style={{ marginTop: 4, fontSize: 9.5, color: 'var(--d-muted)', lineHeight: 1.6 }}>
                  {group.members.map((m) => m.student_name).join(', ')}
                </p>
              </div>
            ))}
          </div>
        </section>

        <table style={{ width: '100%', marginTop: 18, borderCollapse: 'collapse', fontSize: 11 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--d-line)', textAlign: 'left', color: 'var(--d-muted)' }}>
              <th style={{ width: 30, padding: '6px 0', fontWeight: 500 }}>순</th>
              <th style={{ width: 34, padding: '6px 0', fontWeight: 500 }}>조</th>
              <th style={{ width: 62, padding: '6px 0', fontWeight: 500 }}>무대</th>
              <th style={{ width: 90, padding: '6px 0', fontWeight: 500 }}>이름</th>
              <th style={{ padding: '6px 0', fontWeight: 500 }}>곡</th>
              <th style={{ width: 26, padding: '6px 0', fontWeight: 500 }}>✓</th>
            </tr>
          </thead>
          <tbody>
            {r.slots.map((slot) => (
              <tr key={slot.order_no} className="print-avoid-break" style={{ borderBottom: '0.5px solid var(--d-line)' }}>
                <td style={{ padding: '6px 0', fontVariantNumeric: 'tabular-nums' }}>{slot.order_no}</td>
                <td style={{ padding: '6px 0', color: 'var(--d-accent)', fontWeight: 700 }}>{slot.group}</td>
                <td style={{ padding: '6px 0', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                  {formatWallClock(event.event_at, slot.stage_offset_sec)}
                </td>
                <td style={{ padding: '6px 0', fontFamily: 'var(--d-display)', fontWeight: 700 }}>{slot.student_name}</td>
                <td style={{ padding: '6px 0', color: 'var(--d-muted)' }}>{slot.piece_title}</td>
                <td style={{ padding: '6px 0' }}>
                  <span style={{ display: 'inline-block', width: 11, height: 11, border: '1px solid var(--d-line)' }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <footer style={{ marginTop: 'auto', paddingTop: 12, borderTop: '1px solid var(--d-line)', ...T.body(10) }}>
          {r.warnings.length > 0 ? r.warnings.join(' ') : '리허설이 개회 전에 여유 있게 끝납니다.'}
        </footer>
      </div>
    </Sheet>
  )
}

/**
 * 접수 확인표.
 * 접수처에서 도착 체크, 좌석 안내, 참가비 확인을 한 장으로 한다.
 */
export function AttendanceSheet({ ctx }: { ctx: DesignContext }) {
  const { theme, plan } = ctx
  const seating = buildSeating(ctx.rsvps ?? [])
  const seatOf = new Map(seating.blocks.map((b) => [b.student_name, seatLabel(b)]))

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false} flow>
      <div style={{ flex: 1, padding: '48px 54px 38px', display: 'flex', flexDirection: 'column' }}>
        <DocHeader ctx={ctx} title="접수 확인표" note="도착한 순서대로 체크하고 좌석을 안내해 주세요." />

        <table style={{ width: '100%', marginTop: 16, borderCollapse: 'collapse', fontSize: 11 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--d-line)', textAlign: 'left', color: 'var(--d-muted)' }}>
              <th style={{ width: 28, padding: '6px 0', fontWeight: 500 }}>순</th>
              <th style={{ width: 88, padding: '6px 0', fontWeight: 500 }}>학생</th>
              <th style={{ width: 30, padding: '6px 0', fontWeight: 500 }}>도착</th>
              <th style={{ width: 84, padding: '6px 0', fontWeight: 500 }}>좌석</th>
              <th style={{ width: 34, padding: '6px 0', fontWeight: 500 }}>참가비</th>
              <th style={{ padding: '6px 0', fontWeight: 500 }}>특이사항</th>
            </tr>
          </thead>
          <tbody>
            {plan.items.map((item) => (
              <tr key={item.student.id} className="print-avoid-break" style={{ borderBottom: '0.5px solid var(--d-line)' }}>
                <td style={{ padding: '7px 0', fontVariantNumeric: 'tabular-nums' }}>{item.order_no}</td>
                <td style={{ padding: '7px 0', fontFamily: 'var(--d-display)', fontWeight: 700 }}>
                  {item.student.student_name}
                </td>
                <td style={{ padding: '7px 0' }}>
                  <span style={{ display: 'inline-block', width: 12, height: 12, border: '1px solid var(--d-line)' }} />
                </td>
                <td style={{ padding: '7px 0', fontSize: 10, color: 'var(--d-accent)' }}>
                  {seatOf.get(item.student.student_name) ?? ''}
                </td>
                <td style={{ padding: '7px 0' }}>
                  <span style={{ display: 'inline-block', width: 12, height: 12, border: '1px solid var(--d-line)' }} />
                </td>
                <td style={{ padding: '7px 0' }} />
              </tr>
            ))}
          </tbody>
        </table>

        <footer style={{ marginTop: 'auto', paddingTop: 12, borderTop: '1px solid var(--d-line)', ...T.body(10) }}>
          좌석 칸이 비어 있으면 참석 회신이 아직 없는 가정입니다. 여유석으로 안내해 주세요.
        </footer>
      </div>
    </Sheet>
  )
}

/** 예산·정산표 — 항목별 금액과 권장 참가비까지 */
export function BudgetSheet({ ctx }: { ctx: DesignContext }) {
  const { theme, plan } = ctx
  const rsvps = (ctx.rsvps ?? []).filter((r) => r.attending)
  const guests = rsvps.reduce((s, r) => s + r.headcount, 0)
  const students = plan.items.length
  const result = buildBudget({
    students,
    families: Math.max(rsvps.length, students),
    guests: guests || students * 3,
    items: DEFAULT_BUDGET_ITEMS,
    academy_share: 0,
  })

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false} flow>
      <div style={{ flex: 1, padding: '48px 54px 38px', display: 'flex', flexDirection: 'column' }}>
        <DocHeader
          ctx={ctx}
          title="예산 · 정산표"
          note={`학생 ${students}명 · 가정 ${result.lines.find((l) => l.item.basis === 'per_family')?.qty ?? 0}곳 기준. 단가는 학원 사정에 맞게 고쳐 쓰세요.`}
        />

        <table style={{ width: '100%', marginTop: 16, borderCollapse: 'collapse', fontSize: 11 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--d-line)', textAlign: 'left', color: 'var(--d-muted)' }}>
              <th style={{ padding: '6px 0', fontWeight: 500 }}>항목</th>
              <th style={{ width: 66, padding: '6px 0', fontWeight: 500 }}>기준</th>
              <th style={{ width: 76, padding: '6px 0', fontWeight: 500, textAlign: 'right' }}>단가</th>
              <th style={{ width: 34, padding: '6px 0', fontWeight: 500, textAlign: 'right' }}>수량</th>
              <th style={{ width: 88, padding: '6px 0', fontWeight: 500, textAlign: 'right' }}>금액</th>
            </tr>
          </thead>
          <tbody>
            {result.lines.map((line) => (
              <tr key={line.item.id} className="print-avoid-break" style={{ borderBottom: '0.5px solid var(--d-line)' }}>
                <td style={{ padding: '7px 0' }}>
                  <b style={{ fontFamily: 'var(--d-display)' }}>{line.item.label}</b>
                  {line.item.optional && (
                    <span style={{ marginLeft: 6, fontSize: 8.5, color: 'var(--d-accent)' }}>선택</span>
                  )}
                  <br />
                  <span style={{ fontSize: 9, color: 'var(--d-muted)' }}>{line.item.note}</span>
                </td>
                <td style={{ padding: '7px 0', fontSize: 9.5, color: 'var(--d-muted)' }}>{BASIS_LABEL[line.item.basis]}</td>
                <td style={{ padding: '7px 0', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                  {line.item.unit_cost.toLocaleString('ko-KR')}
                </td>
                <td style={{ padding: '7px 0', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{line.qty}</td>
                <td style={{ padding: '7px 0', textAlign: 'right', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                  {line.amount.toLocaleString('ko-KR')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div style={{ marginTop: 16, padding: '14px 16px', background: 'var(--d-accent-soft)', border: '1px solid var(--d-line)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
            <span>합계</span>
            <b style={{ fontVariantNumeric: 'tabular-nums' }}>{formatWon(result.total)}</b>
          </div>
          <div style={{ marginTop: 6, display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
            <span>학생 1인당 원가</span>
            <b style={{ fontVariantNumeric: 'tabular-nums' }}>{formatWon(result.per_student)}</b>
          </div>
          <div
            style={{
              marginTop: 8,
              paddingTop: 8,
              borderTop: '1px solid var(--d-line)',
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 14,
            }}
          >
            <span style={{ fontWeight: 700 }}>권장 참가비</span>
            <b style={{ ...T.display(18), color: 'var(--d-accent)' }}>{formatWon(result.suggested_fee)}</b>
          </div>
        </div>

        <footer style={{ marginTop: 'auto', paddingTop: 12, borderTop: '1px solid var(--d-line)', ...T.body(10) }}>
          {result.warnings.length > 0
            ? result.warnings.join(' ')
            : '선택 항목을 빼면 참가비를 더 낮출 수 있습니다. 대관료가 확정되면 단가부터 고치세요.'}
        </footer>
      </div>
    </Sheet>
  )
}

/** 학부모 안내문 — 같은 질문을 스무 번 받지 않기 위한 한 장 */
export function ParentNotice({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy, plan } = ctx
  const d = dateParts(event.event_at)
  const endMin = Math.round(plan.total_sec / 60)

  const section = (title: string, lines: string[]) => (
    <section key={title} style={{ marginTop: 18 }} className="print-avoid-break">
      <p style={{ ...T.label(9.5), color: 'var(--d-accent)' }}>{title}</p>
      <div style={{ marginTop: 7, fontSize: 12, lineHeight: 1.95 }}>
        {lines.map((line) => (
          <p key={line}>· {line}</p>
        ))}
      </div>
    </section>
  )

  return (
    <Sheet theme={theme} page="a4-portrait">
      <div style={{ flex: 1, padding: '62px 62px 48px', display: 'flex', flexDirection: 'column' }}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ ...T.label(10) }}>{academy.name}</p>
          <h1 style={{ ...T.display(28), marginTop: 8 }}>{event.title} 안내</h1>
          <div style={{ marginTop: 12, display: 'flex', justifyContent: 'center' }}>
            <OrnamentDivider id={theme.ornament} width={190} />
          </div>
        </div>

        <p style={{ marginTop: 22, ...T.body(12), whiteSpace: 'pre-line' }}>
          {event.greeting ||
            '한 해 동안 아이들이 쌓아 온 시간을 들려드립니다. 아래 내용을 한 번만 읽어 주시면 당일이 훨씬 편안해집니다.'}
        </p>

        {section('언제 · 어디서', [
          `${d.year}년 ${d.month}월 ${d.day}일 (${d.weekday}) ${d.time} 시작`,
          event.venue ? `${event.venue}` : '학원 연주홀',
          `연주 시간은 약 ${endMin}분입니다. 시작 20분 전부터 입장하실 수 있습니다.`,
        ])}

        {section('오시는 길과 주차', [
          '주차 공간이 넉넉하지 않습니다. 가능하면 대중교통을 이용해 주세요.',
          '주차하실 경우 시작 30분 전에는 도착하시는 편이 안전합니다.',
        ])}

        {section('관람 안내', [
          '연주 중에는 휴대전화를 무음으로 해 주세요.',
          '곡이 끝난 뒤 박수로 응원해 주세요. 곡 중간의 박수는 아이가 흔들립니다.',
          '사진과 영상은 자유롭게 찍으셔도 됩니다. 플래시만 꺼 주세요.',
          '어린 동생이 울면 잠시 로비에서 쉬어 가셔도 괜찮습니다.',
        ])}

        {section('아이에게 해 주실 말', [
          '"틀려도 괜찮아, 끝까지 치면 돼" 한마디면 충분합니다.',
          '연주가 끝나면 잘한 점 하나를 구체적으로 말해 주세요.',
        ])}

        <footer style={{ marginTop: 'auto', paddingTop: 14, borderTop: '1px solid var(--d-line)', textAlign: 'center' }}>
          <p style={{ ...T.body(11) }}>
            {copy.host}
            {copy.contact ? ` · ${copy.contact}` : ''}
          </p>
          <p style={{ marginTop: 4, fontSize: 10, color: 'var(--d-muted)' }}>
            참석 회신 · {ctx.inviteUrl.replace(/^https?:\/\//, '')}
          </p>
        </footer>
      </div>
    </Sheet>
  )
}

/** 학생 준비 안내문 — 아이가 들고 가서 냉장고에 붙이는 종이 */
export function StudentNotice({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, plan } = ctx
  const d = dateParts(event.event_at)
  const r = buildRehearsal(plan)

  const block = (title: string, lines: string[]) => (
    <section
      key={title}
      className="print-avoid-break"
      style={{ marginTop: 14, padding: '13px 16px', border: '1px solid var(--d-line)', background: 'var(--d-paper-alt)' }}
    >
      <p style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--d-display)', color: 'var(--d-accent)' }}>{title}</p>
      <div style={{ marginTop: 6, fontSize: 12, lineHeight: 1.9 }}>
        {lines.map((line) => (
          <p key={line}>· {line}</p>
        ))}
      </div>
    </section>
  )

  return (
    <Sheet theme={theme} page="a4-portrait">
      <div style={{ flex: 1, padding: '58px 58px 44px', display: 'flex', flexDirection: 'column' }}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ ...T.label(10) }}>{academy.name}</p>
          <h1 style={{ ...T.display(30), marginTop: 8 }}>연주회 준비물</h1>
          <p style={{ marginTop: 8, fontSize: 13, color: 'var(--d-accent)', fontWeight: 700 }}>
            {d.month}월 {d.day}일 ({d.weekday}) {d.time}
            {event.venue ? ` · ${event.venue}` : ''}
          </p>
        </div>

        {block('꼭 챙길 것', [
          '악보 (외워서 치더라도 꼭 가져오세요)',
          '연주할 옷과 신발 — 입고 오면 갈아입을 필요가 없습니다',
          '물 한 병',
          '머리끈이나 핀 (긴 머리는 묶어 주세요)',
        ])}

        {block('입지 않는 것이 좋은 것', [
          '굽이 높은 구두 — 페달을 밟기 어렵습니다',
          '소매가 넓은 옷 — 건반에 걸립니다',
          '소리 나는 팔찌와 시계',
        ])}

        {block('언제 도착할까요', [
          r.groups.length > 0
            ? `${r.groups[0].group}조는 ${formatWallClock(event.event_at, r.groups[0].call_offset_sec)}까지, 조별 시각은 따로 알려드립니다`
            : '시작 1시간 전까지 도착해 주세요',
          '도착하면 접수처에 이름을 말하고 대기실로 가세요',
          '자기 차례 두 번 앞에서 무대 옆으로 오면 됩니다',
        ])}

        {block('무대에서', [
          '들어가서 관객을 보고 인사 — 하나, 둘, 셋 세고 앉으세요',
          '건반에 손을 올리고 한 번 숨을 쉬고 시작하세요',
          '틀려도 멈추지 말고 끝까지 치세요. 아무도 모릅니다',
          '끝나면 손을 무릎에 올리고 일어나서 다시 인사',
        ])}

        <footer style={{ marginTop: 'auto', paddingTop: 14, borderTop: '1px solid var(--d-line)', textAlign: 'center' }}>
          <p style={{ ...T.display(15) }}>긴장하는 건 잘하고 싶다는 뜻이에요.</p>
          <p style={{ marginTop: 5, ...T.body(11) }}>{academy.director_name} 원장 드림</p>
        </footer>
      </div>
    </Sheet>
  )
}

/**
 * 연습 기록표.
 *
 * 연주회 4주 전부터 아이가 매일 체크한다. 원장이 "연습했니" 를 스무 번 묻지 않아도 되고,
 * 학부모는 아이가 얼마나 준비했는지 눈으로 본다.
 */
export function PracticeLog({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event } = ctx
  const d = dateParts(event.event_at)
  const WEEKS = 4
  const DAYS = ['월', '화', '수', '목', '금', '토', '일']

  return (
    <Sheet theme={theme} page="a4-portrait" flow>
      <div style={{ flex: 1, padding: '54px 58px 42px', display: 'flex', flexDirection: 'column' }}>
        <header style={{ textAlign: 'center', paddingBottom: 14, borderBottom: '2px solid var(--d-accent)' }}>
          <p style={{ ...T.label(10) }}>{academy.name}</p>
          <h1 style={{ ...T.display(30), marginTop: 8 }}>연습 기록표</h1>
          <p style={{ marginTop: 8, fontSize: 13, color: 'var(--d-accent)', fontWeight: 700 }}>
            {event.title} · {d.month}월 {d.day}일 ({d.weekday})
          </p>
        </header>

        <div style={{ marginTop: 18, display: 'flex', gap: 14, fontSize: 13 }}>
          <span>
            이름 <span style={{ display: 'inline-block', width: 120, borderBottom: '1px solid var(--d-line)' }} />
          </span>
          <span>
            곡 <span style={{ display: 'inline-block', width: 200, borderBottom: '1px solid var(--d-line)' }} />
          </span>
        </div>

        <table style={{ width: '100%', marginTop: 18, borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--d-line)', color: 'var(--d-muted)' }}>
              <th style={{ width: 60, padding: '7px 0', fontWeight: 500, textAlign: 'left' }}>주차</th>
              {DAYS.map((day) => (
                <th key={day} style={{ padding: '7px 0', fontWeight: 500 }}>
                  {day}
                </th>
              ))}
              <th style={{ width: 90, padding: '7px 0', fontWeight: 500 }}>원장 확인</th>
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: WEEKS }, (_, week) => (
              <tr key={week} className="print-avoid-break" style={{ borderBottom: '0.5px solid var(--d-line)' }}>
                <td style={{ padding: '15px 0', fontWeight: 700, color: 'var(--d-accent)' }}>
                  D-{(WEEKS - week) * 7}
                </td>
                {DAYS.map((day) => (
                  <td key={day} style={{ padding: '15px 0', textAlign: 'center' }}>
                    <span
                      style={{
                        display: 'inline-block',
                        width: 22,
                        height: 22,
                        borderRadius: '50%',
                        border: '1px solid var(--d-line)',
                      }}
                    />
                  </td>
                ))}
                <td style={{ padding: '15px 0' }} />
              </tr>
            ))}
          </tbody>
        </table>

        <div
          style={{
            marginTop: 22,
            padding: '14px 16px',
            border: '1px solid var(--d-line)',
            background: 'var(--d-paper-alt)',
          }}
        >
          <p style={{ fontSize: 12.5, fontWeight: 700, fontFamily: 'var(--d-display)', color: 'var(--d-accent)' }}>
            하루 연습은 이렇게
          </p>
          <div style={{ marginTop: 7, fontSize: 11.5, lineHeight: 1.95 }}>
            <p>· 처음부터 끝까지 한 번 — 틀려도 멈추지 않고</p>
            <p>· 어려운 곳만 천천히 다섯 번</p>
            <p>· 마지막에 다시 처음부터 한 번</p>
            <p>· 무대 인사까지 붙여서 한 번 (일주일에 두 번은)</p>
          </div>
        </div>

        <footer style={{ marginTop: 'auto', paddingTop: 14, textAlign: 'center', ...T.body(11) }}>
          매일 조금씩이 몰아서 하는 것보다 훨씬 낫습니다. 동그라미가 쌓이는 걸 아이가 봅니다.
        </footer>
      </div>
    </Sheet>
  )
}

/** 종료 후 안내문 — 사진 전달과 다음 행사 */
export function AfterNotice({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy, plan } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait">
      <div style={{ flex: 1, padding: '62px 62px 48px', display: 'flex', flexDirection: 'column' }}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ ...T.label(10) }}>{academy.name}</p>
          <h1 style={{ ...T.display(28), marginTop: 8 }}>{event.title}을 마치며</h1>
          <div style={{ marginTop: 12, display: 'flex', justifyContent: 'center' }}>
            <OrnamentDivider id={theme.ornament} width={190} />
          </div>
        </div>

        <p style={{ marginTop: 24, ...T.body(12.5), whiteSpace: 'pre-line' }}>
          {d.year}년 {d.month}월 {d.day}일, {plan.items.length}명의 아이들이 무대에 섰습니다.
          {'\n'}긴장한 손끝으로 끝까지 연주해 낸 아이들에게, 그리고 자리를 채워 주신 부모님께
          {'\n'}깊이 감사드립니다.
        </p>

        {[
          {
            title: '사진과 영상은 이렇게 받으십니다',
            lines: [
              '정리되는 대로 단톡방에 링크를 올려 드립니다 (보통 일주일 안).',
              '개별 사진이 필요하시면 아이 이름을 말씀해 주세요.',
              '다른 아이가 함께 나온 사진은 그 가정의 동의를 받고 전달합니다.',
            ],
          },
          {
            title: '오늘 아이에게 해 주실 말',
            lines: [
              '"끝까지 친 게 제일 멋있었어" — 결과보다 마친 것을 먼저 말해 주세요.',
              '잘한 점 하나를 구체적으로 짚어 주시면 다음 무대가 쉬워집니다.',
              '아쉬웠던 부분은 오늘 말고, 며칠 뒤에.',
            ],
          },
          {
            title: '다음 일정',
            lines: [
              '다음 주 수업은 예정대로 진행합니다.',
              '다음 무대와 시즌 특강 일정은 정해지는 대로 알려 드리겠습니다.',
            ],
          },
        ].map((section) => (
          <section key={section.title} style={{ marginTop: 18 }} className="print-avoid-break">
            <p style={{ ...T.label(9.5), color: 'var(--d-accent)' }}>{section.title}</p>
            <div style={{ marginTop: 7, fontSize: 12, lineHeight: 1.95 }}>
              {section.lines.map((line) => (
                <p key={line}>· {line}</p>
              ))}
            </div>
          </section>
        ))}

        <footer style={{ marginTop: 'auto', paddingTop: 14, borderTop: '1px solid var(--d-line)', textAlign: 'center' }}>
          <p style={{ ...T.display(14) }}>아이들이 오늘 하루를 오래 기억하기를 바랍니다.</p>
          <p style={{ marginTop: 6, ...T.body(11) }}>
            {academy.director_name} 원장 드림{copy.contact ? ` · ${copy.contact}` : ''}
          </p>
        </footer>
      </div>
    </Sheet>
  )
}
