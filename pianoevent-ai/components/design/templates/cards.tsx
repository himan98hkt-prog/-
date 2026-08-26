import { OrnamentDivider, TrebleClef } from '@/components/design/ornaments'
import { Sheet, type as T } from '@/components/design/sheet'
import { dateParts } from '@/components/design/templates/posters'
import type { DesignContext } from '@/lib/design/context'
import { formatShortDate } from '@/lib/format'

/** 입장권 3매 — 절취선을 따라 자른다 */
export function TicketStrip({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <div style={{ height: '100%', padding: '46px 52px', display: 'flex', flexDirection: 'column', gap: 26 }}>
        {[0, 1, 2].map((index) => (
          <div
            key={index}
            style={{
              flex: 1,
              border: '1px dashed var(--d-line)',
              borderRadius: 10,
              display: 'grid',
              gridTemplateColumns: '1fr 128px',
              overflow: 'hidden',
              background: 'var(--d-paper-alt)',
            }}
          >
            <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column' }}>
              <p style={{ ...T.label(9.5) }}>{academy.name}</p>
              <h2 style={{ ...T.display(24), marginTop: 10 }}>{event.title}</h2>
              <p style={{ marginTop: 10, fontSize: 12.5, color: 'var(--d-muted)' }}>
                {d.year}. {d.month}. {d.day} ({d.weekday}) {d.time}
                {event.venue ? ` · ${event.venue}` : ''}
              </p>

              <div style={{ marginTop: 'auto', marginBottom: 14 }}>
                <OrnamentDivider id={theme.ornament} width={150} />
                <p style={{ marginTop: 10, fontSize: 11, color: 'var(--d-muted)' }}>{copy.footnote}</p>
              </div>

              <div style={{ display: 'flex', gap: 18, fontSize: 11, color: 'var(--d-muted)' }}>
                <span>학생 이름 ______________</span>
                <span>좌석 ________</span>
              </div>
            </div>

            <div
              style={{
                borderLeft: '1px dashed var(--d-line)',
                background: 'var(--d-band)',
                color: 'var(--d-band-ink)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6,
              }}
            >
              <span style={{ fontSize: 9.5, letterSpacing: '0.28em' }}>ADMIT ONE</span>
              <span style={{ ...T.display(30), color: 'var(--d-band-ink)' }}>{d.day}</span>
              <span style={{ fontSize: 10, opacity: 0.85 }}>
                {d.year}.{d.month}
              </span>
              <span style={{ fontSize: 9, opacity: 0.7, marginTop: 4 }}>NO. {String(index + 1).padStart(3, '0')}</span>
            </div>
          </div>
        ))}

        <p style={{ textAlign: 'center', fontSize: 10, color: 'var(--d-muted)' }}>{copy.contact || copy.host}</p>
      </div>
    </Sheet>
  )
}

/** 카카오톡·인스타그램용 정사각 카드 */
export function SocialCard({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy, inviteUrl } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="square" decorated={false}>
      <div
        style={{
          height: '100%',
          padding: 78,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <p style={{ ...T.label(13) }}>{academy.name}</p>
          <TrebleClef size={30} opacity={0.85} />
        </div>

        <div>
          <p style={{ fontSize: 20, letterSpacing: '0.2em', color: 'var(--d-accent)' }}>{copy.subtitle}</p>
          <h1 style={{ ...T.display(66), marginTop: 20 }}>{event.title}</h1>
          <div style={{ marginTop: 26 }}>
            <OrnamentDivider id={theme.ornament} width={260} />
          </div>
          <p style={{ marginTop: 30, fontSize: 27, fontFamily: 'var(--d-display)' }}>
            {d.year}. {d.month}. {d.day} ({d.weekday}) {d.time}
          </p>
          {event.venue && <p style={{ marginTop: 10, fontSize: 21, color: 'var(--d-muted)' }}>{event.venue}</p>}
        </div>

        <div
          style={{
            borderTop: '1px solid var(--d-line)',
            paddingTop: 20,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: 15,
            color: 'var(--d-muted)',
          }}
        >
          <span>{copy.host}</span>
          <span style={{ color: 'var(--d-accent)' }}>{inviteUrl ? '참석 회신은 링크에서' : copy.contact}</span>
        </div>
      </div>
    </Sheet>
  )
}

/** 연주 후 학부모에게 드리는 감사 카드 (A4 한 장에 2매) */
export function ThankYouCards({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event } = ctx

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        {[0, 1].map((index) => (
          <div
            key={index}
            style={{
              flex: 1,
              borderBottom: index === 0 ? '1px dashed var(--d-line)' : 'none',
              padding: '52px 74px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center',
            }}
          >
            <TrebleClef size={22} opacity={0.85} />
            <h2 style={{ ...T.display(26), marginTop: 20 }}>고맙습니다</h2>
            <div style={{ marginTop: 14 }}>
              <OrnamentDivider id={theme.ornament} width={160} />
            </div>
            <p style={{ marginTop: 22, ...T.body(13.5), maxWidth: 420 }}>
              오늘 무대에 오른 아이가 한 곡을 끝까지 마쳤습니다.
              <br />
              그 자리에 함께해 주셔서 고맙습니다.
              <br />
              다음 계절에도 아이의 소리를 함께 들어 주세요.
            </p>
            <p style={{ marginTop: 'auto', fontSize: 11, color: 'var(--d-muted)' }}>
              {event.title} · {formatShortDate(event.event_at)} · {academy.name}
            </p>
          </div>
        ))}
      </div>
    </Sheet>
  )
}

