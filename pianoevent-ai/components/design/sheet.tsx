import { OrnamentBackdrop, OrnamentCorner } from '@/components/design/ornaments'
import { PAGE_PX, type PageSize } from '@/lib/design/templates'
import { themeVars, type DesignTheme } from '@/lib/design/themes'

/** 테마 프레임 — 종이 가장자리 장식 */
function Frame({ theme }: { theme: DesignTheme }) {
  const corners = (
    <>
      <OrnamentCorner id={theme.ornament} position="tl" />
      <OrnamentCorner id={theme.ornament} position="tr" />
      <OrnamentCorner id={theme.ornament} position="bl" />
      <OrnamentCorner id={theme.ornament} position="br" />
    </>
  )

  switch (theme.frame) {
    case 'double':
      return (
        <div aria-hidden style={{ position: 'absolute', inset: 22, pointerEvents: 'none' }}>
          <div style={{ position: 'absolute', inset: 0, border: '2px solid var(--d-accent)', opacity: 0.75 }} />
          <div style={{ position: 'absolute', inset: 7, border: '0.7px solid var(--d-accent)', opacity: 0.45 }} />
          {corners}
        </div>
      )
    case 'thin':
      return (
        <div
          aria-hidden
          style={{ position: 'absolute', inset: 26, border: '1px solid var(--d-line)', pointerEvents: 'none' }}
        >
          {corners}
        </div>
      )
    case 'rounded':
      return (
        <div
          aria-hidden
          style={{
            position: 'absolute',
            inset: 22,
            border: '2.5px solid var(--d-accent-soft)',
            borderRadius: 28,
            pointerEvents: 'none',
          }}
        >
          {corners}
        </div>
      )
    case 'ribbon':
      return (
        <div aria-hidden style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
          <div style={{ position: 'absolute', insetInline: 0, top: 0, height: 14, background: 'var(--d-band)' }} />
          <div
            style={{ position: 'absolute', insetInline: 0, top: 14, height: 5, background: 'var(--d-accent)', opacity: 0.85 }}
          />
          <div style={{ position: 'absolute', inset: 34, border: '1px solid var(--d-line)' }} />
          {corners}
        </div>
      )
    case 'deco':
      return (
        <div aria-hidden style={{ position: 'absolute', inset: 24, pointerEvents: 'none' }}>
          {corners}
        </div>
      )
    default:
      return null
  }
}

function Texture({ theme }: { theme: DesignTheme }) {
  if (theme.texture === 'grain') {
    return (
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          opacity: 0.5,
          backgroundImage:
            'repeating-linear-gradient(0deg, color-mix(in srgb, var(--d-line) 14%, transparent) 0 1px, transparent 1px 4px)',
        }}
      />
    )
  }
  if (theme.texture === 'gradient') {
    return (
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background: 'linear-gradient(160deg, var(--d-paper-alt) 0%, transparent 55%)',
        }}
      />
    )
  }
  return null
}

/**
 * 한 장의 인쇄면.
 * 화면 미리보기와 인쇄가 같은 컴포넌트를 쓰고, 크기는 96dpi 기준 실제 A4 픽셀로 고정한다.
 */
export function Sheet({
  theme,
  page,
  children,
  decorated = true,
  flow = false,
}: {
  theme: DesignTheme
  page: PageSize
  children: React.ReactNode
  decorated?: boolean
  /**
   * 내용이 한 장을 넘칠 수 있는 문서(대본·명단·표)는 flow 로 둔다.
   * 포스터처럼 높이를 고정하면 학생이 많을 때 뒷부분이 그대로 잘려 나간다.
   * flow 면 종이가 세로로 늘어나고, 인쇄할 때 브라우저가 페이지를 나눈다.
   */
  flow?: boolean
}) {
  const size = PAGE_PX[page]

  return (
    <div
      className={flow ? 'd-sheet' : 'd-sheet print-avoid-break'}
      style={{
        ...themeVars(theme),
        width: size.w,
        height: flow ? 'auto' : size.h,
        minHeight: size.h,
        position: 'relative',
        overflow: flow ? 'visible' : 'hidden',
        background: 'var(--d-paper)',
        color: 'var(--d-ink)',
        fontFamily: 'var(--d-body)',
      }}
    >
      <Texture theme={theme} />
      <OrnamentBackdrop id={theme.ornament} />
      {decorated && <Frame theme={theme} />}
      <div
        style={{
          position: 'relative',
          width: '100%',
          height: flow ? 'auto' : '100%',
          minHeight: flow ? size.h : undefined,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {children}
      </div>
    </div>
  )
}

/** 제목·본문 공통 조판 유틸 */
export const type = {
  display: (size: number, weight = 700): React.CSSProperties => ({
    fontFamily: 'var(--d-display)',
    fontSize: size,
    fontWeight: weight,
    lineHeight: 1.18,
    letterSpacing: '-0.01em',
  }),
  label: (size = 12): React.CSSProperties => ({
    fontSize: size,
    letterSpacing: '0.32em',
    textTransform: 'uppercase',
    color: 'var(--d-muted)',
  }),
  body: (size = 14): React.CSSProperties => ({ fontSize: size, lineHeight: 1.7, color: 'var(--d-muted)' }),
}
