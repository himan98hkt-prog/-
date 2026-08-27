import { OrnamentBackdrop, OrnamentDivider } from '@/components/design/ornaments'
import type { DesignTheme } from '@/lib/design/themes'
import { themeVars } from '@/lib/design/themes'
import { STAGE_SLIDE_H, STAGE_SLIDE_W, type StageSlide } from '@/lib/stage/deck'

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
}: {
  slide: StageSlide
  theme: DesignTheme
  academyName: string
  /** 어두운 공연장에서는 검은 배경이 눈에 편하다 */
  dark?: boolean
  logoUrl?: string | null
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

      {/* 위·아래 얇은 띠 — 어느 슬라이드든 학원 것임을 알아보게 한다 */}
      <div aria-hidden style={{ position: 'absolute', insetInline: 0, top: 0, height: 8, background: 'var(--d-accent)' }} />
      <div
        aria-hidden
        style={{ position: 'absolute', insetInline: 0, bottom: 0, height: 3, background: 'var(--d-accent-soft)' }}
      />

      <Body slide={slide} theme={theme} dark={dark} logoUrl={logoUrl} />

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
    </div>
  )
}

function Body({
  slide,
  theme,
  dark,
  logoUrl,
}: {
  slide: StageSlide
  theme: DesignTheme
  dark: boolean
  logoUrl: string | null
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
    // 사진이 있으면 왼쪽에 얼굴, 오른쪽에 이름 — 없으면 가운데 정렬 그대로
    if (slide.photo) {
      return (
        <div
          style={{
            position: 'relative',
            flex: 1,
            display: 'grid',
            gridTemplateColumns: '440px 1fr',
            alignItems: 'center',
            gap: 56,
            padding: '56px 80px 72px',
          }}
        >
          <div
            style={{
              width: 440,
              height: 440,
              borderRadius: theme.photo.shape === 'circle' ? '50%' : theme.photo.shape === 'rect' ? 0 : 28,
              overflow: 'hidden',
              border: '6px solid var(--d-accent-soft)',
              boxShadow: '0 18px 44px rgba(0,0,0,0.28)',
              background: 'var(--d-paper-alt)',
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={slide.photo}
              alt=""
              style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
            />
          </div>
          <div style={{ textAlign: 'left', minWidth: 0 }}>
            <p style={{ ...label(21), color: 'var(--d-accent)' }}>{slide.eyebrow}</p>
            <h1
              style={{
                fontFamily: 'var(--d-display)',
                fontSize: slide.title.length > 8 ? 76 : 94,
                fontWeight: 700,
                lineHeight: 1.1,
                letterSpacing: '-0.02em',
                marginTop: 12,
              }}
            >
              {slide.title}
            </h1>
            <div style={{ marginTop: 14 }}>
              <OrnamentDivider id={theme.ornament} width={280} />
            </div>
            <p style={{ marginTop: 14, fontSize: 34, fontWeight: 600, lineHeight: 1.3 }}>{slide.subtitle}</p>
            {slide.body ? (
              <p
                style={{
                  marginTop: 18,
                  fontSize: 22,
                  lineHeight: 1.7,
                  color: 'var(--d-muted)',
                  display: '-webkit-box',
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                }}
              >
                {slide.body}
              </p>
            ) : null}
          </div>
        </div>
      )
    }

    return (
      <div style={center}>
        <p style={{ ...label(21), color: 'var(--d-accent)' }}>{slide.eyebrow}</p>
        <h1
          style={{
            fontFamily: 'var(--d-display)',
            fontSize: slide.title.length > 8 ? 84 : 104,
            fontWeight: 700,
            lineHeight: 1.1,
            letterSpacing: '-0.02em',
            marginTop: 14,
          }}
        >
          {slide.title}
        </h1>
        <div style={{ marginTop: 16 }}>
          <OrnamentDivider id={theme.ornament} width={340} />
        </div>
        <p style={{ marginTop: 16, fontSize: 38, fontWeight: 600, lineHeight: 1.3 }}>{slide.subtitle}</p>
        {slide.body ? (
          <p
            style={{
              marginTop: 20,
              fontSize: 23,
              lineHeight: 1.75,
              color: 'var(--d-muted)',
              maxWidth: 880,
              display: '-webkit-box',
              WebkitLineClamp: 3,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {slide.body}
          </p>
        ) : null}
      </div>
    )
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
