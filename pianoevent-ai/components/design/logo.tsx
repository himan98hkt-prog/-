import { ArtOrnament } from '@/components/design/art-ornament'
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
  const { theme, academy, logoUrl } = ctx
  const h = height ?? theme.logo.height
  const shape = theme.logo.shape

  if (!logoUrl) {
    /*
     * 로고가 없는 학원이 많다. 예전에는 이 자리를 **비워** 두었다 — 인쇄물 맨 위가
     * 휑하게 비면 완성돼 보이지 않는다. 지금은 피아노 모노그램을 얹는다.
     * 색이 아니라 모양으로 쓰므로 테마 강조색을 그대로 입는다(남색 테마면 남색 표식).
     *
     * 미리보기와 인쇄물이 **같아야 한다.** 예전에는 미리보기에만 점선 상자를 보여 주고
     * 인쇄물에서는 빈자리로 두었는데, 뽑아 보시고서야 다르다는 것을 아셨다.
     * 학원 로고를 등록하시면 그것이 이 자리를 대신한다 — 표식은 조용히 물러난다.
     */
    return (
      <div style={{ alignSelf: align === 'center' ? 'center' : 'flex-start' }}>
        <ArtOrnament id="mark-piano" width={h} opacity={0.9} />
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