/** 참가 상장 — 학생 한 명당 한 장 */
export function Certificates({ ctx, limit }: { ctx: DesignContext; limit?: number }) {
  const { theme, academy, event, plan } = ctx
  const items = typeof limit === 'number' ? plan.items.slice(0, limit) : plan.items
  const d = dateParts(event.event_at)

  return (
    <>
      {items.map((item) => (
        <Sheet key={item.student.id} theme={theme} page="a4-landscape">
          <div
            style={{
              height: '100%',
              padding: '76px 110px 64px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center',
            }}
          >
            <p style={{ ...T.label(12) }}>{academy.name}</p>
            <h1 style={{ ...T.display(40), marginTop: 22, letterSpacing: '0.3em' }}>참 가 상</h1>

            <div style={{ marginTop: 18 }}>
              <OrnamentDivider id={theme.ornament} width={220} />
            </div>

            <p style={{ marginTop: 36, ...T.display(30) }}>{item.student.student_name}</p>

            <p style={{ marginTop: 26, ...T.body(15), maxWidth: 560, lineHeight: 2 }}>
              위 학생은 {d.year}년 {d.month}월 {d.day}일 열린 {event.title}에서
              <br />
              「{item.student.piece_title}」{item.student.composer ? ` (${item.student.composer})` : ''} 을(를) 끝까지
              연주하였기에
              <br />이 상장을 드립니다.
            </p>

            <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
              <p style={{ fontSize: 13, color: 'var(--d-muted)' }}>
                {d.year}년 {d.month}월 {d.day}일
              </p>
              <p style={{ fontSize: 16, fontFamily: 'var(--d-display)' }}>
                {academy.name} 원장 {academy.director_name}
              </p>
            </div>
          </div>
        </Sheet>
      ))}
    </>
  )
}

/** 좌석 이름표 — A4 한 장에 8개 */
export function NameTags({ ctx, limitSheets }: { ctx: DesignContext; limitSheets?: number }) {
  const { theme, event, plan } = ctx
  const PER_SHEET = 8
  const sheets: (typeof plan.items)[] = []
  for (let i = 0; i < plan.items.length; i += PER_SHEET) sheets.push(plan.items.slice(i, i + PER_SHEET))
  const visible = typeof limitSheets === 'number' ? sheets.slice(0, limitSheets) : sheets

  return (
    <>
      {visible.map((group, sheetIndex) => (
        <Sheet key={sheetIndex} theme={theme} page="a4-portrait" decorated={false}>
          <div
            style={{
              height: '100%',
              padding: 34,
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gridTemplateRows: 'repeat(4, 1fr)',
              gap: 12,
            }}
          >
            {Array.from({ length: PER_SHEET }, (_, index) => {
              const item = group[index]
              return (
                <div
                  key={index}
                  style={{
                    border: '1px dashed var(--d-line)',
                    borderRadius: 8,
                    padding: '16px 20px',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'center',
                    background: item ? 'var(--d-paper-alt)' : 'transparent',
                  }}
                >
                  {item && (
                    <>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                        <span style={{ ...T.display(28), color: 'var(--d-accent)' }}>{item.order_no}</span>
                        <span style={{ ...T.display(22) }}>{item.student.student_name}</span>
                      </div>
                      <p style={{ marginTop: 8, fontSize: 12, color: 'var(--d-muted)' }}>{item.student.piece_title}</p>
                      <p style={{ marginTop: 2, fontSize: 10.5, color: 'var(--d-muted)' }}>
                        {item.student.composer || event.title}
                      </p>
                    </>
                  )}
                </div>
              )
            })}
          </div>
        </Sheet>
      ))}
    </>
  )
}
