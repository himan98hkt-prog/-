import { OrnamentBackdrop, OrnamentDivider } from '@/components/design/ornaments'
import type { DesignTheme } from '@/lib/design/themes'
import { themeVars } from '@/lib/design/themes'
import { STAGE_SLIDE_H, STAGE_SLIDE_W, type StageSlide } from '@/lib/stage/deck'
import { StageBackdropView } from '@/components/stage/backdrops'
import { DEFAULT_STAGE_BACKDROP, type StageBackdrop } from '@/lib/stage/backdrops'
import {
  DEFAULT_PHOTO_SHAPE,
  DEFAULT_STAGE_LAYOUT,
  fallbackLayout,
  photoShapeInfo,
  PIANO_SAFE_BOTTOM,
  type PhotoShape,
  type StageLayout,
} from '@/lib/stage/layouts'

/**
 * 스크린 한 장 — 1280 × 720 (16:9) 고정.
 *
 * 이 컴포넌트 하나를 세 곳이 같이 쓴다.
 *   · 연주회 당일 전체화면 스크린
 *   · PDF 로 저장 (파워포인트 대신 USB 에 담아 가는 용도)
 *   · 상세페이지·미리보기 축소판
 * 세 곳이 같은 코드를 쓰므로 화면과 인쇄가 어긋나지 않는다.
 */
