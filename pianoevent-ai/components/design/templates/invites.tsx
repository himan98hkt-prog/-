import { LogoSlot } from '@/components/design/logo'
import { OrnamentDivider, TrebleClef } from '@/components/design/ornaments'
import { PhotoBackdrop, PhotoFrame } from '@/components/design/photo'
import { Sheet, type as T } from '@/components/design/sheet'
import { dateParts } from '@/components/design/templates/posters'
import type { DesignContext } from '@/lib/design/context'

/** 손으로 건네는 초대장. A4 한 장을 반으로 자르면 두 장이 나온다. */
export function InvitationCards({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  const card = (key: string) => (
    <div
      key={key}
      className="print-avoid-break"
      style={{
        height: '50%',
        padding: '40px 56px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
        borderBottom: key === 'top' ? '1px dashed var(--d-line)' : 'none',
        position: 'relative',
      }}
    >
      <LogoSlot ctx={ctx} height={theme.logo.height - 14} />
      <p style={{ ...T.label(9.5), marginTop: 10 }}>{academy.name}</p>

      <div style={{ marginTop: 14 }}>
        <TrebleClef size={18} opacity={0.85} />
      </div>

      <h2 style={{ ...T.display(27), marginTop: 12 }}>{event.title}</h2>
      {copy.subtitle && (
        <p style={{ marginTop: 7, fontSize: 11.5, letterSpacing: '0.18em', color: 'var(--d-muted)' }}>{copy.subtitle}</p>
      )}

      <div style={{ marginTop: 14 }}>
        <OrnamentDivider id={theme.ornament} width={160} />
      </div>

      <p style={{ marginTop: 16, ...T.display(20), color: 'var(--d-accent)' }}>
        {d.year}. {d.month}. {d.day} ({d.weekday}) {d.time}
      </p>
      {event.venue && <p style={{ marginTop: 7, fontSize: 13, fontFamily: 'var(--d-display)' }}>{event.venue}</p>}

      <p style={{ marginTop: 14, maxWidth: 460, ...T.body(10.5), whiteSpace: 'pre-line' }}>
        {event.greeting || '한 해 동안 아이들이 쌓아 온 시간을 들려드립니다. 귀한 걸음으로 함께해 주세요.'}
      </p>

      <div style={{ marginTop: 'auto', width: '100%', paddingTop: 12, borderTop: '0.5px solid var(--d-line)' }}>
        <p style={{ ...T.body(9.5) }}>
          {copy.host}
          {copy.contact ? ` · ${copy.contact}` : ''}
        </p>
        <p style={{ marginTop: 3, fontSize: 8.5, color: 'var(--d-muted)' }}>
          참석 회신 · {ctx.inviteUrl.replace(/^https?:\/\//, '')}
        </p>
      </div>
    </div>
  )

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        {card('top')}
        {card('bottom')}
      </div>
    </Sheet>
  )
}

/** 인스타그램·카카오 스토리용 9:16 세로 이미지 */
export function StoryCard({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="story" decorated={false}>
      <PhotoBackdrop ctx={ctx} opacity={0.22} />
      {/* 사진 위에 큰 글씨가 얹히므로 종이색 장막을 한 겹 깐다 */}
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'linear-gradient(180deg, var(--d-paper) 0%, color-mix(in srgb, var(--d-paper) 72%, transparent) 34%, color-mix(in srgb, var(--d-paper) 78%, transparent) 66%, var(--d-paper) 100%)',
        }}
      />
      <div
        style={{
          height: '100%',
          padding: '92px 64px 80px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          position: 'relative',
        }}
      >
        <LogoSlot ctx={ctx} height={theme.logo.height + 6} />
        <p style={{ ...T.label(13), marginTop: 18 }}>{academy.name}</p>

        <div style={{ marginTop: 44 }}>
          <TrebleClef size={38} opacity={0.9} />
        </div>

        <h1 style={{ ...T.display(58), marginTop: 34 }}>{event.title}</h1>
        {copy.subtitle && (
          <p style={{ marginTop: 16, fontSize: 20, letterSpacing: '0.2em', color: 'var(--d-muted)' }}>{copy.subtitle}</p>
        )}

        <div style={{ marginTop: 40 }}>
          <OrnamentDivider id={theme.ornament} width={280} />
        </div>

        <div style={{ marginTop: 52 }}>
          <div style={{ ...T.display(112, 800), color: 'var(--d-accent)', lineHeight: 1 }}>
            {d.month}.{d.day}
          </div>
          <p style={{ marginTop: 16, fontSize: 20, letterSpacing: '0.22em', color: 'var(--d-muted)' }}>
            {d.year} · {d.weekday}요일 {d.time}
          </p>
        </div>

        {event.venue && <p style={{ marginTop: 34, fontSize: 24, fontFamily: 'var(--d-display)' }}>{event.venue}</p>}

        <div
          style={{
            marginTop: 'auto',
            width: '100%',
            padding: '20px 0',
            borderRadius: 16,
            background: 'var(--d-accent-soft)',
          }}
        >
          <p style={{ fontSize: 17, fontWeight: 700 }}>참석 회신은 링크에서</p>
          <p style={{ marginTop: 6, fontSize: 14, color: 'var(--d-muted)' }}>
            {ctx.inviteUrl.replace(/^https?:\/\//, '')}
          </p>
        </div>
      </div>
    </Sheet>
  )
}

/** 입구에 세우는 X배너 시안 (1:3) */
export function BannerStand({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy, plan } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="banner" decorated={false}>
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', textAlign: 'center' }}>
        <div style={{ background: 'var(--d-band)', color: 'var(--d-band-ink)', padding: '46px 40px 40px' }}>
          <LogoSlot ctx={ctx} height={theme.logo.height + 10} />
          <p style={{ marginTop: 16, fontSize: 17, letterSpacing: '0.3em' }}>{academy.name}</p>
        </div>

        <div style={{ padding: '58px 44px 0' }}>
          <h1 style={{ ...T.display(56, 800), lineHeight: 1.12 }}>{event.title}</h1>
          {copy.subtitle && (
            <p style={{ marginTop: 20, fontSize: 20, letterSpacing: '0.2em', color: 'var(--d-accent)' }}>{copy.subtitle}</p>
          )}
          <div style={{ marginTop: 30, display: 'flex', justifyContent: 'center' }}>
            <OrnamentDivider id={theme.ornament} width={240} />
          </div>
        </div>

        <div style={{ padding: '48px 44px 0' }}>
          <PhotoFrame ctx={ctx} width={412} height={300} shape={theme.photo.shape === 'circle' ? 'rounded' : theme.photo.shape} />
        </div>

        <div style={{ marginTop: 'auto', padding: '0 44px 56px' }}>
          <div style={{ ...T.display(78, 800), color: 'var(--d-accent)', lineHeight: 1 }}>
            {d.month}.{d.day}
          </div>
          <p style={{ marginTop: 14, fontSize: 19, letterSpacing: '0.2em', color: 'var(--d-muted)' }}>
            {d.year} {d.weekday}요일 {d.time}
          </p>
          {event.venue && <p style={{ marginTop: 22, fontSize: 24, fontFamily: 'var(--d-display)' }}>{event.venue}</p>}
          <p style={{ marginTop: 26, paddingTop: 20, borderTop: '1px solid var(--d-line)', ...T.body(14) }}>
            {plan.items.length > 0 ? `${plan.items.length}명의 어린 연주자가 함께합니다` : copy.host}
          </p>
        </div>
      </div>
    </Sheet>
  )
}
