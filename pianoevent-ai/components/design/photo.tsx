import type { DesignContext } from '@/lib/design/context'
import { PHOTO_FILTER, type PhotoShape } from '@/lib/design/themes'

function radiusFor(shape: PhotoShape, width: number, height: number): string {
  switch (shape) {
    case 'circle':
      return '50%'
    case 'rounded':
      return '18px'
    case 'arch':
      // 위쪽만 반원으로 — 무대 아치 느낌
      return `${Math.min(width, height * 1.2) / 2}px ${Math.min(width, height * 1.2) / 2}px 10px 10px`
    default:
      return '0'
  }
}

/**
 * 학원·행사 사진 자리.
 * 모양은 테마가 정하고(직각·라운드·원형·아치), 사진이 없으면 미리보기에서만 자리를 안내한다.
 */
export function PhotoFrame({
  ctx,
  width,
  height,
  shape,
}: {
  ctx: DesignContext
  width: number | string
  height: number
  /** 테마 기본 모양을 덮어쓰고 싶을 때 */
  shape?: PhotoShape
}) {
  const { theme, photoUrl, placeholder } = ctx
  const finalShape = shape ?? theme.photo.shape
  const numericWidth = typeof width === 'number' ? width : height
  const borderRadius = radiusFor(finalShape, numericWidth, height)

  if (!photoUrl) {
    if (!placeholder) return null
    return (
      <div
        aria-label="사진 자리"
        style={{
          width,
          height,
          borderRadius,
          border: '1px dashed var(--d-line)',
          background: 'var(--d-paper-alt)',
          color: 'var(--d-muted)',
          fontSize: 12,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          letterSpacing: '0.1em',
        }}
      >
        사진 자리
      </div>
    )
  }

  return (
    <div style={{ width, height, borderRadius, overflow: 'hidden', background: 'var(--d-paper-alt)' }}>
      {/* 외부 URL 이라 next/image 대신 img 로 그린다 */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={photoUrl}
        alt={`${ctx.academy.name} 사진`}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          display: 'block',
          filter: PHOTO_FILTER[theme.photo.treatment ?? 'natural'],
        }}
      />
    </div>
  )
}

/** 사진을 배경으로 깔고 글씨가 읽히도록 어둡게 덮는 층 */
export function PhotoBackdrop({ ctx, opacity = 0.55 }: { ctx: DesignContext; opacity?: number }) {
  if (!ctx.photoUrl) return null
  const filter = PHOTO_FILTER[ctx.theme.photo.treatment ?? 'natural']
  return (
    <div aria-hidden style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={ctx.photoUrl}
        alt=""
        style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block', filter }}
      />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: `linear-gradient(180deg,
            color-mix(in srgb, var(--d-paper) ${Math.round(opacity * 100)}%, transparent) 0%,
            color-mix(in srgb, var(--d-paper) ${Math.round(Math.min(1, opacity + 0.35) * 100)}%, transparent) 55%,
            var(--d-paper) 100%)`,
        }}
      />
    </div>
  )
}

/**
 * 전면 사진 — 지면을 사진이 가득 채우고, 글씨가 들어갈 아래쪽만 어둡게 덮는다.
 * 실제 촬영 사진을 쓸 때 가장 "진짜 포스터" 같아 보이는 방식이다.
 */
export function PhotoFullBleed({ ctx, scrim = 0.72 }: { ctx: DesignContext; scrim?: number }) {
  const { photoUrl, theme, academy } = ctx

  if (!photoUrl) {
    return (
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          background: `linear-gradient(160deg, var(--d-paper-alt) 0%, var(--d-accent-soft) 100%)`,
        }}
      />
    )
  }

  return (
    <div aria-hidden style={{ position: 'absolute', inset: 0 }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={photoUrl}
        alt={`${academy.name} 사진`}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          display: 'block',
          filter: PHOTO_FILTER[theme.photo.treatment ?? 'natural'],
        }}
      />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: `linear-gradient(180deg,
            rgba(0,0,0,0.34) 0%,
            rgba(0,0,0,0.06) 34%,
            rgba(0,0,0,${scrim * 0.62}) 68%,
            rgba(0,0,0,${scrim}) 100%)`,
        }}
      />
    </div>
  )
}