export function StageSlideView({
  slide,
  theme,
  academyName,
  dark = false,
  logoUrl = null,
  layout = DEFAULT_STAGE_LAYOUT,
  shape = DEFAULT_PHOTO_SHAPE,
  backdrop = DEFAULT_STAGE_BACKDROP,
}: {
  slide: StageSlide
  theme: DesignTheme
  academyName: string
  /** 어두운 공연장에서는 검은 배경이 눈에 편하다 */
  dark?: boolean
  logoUrl?: string | null
  /** 연주자 화면 모양 */
  layout?: StageLayout
  /** 아이 사진을 담는 창 모양 */
  shape?: PhotoShape
  /** 무대 배경 그림 */
  backdrop?: StageBackdrop
}) {
  const vars = themeVars(theme)
  // 어두운 화면은 종이색과 잉크색을 맞바꾼다 — 테마의 강조색은 그대로 살린다
  const palette: React.CSSProperties = dark
    ? {
        ...vars,
        ['--d-paper' as string]: theme.palette.ink,
        ['--d-paper-alt' as string]: theme.palette.ink,
        ['--d-ink' as string]: theme.palette.paper,
        ['--d-muted' as string]: theme.palette.paperAlt,
        ['--d-line' as string]: theme.palette.accentSoft,
      }
    : vars

  return (
    <div
      className="stage-slide"
      style={{
        ...palette,
        width: STAGE_SLIDE_W,
        height: STAGE_SLIDE_H,
        position: 'relative',
        overflow: 'hidden',
        background: 'var(--d-paper)',
        color: 'var(--d-ink)',
        fontFamily: 'var(--d-body)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div aria-hidden style={{ opacity: dark ? 0.35 : 1 }}>
        <OrnamentBackdrop id={theme.ornament} />
      </div>
      <StageBackdropView id={backdrop} theme={theme} dark={dark} />

      {/* 위·아래 얇은 띠 — 어느 슬라이드든 학원 것임을 알아보게 한다 */}
      <div aria-hidden style={{ position: 'absolute', insetInline: 0, top: 0, height: 8, background: 'var(--d-accent)' }} />
      <div
        aria-hidden
        style={{ position: 'absolute', insetInline: 0, bottom: 0, height: 3, background: 'var(--d-accent-soft)' }}
      />

      <Body slide={slide} theme={theme} dark={dark} logoUrl={logoUrl} layout={layout} shape={shape} />

      {/*
        연주자 화면에는 아래 줄을 두지 않는다 — 그랜드피아노 뚜껑이 가리는 자리라
        객석에서 읽히지 않고, 사진 위에 글자만 지저분하게 얹힌다.
        순서 번호는 화면 모양이 이미 위쪽에 크게 보여 준다.
      */}
      {slide.kind === 'performance' ? null : (
        <footer
          style={{
            position: 'absolute',
            insetInline: 0,
            bottom: 20,
            display: 'flex',
            justifyContent: 'space-between',
            padding: '0 56px',
            fontSize: 17,
            color: 'var(--d-muted)',
            letterSpacing: '0.06em',
          }}
        >
          <span>{academyName}</span>
          <span style={{ fontVariantNumeric: 'tabular-nums' }}>{slide.counter ?? ''}</span>
        </footer>
      )}
    </div>
  )
}

function Body({
  slide,
  theme,
  dark,
  logoUrl,
  layout,
  shape,
}: {
  slide: StageSlide
  theme: DesignTheme
  dark: boolean
  logoUrl: string | null
  layout: StageLayout
  shape: PhotoShape
}) {
  const center: React.CSSProperties = {
    position: 'relative',
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    textAlign: 'center',
    padding: '64px 88px 72px',
    gap: 0,
  }

  if (slide.kind === 'agenda' && slide.lines) {
    return (
      <div style={{ ...center, paddingTop: 44, paddingBottom: 56 }}>
        <p style={{ ...label(20), color: 'var(--d-accent)' }}>{slide.eyebrow}</p>
        <p style={{ marginTop: 8, fontSize: 22, color: 'var(--d-muted)' }}>{slide.title}</p>
        <div
          style={{
            marginTop: 26,
            width: '100%',
            display: 'grid',
            // 왼쪽 칸을 위에서 아래로 다 채운 뒤 오른쪽으로 넘어간다 — 순서지와 같은 읽기 방향
            gridAutoFlow: slide.lines.length > 6 ? 'column' : 'row',
            gridTemplateColumns: slide.lines.length > 6 ? '1fr 1fr' : '1fr',
            gridTemplateRows: slide.lines.length > 6 ? `repeat(${Math.ceil(slide.lines.length / 2)}, auto)` : undefined,
            columnGap: 44,
            rowGap: 2,
            textAlign: 'left',
          }}
        >
          {slide.lines.map((line) => (
            <div
              key={line.no}
              style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: 14,
                padding: '7px 0',
                borderBottom: '1px solid var(--d-line)',
              }}
            >
              <span
                style={{
                  width: 34,
                  flexShrink: 0,
                  fontVariantNumeric: 'tabular-nums',
                  fontWeight: 700,
                  color: 'var(--d-accent)',
                  fontSize: 22,
                }}
              >
                {line.no}
              </span>
              <span style={{ fontSize: 25, fontWeight: 700, whiteSpace: 'nowrap' }}>{line.name}</span>
              <span
                style={{
                  fontSize: 19,
                  color: 'var(--d-muted)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {line.piece}
              </span>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (slide.kind === 'performance') {
    const chosen = slide.photo ? layout : fallbackLayout(layout)
    return <Performance slide={slide} theme={theme} layout={chosen} dark={dark} shape={shape} />
  }

  if (slide.kind === 'section') {
    return (
      <div style={center}>
        <p style={{ ...label(22), color: 'var(--d-accent)' }}>{slide.eyebrow}</p>
        <h1
          style={{
            fontFamily: 'var(--d-display)',
            fontSize: 108,
            fontWeight: 700,
            lineHeight: 1.1,
            marginTop: 18,
          }}
        >
          {slide.title}
        </h1>
        <p style={{ marginTop: 22, fontSize: 30, color: 'var(--d-muted)' }}>{slide.subtitle}</p>
      </div>
    )
  }

  // standby · intermission · closing — 표지 성격의 화면
  return (
    <div style={center}>
      {logoUrl && slide.kind === 'standby' ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={logoUrl}
          alt=""
          style={{ height: 92, width: 'auto', objectFit: 'contain', marginBottom: 22, opacity: dark ? 0.92 : 1 }}
        />
      ) : null}
      <p style={{ ...label(22), color: 'var(--d-accent)' }}>{slide.eyebrow}</p>
      <h1
        style={{
          fontFamily: 'var(--d-display)',
          fontSize: slide.title.length > 14 ? 74 : 96,
          fontWeight: 700,
          lineHeight: 1.14,
          letterSpacing: '-0.02em',
          marginTop: 16,
        }}
      >
        {slide.title}
      </h1>
      {slide.subtitle ? <p style={{ marginTop: 18, fontSize: 30, color: 'var(--d-muted)' }}>{slide.subtitle}</p> : null}
      {slide.body ? (
        <p style={{ marginTop: 26, fontSize: 23, lineHeight: 1.8, color: 'var(--d-muted)', whiteSpace: 'pre-line' }}>
          {slide.body}
        </p>
      ) : null}
    </div>
  )
}

function label(size: number): React.CSSProperties {
  return { fontSize: size, letterSpacing: '0.14em', fontWeight: 600 }
}

/** 사진을 잘라 화면을 꽉 채운다 — 둘레에 빈 자리를 남기지 않는다 */
function Photo({ src, style }: { src: string; style?: React.CSSProperties }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt=""
      style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center 35%', display: 'block', ...style }}
    />
  )
}

/** 글자 뒤에 까는 그늘 — 사진 위에서도 이름이 읽히게 */
function scrim(strength = 0.82): string {
  return `linear-gradient(to left, rgba(0,0,0,${strength}) 0%, rgba(0,0,0,${strength * 0.84}) 42%, rgba(0,0,0,${strength * 0.5}) 72%, rgba(0,0,0,0) 100%)`
}

/**
 * 연주자 화면.
 *
 * 어느 모양이든 두 가지를 지킨다 — 사진은 꽉 채우고, 글자는 아래쪽
 * (피아노 뚜껑이 가리는 자리)에 놓지 않는다.
 */
function Performance({
  slide,
  theme,
  layout,
  dark,
  shape,
}: {
  slide: StageSlide
  theme: DesignTheme
  layout: StageLayout
  dark: boolean
  shape: PhotoShape
}) {
  const eyebrow = slide.eyebrow ?? ''
  const name = slide.title
  const piece = slide.subtitle ?? ''
  const note = slide.body
  const order = slide.counter?.split('/')[0]?.trim() ?? ''
  const safeBottom = STAGE_SLIDE_H * PIANO_SAFE_BOTTOM

  if (layout === 'photo-frame' && slide.photo) {
    const frame = photoShapeInfo(shape).css
    return (
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'grid',
          gridTemplateColumns: '480px 1fr',
          alignItems: 'center',
          gap: 52,
          padding: `40px 64px ${safeBottom * 0.8}px 64px`,
        }}
      >
        <div style={{ position: 'relative', width: 420, height: 420, justifySelf: 'center' }}>
          {/*
            액자는 테두리(border)가 아니라 **뒤에 깔린 같은 모양**이다.
            육각·마름모처럼 잘라 낸 모양은 테두리까지 잘려 나가 사라진다.
          */}
          <div
            aria-hidden
            style={{
              position: 'absolute',
              inset: -16,
              background: 'var(--d-accent)',
              opacity: 0.85,
              ...frame,
            }}
          />
          <div
            aria-hidden
            style={{
              position: 'absolute',
              inset: -8,
              background: 'var(--d-paper)',
              ...frame,
            }}
          />
          <div
            style={{
              position: 'relative',
              width: '100%',
              height: '100%',
              overflow: 'hidden',
              boxShadow: '0 20px 48px rgba(0,0,0,0.35)',
              background: 'var(--d-paper-alt)',
              ...frame,
            }}
          >
            <Photo src={slide.photo} />
          </div>
        </div>
        <div style={{ textAlign: 'left', minWidth: 0 }}>
          <p style={{ ...label(20), color: 'var(--d-accent)' }}>{eyebrow}</p>
          <h1 style={{ ...display(name.length > 7 ? 76 : 92), marginTop: 10 }}>{name}</h1>
          <div style={{ marginTop: 14 }}>
            <OrnamentDivider id={theme.ornament} width={260} />
          </div>
          <p style={{ marginTop: 14, fontSize: 34, fontWeight: 600, lineHeight: 1.3 }}>{piece}</p>
          {note ? <p style={{ ...noteStyle, marginTop: 14 }}>{note}</p> : null}
        </div>
      </div>
    )
  }

  if (layout === 'photo-side' && slide.photo) {
    return (
      <div style={{ position: 'absolute', inset: 0, display: 'grid', gridTemplateColumns: '54% 46%' }}>
        <div style={{ position: 'relative', overflow: 'hidden' }}>
          <Photo src={slide.photo} />
          <div aria-hidden style={{ position: 'absolute', inset: 0, boxShadow: 'inset -30px 0 60px -30px rgba(0,0,0,0.5)' }} />
        </div>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            padding: `40px 56px ${safeBottom * 0.7}px 44px`,
            gap: 0,
            background: 'var(--d-paper)',
          }}
        >
          <p style={{ ...label(20), color: 'var(--d-accent)' }}>{eyebrow}</p>
          <h1 style={{ ...display(name.length > 7 ? 74 : 88), marginTop: 10 }}>{name}</h1>
          <div style={{ marginTop: 12 }}>
            <OrnamentDivider id={theme.ornament} width={220} />
          </div>
          <p style={{ marginTop: 14, fontSize: 32, fontWeight: 600, lineHeight: 1.3 }}>{piece}</p>
          {note ? <p style={{ ...noteStyle, marginTop: 14 }}>{note}</p> : null}
        </div>
      </div>
    )
  }

  if (layout === 'photo-panel' && slide.photo) {
    return (
      <div style={{ position: 'absolute', inset: 0 }}>
        <Photo src={slide.photo} />
        <div aria-hidden style={{ position: 'absolute', inset: 0, background: scrim(0.86) }} />
        <div
          style={{
            position: 'absolute',
            top: 0,
            right: 0,
            width: 500,
            height: `${100 - PIANO_SAFE_BOTTOM * 100}%`,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            padding: '0 56px',
            color: '#fff',
          }}
        >
          <p style={{ ...label(20), color: theme.palette.accent }}>{eyebrow}</p>
          <h1 style={{ ...display(name.length > 7 ? 76 : 92), marginTop: 10, color: '#fff' }}>{name}</h1>
          <div style={{ marginTop: 12, height: 3, width: 200, background: theme.palette.accent }} />
          <p style={{ marginTop: 16, fontSize: 33, fontWeight: 600, lineHeight: 1.32 }}>{piece}</p>
          {note ? <p style={{ ...noteStyle, color: 'rgba(255,255,255,0.86)', marginTop: 14 }}>{note}</p> : null}
        </div>
      </div>
    )
  }

  if (layout === 'photo-band' && slide.photo) {
    return (
      <div style={{ position: 'absolute', inset: 0 }}>
        <Photo src={slide.photo} />
        <div
          aria-hidden
          style={{
            position: 'absolute',
            insetInline: 0,
            top: 0,
            height: 320,
            background:
              'linear-gradient(to bottom, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.86) 62%, rgba(0,0,0,0.6) 84%, rgba(0,0,0,0) 100%)',
          }}
        />
        <div style={{ position: 'absolute', insetInline: 0, top: 0, padding: '38px 72px 0', color: '#fff' }}>
          <p style={{ ...label(21), color: theme.palette.accent }}>{eyebrow}</p>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 26, marginTop: 8, flexWrap: 'wrap' }}>
            <h1 style={{ ...display(name.length > 7 ? 74 : 88), color: '#fff' }}>{name}</h1>
            <p style={{ fontSize: 34, fontWeight: 600, color: 'rgba(255,255,255,0.94)' }}>{piece}</p>
          </div>
          {note ? (
            <p style={{ ...noteStyle, color: 'rgba(255,255,255,0.82)', marginTop: 10, maxWidth: 1000 }}>{note}</p>
          ) : null}
        </div>
      </div>
    )
  }

  if (layout === 'photo-corner' && slide.photo) {
    return (
      <div style={{ position: 'absolute', inset: 0 }}>
        <Photo src={slide.photo} />
        <div
          aria-hidden
          style={{
            position: 'absolute',
            insetInline: 0,
            top: 0,
            height: 340,
            background:
              'linear-gradient(to bottom, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.8) 60%, rgba(0,0,0,0.5) 82%, rgba(0,0,0,0) 100%)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            left: 60,
            top: 34,
            lineHeight: 0.9,
            color: theme.palette.accent,
            fontFamily: 'var(--d-display)',
            fontWeight: 700,
            fontSize: 132,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {order}
        </div>
        <div style={{ position: 'absolute', right: 60, top: 40, textAlign: 'right', color: '#fff', maxWidth: 820 }}>
          <p style={{ ...label(19), color: theme.palette.accent }}>{eyebrow}</p>
          <h1 style={{ ...display(name.length > 7 ? 72 : 84), marginTop: 8, color: '#fff' }}>{name}</h1>
          <p style={{ marginTop: 10, fontSize: 32, fontWeight: 600 }}>{piece}</p>
          {note ? <p style={{ ...noteStyle, color: 'rgba(255,255,255,0.84)', marginTop: 10 }}>{note}</p> : null}
        </div>
      </div>
    )
  }

  if (layout === 'text-number') {
    return (
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'grid',
          gridTemplateColumns: '340px 1fr',
          alignItems: 'center',
          paddingBottom: safeBottom,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            // 강조색 블록 — 어두운 화면에서도 배경에 묻히지 않는다
            background: 'var(--d-accent)',
            color: 'var(--d-paper)',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--d-display)',
              fontWeight: 700,
              fontSize: 200,
              lineHeight: 1,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {order}
          </span>
        </div>
        <div style={{ padding: '0 72px' }}>
          <p style={{ ...label(21), color: 'var(--d-accent)' }}>{eyebrow}</p>
          <h1 style={{ ...display(name.length > 8 ? 88 : 104), marginTop: 10 }}>{name}</h1>
          <div style={{ marginTop: 14 }}>
            <OrnamentDivider id={theme.ornament} width={280} />
          </div>
          <p style={{ marginTop: 16, fontSize: 38, fontWeight: 600 }}>{piece}</p>
          {note ? <p style={{ ...noteStyle, marginTop: 14, maxWidth: 800 }}>{note}</p> : null}
        </div>
      </div>
    )
  }

  if (layout === 'text-card') {
    return (
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: `56px 90px ${safeBottom}px`,
        }}
      >
        <div
          style={{
            width: '100%',
            border: '3px solid var(--d-accent)',
            outline: '1px solid var(--d-line)',
            outlineOffset: 8,
            padding: '44px 60px',
            textAlign: 'center',
            background: dark ? 'rgba(255,255,255,0.07)' : 'var(--d-paper-alt)',
          }}
        >
          <p style={{ ...label(21), color: 'var(--d-accent)' }}>{eyebrow}</p>
          <h1 style={{ ...display(name.length > 8 ? 80 : 96), marginTop: 12 }}>{name}</h1>
          <div style={{ marginTop: 14, display: 'flex', justifyContent: 'center' }}>
            <OrnamentDivider id={theme.ornament} width={320} />
          </div>
          <p style={{ marginTop: 16, fontSize: 36, fontWeight: 600 }}>{piece}</p>
          {note ? <p style={{ ...noteStyle, marginTop: 16 }}>{note}</p> : null}
        </div>
      </div>
    )
  }

  // text-hero — 사진 없이 이름만 크게. 아래쪽은 비워 둔다
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: `48px 90px ${safeBottom}px`,
      }}
    >
      <p style={{ ...label(22), color: 'var(--d-accent)' }}>{eyebrow}</p>
      <h1 style={{ ...display(name.length > 8 ? 96 : 116), marginTop: 12 }}>{name}</h1>
      <div style={{ marginTop: 16 }}>
        <OrnamentDivider id={theme.ornament} width={360} />
      </div>
      <p style={{ marginTop: 16, fontSize: 40, fontWeight: 600, lineHeight: 1.3 }}>{piece}</p>
      {note ? <p style={{ ...noteStyle, marginTop: 18, maxWidth: 900 }}>{note}</p> : null}
    </div>
  )
}

function display(size: number): React.CSSProperties {
  return {
    fontFamily: 'var(--d-display)',
    fontSize: size,
    fontWeight: 700,
    lineHeight: 1.08,
    letterSpacing: '-0.02em',
    margin: 0,
  }
}

const noteStyle: React.CSSProperties = {
  fontSize: 22,
  lineHeight: 1.65,
  color: 'var(--d-muted)',
  display: '-webkit-box',
  WebkitLineClamp: 3,
  WebkitBoxOrient: 'vertical',
  overflow: 'hidden',
  margin: 0,
}
