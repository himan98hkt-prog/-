import { LogoSlot } from '@/components/design/logo'
import { OrnamentDivider, TrebleClef } from '@/components/design/ornaments'
import { PhotoFrame } from '@/components/design/photo'
import { Sheet, type as T } from '@/components/design/sheet'
import { dateParts } from '@/components/design/templates/posters'
import type { DesignContext } from '@/lib/design/context'

/**
 * 타이포 포스터 — 사진도 장식도 없이 글자 크기만으로 지면을 잡는다.
 * 사진이 마땅치 않은 학원이 가장 자주 겪는 상황이라 별도 양식으로 둔다.
 */
export function PosterTypographic({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)
  const words = event.title.split(/\s+/).filter(Boolean)

  return (
    <Sheet theme={theme} page="a4-portrait">
      <div style={{ height: '100%', padding: '76px 68px 62px', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <div>
            <p style={{ ...T.label(11) }}>{academy.name}</p>
            {copy.subtitle && (
              <p style={{ marginTop: 8, fontSize: 15, color: 'var(--d-accent)', fontFamily: 'var(--d-display)' }}>
                {copy.subtitle}
              </p>
            )}
          </div>
          <LogoSlot ctx={ctx} align="start" height={theme.logo.height - 8} />
        </div>

        <div style={{ marginTop: 54 }}>
          {words.map((word, i) => (
            <div
              key={`${word}-${i}`}
              style={{
                ...T.display(words.length > 3 ? 62 : 78, 800),
                color: i % 2 === 1 ? 'var(--d-accent)' : 'var(--d-ink)',
                lineHeight: 1.06,
              }}
            >
              {word}
            </div>
          ))}
        </div>

        <div style={{ marginTop: 40, display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ height: 3, flex: 1, background: 'var(--d-accent)' }} />
          <TrebleClef size={22} opacity={0.8} />
        </div>

        <div style={{ marginTop: 'auto', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 26 }}>
          <div>
            <p style={{ ...T.label(10), marginBottom: 10 }}>일시</p>
            <p style={{ ...T.display(34), color: 'var(--d-accent)' }}>
              {d.month}.{d.day}
            </p>
            <p style={{ marginTop: 6, fontSize: 13, color: 'var(--d-muted)' }}>
              {d.year}년 {d.weekday}요일 {d.time}
            </p>
          </div>
          <div>
            <p style={{ ...T.label(10), marginBottom: 10 }}>장소</p>
            <p style={{ fontSize: 19, fontFamily: 'var(--d-display)', lineHeight: 1.4 }}>{event.venue || '학원 연주홀'}</p>
            {copy.contact && <p style={{ marginTop: 8, ...T.body(12) }}>{copy.contact}</p>}
          </div>
        </div>

        <p style={{ marginTop: 26, paddingTop: 16, borderTop: '1px solid var(--d-line)', ...T.body(11.5) }}>
          {copy.host}
          {copy.footnote ? ` · ${copy.footnote}` : ''}
        </p>
      </div>
    </Sheet>
  )
}

/** 사진 2단 포스터 — 위쪽 사진, 아래쪽 정보 두 칸 */
export function PosterDuo({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy, plan } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '40px 52px 22px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <p style={{ ...T.label(11) }}>{academy.name}</p>
          <LogoSlot ctx={ctx} align="start" height={theme.logo.height - 12} />
        </div>

        <div style={{ padding: '0 52px' }}>
          <PhotoFrame ctx={ctx} width={690} height={330} shape={theme.photo.shape === 'circle' ? 'rounded' : theme.photo.shape} />
        </div>

        <div style={{ padding: '30px 52px 0' }}>
          <h1 style={{ ...T.display(44) }}>{event.title}</h1>
          {copy.subtitle && (
            <p style={{ marginTop: 10, fontSize: 15, letterSpacing: '0.16em', color: 'var(--d-accent)' }}>{copy.subtitle}</p>
          )}
          <div style={{ marginTop: 18 }}>
            <OrnamentDivider id={theme.ornament} width={200} />
          </div>
        </div>

        <div
          style={{
            marginTop: 'auto',
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            borderTop: '1px solid var(--d-line)',
          }}
        >
          <div style={{ padding: '26px 52px 30px', borderRight: '1px solid var(--d-line)' }}>
            <p style={{ ...T.label(10), marginBottom: 10 }}>일시</p>
            <p style={{ ...T.display(30), color: 'var(--d-accent)' }}>
              {d.month}월 {d.day}일
            </p>
            <p style={{ marginTop: 6, fontSize: 13, color: 'var(--d-muted)' }}>
              {d.weekday}요일 {d.time}
            </p>
          </div>
          <div style={{ padding: '26px 52px 30px' }}>
            <p style={{ ...T.label(10), marginBottom: 10 }}>장소 · 출연</p>
            <p style={{ fontSize: 17, fontFamily: 'var(--d-display)' }}>{event.venue || '학원 연주홀'}</p>
            <p style={{ marginTop: 6, fontSize: 13, color: 'var(--d-muted)' }}>
              {plan.items.length > 0 ? `${plan.items.length}명의 어린 연주자` : '학원 학생 전원'}
            </p>
          </div>
        </div>

        <div
          style={{
            background: 'var(--d-band)',
            color: 'var(--d-band-ink)',
            padding: '14px 52px',
            fontSize: 11.5,
            display: 'flex',
            justifyContent: 'space-between',
          }}
        >
          <span>{copy.host}</span>
          <span>{copy.contact || academy.director_name}</span>
        </div>
      </div>
    </Sheet>
  )
}
