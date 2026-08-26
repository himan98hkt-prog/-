import type { DesignContext } from '@/lib/design/context'

/**
 * 학원 로고 자리.
 * 로고가 등록돼 있으면 테마가 정한 모양(원형·금테·플레이트)으로 앉히고,
 * 없으면 미리보기에서만 자리 안내를 보여 준다 — 인쇄물에는 빈 상자가 찍히지 않는다.
 */
export function LogoSlot({
  ctx,
  height,
  align = 'center',
}: {
  ctx: DesignContext
  /** 테마 기본값을 덮어쓰고 싶을 때 */
  height?: number
  align?: 'center' | 'start'
}) {
  const { theme, academy, logoUrl, placeholder } = ctx
  const h = height ?? theme.logo.height
  const shape = theme.logo.shape

  if (!logoUrl) {
    if (!placeholder) return null
    return (
      <div
        aria-label="로고 자리"
        style={{
          height: h,
          width: shape === 'plain' ? h * 2.2 : h,
          borderRadius: shape === 'plain' ? 6 : '50%',
          border: '1px dashed var(--d-line)',
          color: 'var(--d-muted)',
          fontSize: Math.max(9, h * 0.16),
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          alignSelf: align === 'center' ? 'center' : 'flex-start',
          letterSpacing: '0.1em',
        }}
      >
        로고 자리
      </div>
    )
  }

  const box: React.CSSProperties = {
    height: h,
    width: shape === 'plain' ? 'auto' : h,
    maxWidth: h * 2.4,
    objectFit: 'contain',
    alignSelf: align === 'center' ? 'center' : 'flex-start',
  }

  if (shape === 'plain') {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={logoUrl} alt={`${academy.name} 로고`} style={box} />
  }

  const wrapper: React.CSSProperties = {
    height: h,
    width: h,
    borderRadius: '50%',
    overflow: 'hidden',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: align === 'center' ? 'center' : 'flex-start',
    ...(shape === 'ring' ? { border: '1.5px solid var(--d-accent)', padding: 5 } : {}),
    ...(shape === 'plate' ? { background: 'var(--d-paper-alt)', padding: 7, border: '1px solid var(--d-line)' } : {}),
  }

  return (
    <div style={wrapper}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={logoUrl}
        alt={`${academy.name} 로고`}
        style={{ width: '100%', height: '100%', objectFit: 'contain', borderRadius: '50%' }}
      />
    </div>
  )
}
