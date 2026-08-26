import type { OrnamentId } from '@/lib/design/themes'

/**
 * 인쇄물 장식. 전부 직접 그린 인라인 SVG 라 외부 이미지·폰트 아이콘에 의존하지 않는다.
 * 색은 테마 CSS 변수(--d-accent, --d-line)를 따른다.
 */

/** 제목 아래 들어가는 가로 장식 */
export function OrnamentDivider({ id, width = 220 }: { id: OrnamentId; width?: number }) {
  const stroke = 'var(--d-accent)'

  if (id === 'none') return null

  if (id === 'keys') {
    return (
      <svg width={width} height="18" viewBox="0 0 220 18" fill="none" aria-hidden>
        <rect x="0.5" y="0.5" width="219" height="17" rx="1.5" stroke={stroke} strokeOpacity="0.5" />
        {Array.from({ length: 15 }, (_, i) => (
          <line key={i} x1={14.6 * (i + 1)} y1="0" x2={14.6 * (i + 1)} y2="18" stroke={stroke} strokeOpacity="0.35" />
        ))}
        {[0, 1, 3, 4, 5, 7, 8, 10, 11, 12].map((i) => (
          <rect key={i} x={14.6 * (i + 1) - 4} y="0" width="8" height="11" rx="1" fill={stroke} fillOpacity="0.75" />
        ))}
      </svg>
    )
  }

  if (id === 'floral') {
    return (
      <svg width={width} height="22" viewBox="0 0 220 22" fill="none" aria-hidden>
        <path d="M10 11h78M132 11h78" stroke={stroke} strokeOpacity="0.55" strokeLinecap="round" />
        <path d="M110 3c5 3 7 5 7 8s-2 5-7 8c-5-3-7-5-7-8s2-5 7-8Z" fill={stroke} fillOpacity="0.8" />
        <path d="M96 11c4-4 8-4 10 0-2 4-6 4-10 0ZM124 11c-4-4-8-4-10 0 2 4 6 4 10 0Z" fill={stroke} fillOpacity="0.55" />
        <circle cx="88" cy="11" r="2" fill={stroke} />
        <circle cx="132" cy="11" r="2" fill={stroke} />
      </svg>
    )
  }

  if (id === 'leaf') {
    return (
      <svg width={width} height="20" viewBox="0 0 220 20" fill="none" aria-hidden>
        <path d="M8 10h94M118 10h94" stroke={stroke} strokeOpacity="0.5" strokeLinecap="round" />
        <path d="M110 2c6 4 6 12 0 16-6-4-6-12 0-16Z" fill={stroke} fillOpacity="0.75" />
        <path d="M110 4v12" stroke="var(--d-paper)" strokeOpacity="0.6" strokeWidth="0.8" />
      </svg>
    )
  }

  if (id === 'stars') {
    return (
      <svg width={width} height="22" viewBox="0 0 220 22" fill="none" aria-hidden>
        <path d="M20 11h70M130 11h70" stroke={stroke} strokeOpacity="0.45" strokeLinecap="round" strokeDasharray="2 6" />
        <path d="M110 2l2.4 6.1 6.6.4-5.1 4.2 1.7 6.3-5.6-3.6-5.6 3.6 1.7-6.3-5.1-4.2 6.6-.4L110 2Z" fill={stroke} />
        <circle cx="96" cy="11" r="1.6" fill={stroke} fillOpacity="0.7" />
        <circle cx="124" cy="11" r="1.6" fill={stroke} fillOpacity="0.7" />
      </svg>
    )
  }

  if (id === 'spotlight' || id === 'wave') {
    return (
      <svg width={width} height="14" viewBox="0 0 220 14" fill="none" aria-hidden>
        <path
          d="M2 7c18-8 36 8 54 0s36-8 54 0 36 8 54 0 36-8 54 0"
          stroke={stroke}
          strokeOpacity="0.6"
          strokeLinecap="round"
        />
      </svg>
    )
  }

  if (id === 'foil') {
    return (
      <svg width={width} height="14" viewBox="0 0 220 14" fill="none" aria-hidden>
        <path d="M0 4h220M0 10h220" stroke={stroke} strokeOpacity="0.35" />
        <path d="M92 7h36" stroke={stroke} strokeWidth="1.6" />
        <path d="M110 1.5l2.2 4.1 4.6.8-3.3 3.3.8 4.6-4.3-2.2-4.3 2.2.8-4.6-3.3-3.3 4.6-.8L110 1.5Z" fill={stroke} />
      </svg>
    )
  }

  if (id === 'lyre') {
    return (
      <svg width={width} height="26" viewBox="0 0 220 26" fill="none" aria-hidden>
        <path d="M6 13h84M130 13h84" stroke={stroke} strokeOpacity="0.5" strokeLinecap="round" />
        <path
          d="M100 22c-3-6-4-11-3-15 1-4 4-6 7-6M120 22c3-6 4-11 3-15-1-4-4-6-7-6"
          stroke={stroke}
          strokeWidth="1.4"
          strokeLinecap="round"
        />
        <path d="M104 8h12M103 12h14M102 16h16" stroke={stroke} strokeOpacity="0.75" strokeWidth="0.9" />
        <path d="M100 22h20" stroke={stroke} strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    )
  }

  if (id === 'garland') {
    return (
      <svg width={width} height="22" viewBox="0 0 220 22" fill="none" aria-hidden>
        <path d="M78 11c8-8 20-8 32 0 12 8 24 8 32 0" stroke={stroke} strokeOpacity="0.6" strokeLinecap="round" />
        <path d="M12 11h60M148 11h60" stroke={stroke} strokeOpacity="0.4" strokeLinecap="round" />
        {[86, 100, 120, 134].map((x, i) => (
          <path
            key={x}
            d={`M${x} ${i % 2 ? 6 : 16}c4 2 4 6 0 8-4-2-4-6 0-8Z`}
            fill={stroke}
            fillOpacity="0.6"
          />
        ))}
      </svg>
    )
  }

  if (id === 'confetti') {
    return (
      <svg width={width} height="24" viewBox="0 0 220 24" fill="none" aria-hidden>
        <path d="M14 12h74M132 12h74" stroke={stroke} strokeOpacity="0.4" strokeLinecap="round" strokeDasharray="1 7" />
        <circle cx="96" cy="7" r="2" fill={stroke} fillOpacity="0.7" />
        <rect x="122" y="14" width="4" height="4" rx="1" fill={stroke} fillOpacity="0.55" transform="rotate(24 124 16)" />
        <path d="M106 5v10a4 4 0 1 1-2-3.4V7l8-2v8a4 4 0 1 1-2-3.4V3l-4 1V5Z" fill={stroke} />
      </svg>
    )
  }

  if (id === 'holly') {
    return (
      <svg width={width} height="22" viewBox="0 0 220 22" fill="none" aria-hidden>
        <path d="M10 11h86M124 11h86" stroke={stroke} strokeOpacity="0.5" strokeLinecap="round" />
        <path d="M104 11c0-5 3-8 6-8s6 3 6 8-3 8-6 8-6-3-6-8Z" fill={stroke} fillOpacity="0.8" />
        <circle cx="100" cy="11" r="2.2" fill={stroke} />
        <circle cx="120" cy="11" r="2.2" fill={stroke} />
      </svg>
    )
  }

  // moon / deco
  return (
    <svg width={width} height="16" viewBox="0 0 220 16" fill="none" aria-hidden>
      <path d="M4 8h88M128 8h88" stroke={stroke} strokeOpacity="0.5" strokeLinecap="round" />
      <path d="M110 1l3 5.6 6.2 1.4-6.2 1.4L110 15l-3-5.6L100.8 8l6.2-1.4L110 1Z" fill={stroke} />
    </svg>
  )
}

/** 모서리 장식 — 포스터·상장의 네 귀퉁이 */
export function OrnamentCorner({
  id,
  position,
  size = 96,
}: {
  id: OrnamentId
  position: 'tl' | 'tr' | 'bl' | 'br'
  size?: number
}) {
  if (id === 'none' || id === 'wave') return null

  const rotate = { tl: 0, tr: 90, br: 180, bl: 270 }[position]
  const pos = {
    tl: { top: 0, left: 0 },
    tr: { top: 0, right: 0 },
    bl: { bottom: 0, left: 0 },
    br: { bottom: 0, right: 0 },
  }[position]

  const stroke = 'var(--d-accent)'

  const art = () => {
    switch (id) {
      case 'floral':
        return (
          <>
            <path d="M6 42c0-20 16-36 36-36" stroke={stroke} strokeOpacity="0.6" fill="none" />
            <path d="M20 20c6-6 14-6 18 0-6 6-14 6-18 0Z" fill={stroke} fillOpacity="0.65" />
            <path d="M30 34c-6-6-6-14 0-18 6 6 6 14 0 18Z" fill={stroke} fillOpacity="0.45" />
            <circle cx="42" cy="6" r="2.4" fill={stroke} />
          </>
        )
      case 'leaf':
        return (
          <>
            <path d="M8 48C8 24 24 8 48 8" stroke={stroke} strokeOpacity="0.55" fill="none" />
            <path d="M22 30c8-2 12-8 12-16-8 2-13 8-12 16Z" fill={stroke} fillOpacity="0.6" />
            <path d="M34 40c8-2 12-8 12-16-8 2-13 8-12 16Z" fill={stroke} fillOpacity="0.4" />
          </>
        )
      case 'stars':
        return (
          <>
            <circle cx="14" cy="14" r="2.4" fill={stroke} />
            <circle cx="34" cy="10" r="1.6" fill={stroke} fillOpacity="0.7" />
            <circle cx="10" cy="34" r="1.6" fill={stroke} fillOpacity="0.7" />
            <path d="M30 26l1.7 4.3 4.6.3-3.6 2.9 1.2 4.4-3.9-2.5-3.9 2.5 1.2-4.4-3.6-2.9 4.6-.3L30 26Z" fill={stroke} fillOpacity="0.55" />
          </>
        )
      case 'holly':
        return (
          <>
            <path d="M10 44C10 24 24 10 44 10" stroke={stroke} strokeOpacity="0.5" fill="none" />
            <path d="M24 26c0-6 4-10 8-10s8 4 8 10-4 10-8 10-8-4-8-10Z" fill={stroke} fillOpacity="0.7" />
            <circle cx="20" cy="34" r="2.6" fill={stroke} />
            <circle cx="42" cy="20" r="2.6" fill={stroke} />
          </>
        )
      case 'foil':
        return (
          <>
            <path d="M8 52V8h44" stroke={stroke} strokeOpacity="0.9" fill="none" />
            <path d="M13 52V13h39" stroke={stroke} strokeOpacity="0.45" fill="none" />
            <circle cx="8" cy="8" r="2.6" fill={stroke} />
            <circle cx="52" cy="8" r="1.6" fill={stroke} fillOpacity="0.6" />
            <circle cx="8" cy="52" r="1.6" fill={stroke} fillOpacity="0.6" />
          </>
        )
      case 'lyre':
        return (
          <>
            <path d="M10 50C10 26 26 10 50 10" stroke={stroke} strokeOpacity="0.55" fill="none" />
            <path d="M22 34c-2-6-1-11 3-14 4-3 8-2 10 1" stroke={stroke} strokeWidth="1.2" fill="none" />
            <path d="M24 26h12M23 30h14" stroke={stroke} strokeOpacity="0.7" strokeWidth="0.8" />
          </>
        )
      case 'garland':
        return (
          <>
            <path d="M8 46C8 24 24 8 46 8" stroke={stroke} strokeOpacity="0.5" fill="none" />
            {[
              [20, 30],
              [30, 20],
              [40, 13],
            ].map(([x, y]) => (
              <path key={`${x}-${y}`} d={`M${x} ${y}c5 2 5 7 0 9-5-2-5-7 0-9Z`} fill={stroke} fillOpacity="0.55" />
            ))}
          </>
        )
      case 'confetti':
        return (
          <>
            <circle cx="14" cy="16" r="2.6" fill={stroke} fillOpacity="0.8" />
            <rect x="30" y="10" width="5" height="5" rx="1" fill={stroke} fillOpacity="0.55" transform="rotate(20 32 12)" />
            <circle cx="12" cy="36" r="1.8" fill={stroke} fillOpacity="0.5" />
            <path d="M40 24v10a3 3 0 1 1-1.6-2.6V26l6-1.4V33a3 3 0 1 1-1.6-2.6v-7L40 24Z" fill={stroke} fillOpacity="0.7" />
          </>
        )
      case 'moon':
        return (
          <>
            <path d="M18 8a14 14 0 1 0 14 14A11 11 0 0 1 18 8Z" fill={stroke} fillOpacity="0.85" />
            <circle cx="42" cy="12" r="1.8" fill={stroke} fillOpacity="0.7" />
            <circle cx="12" cy="40" r="1.4" fill={stroke} fillOpacity="0.6" />
          </>
        )
      case 'keys':
        return (
          <>
            <rect x="6" y="6" width="46" height="14" rx="1.5" stroke={stroke} strokeOpacity="0.55" fill="none" />
            {[0, 1, 2, 3].map((i) => (
              <rect key={i} x={12 + i * 10} y="6" width="6" height="9" fill={stroke} fillOpacity="0.7" />
            ))}
            <path d="M6 26v26" stroke={stroke} strokeOpacity="0.4" />
          </>
        )
      default:
        // deco — 아르데코 계단선
        return (
          <>
            <path d="M6 54V6h48" stroke={stroke} strokeOpacity="0.85" fill="none" />
            <path d="M14 54V14h40" stroke={stroke} strokeOpacity="0.5" fill="none" />
            <path d="M22 54V22h32" stroke={stroke} strokeOpacity="0.28" fill="none" />
            <circle cx="6" cy="6" r="3" fill={stroke} />
          </>
        )
    }
  }

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 60 60"
      fill="none"
      aria-hidden
      style={{ position: 'absolute', ...pos, transform: `rotate(${rotate}deg)`, pointerEvents: 'none' }}
    >
      {art()}
    </svg>
  )
}

/** 배경 연출 — 스포트라이트·별가루 등 전면 효과 */
export function OrnamentBackdrop({ id }: { id: OrnamentId }) {
  if (id === 'spotlight') {
    return (
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'radial-gradient(120% 55% at 50% -8%, color-mix(in srgb, var(--d-accent) 28%, transparent) 0%, transparent 62%)',
        }}
      />
    )
  }

  if (id === 'moon') {
    return (
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'radial-gradient(80% 40% at 80% 8%, color-mix(in srgb, var(--d-accent) 22%, transparent) 0%, transparent 60%)',
        }}
      />
    )
  }

  if (id === 'stars') {
    return (
      <svg aria-hidden style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} width="100%" height="100%">
        <defs>
          <pattern id="d-stars" width="64" height="64" patternUnits="userSpaceOnUse">
            <circle cx="12" cy="18" r="1.6" fill="var(--d-accent)" fillOpacity="0.22" />
            <circle cx="46" cy="44" r="1.1" fill="var(--d-accent)" fillOpacity="0.16" />
            <circle cx="30" cy="8" r="0.9" fill="var(--d-accent)" fillOpacity="0.14" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#d-stars)" />
      </svg>
    )
  }

  return null
}

/** 음자리표 — 표지·카드의 중심 심볼 */
export function TrebleClef({ size = 64, opacity = 1 }: { size?: number; opacity?: number }) {
  return (
    <svg width={size} height={size * 2.1} viewBox="0 0 34 72" fill="none" aria-hidden style={{ opacity }}>
      <path
        d="M18.6 71c-6.4 0-10.6-3.4-10.6-8 0-3.6 2.5-6.2 6-6.2 3.1 0 5.4 2.2 5.4 5.1 0 2.7-1.9 4.6-4.4 4.6-.6 0-1.2-.1-1.7-.4 1 1.7 3 2.7 5.4 2.7 4.3 0 7.2-2.9 6.4-8.2L21 42.4C13.4 39.7 8 33.4 8 26.2 8 18.4 12.9 11.5 18 4.6 19.4 2.7 20.4 1 21.6 1c1.6 0 3.1 4.4 3.1 9.5 0 7.4-3.4 13.2-8.4 19.6l1.4 8.2c6.9.4 11.9 5.2 11.9 11.8 0 5.6-3.6 10-8.9 11.3l.9 5.4c1.2 7.2-3.1 11.2-9 11.2h-.1Zm3.9-21.4 2.6 15.2c3.5-1.2 5.7-4.3 5.7-8.2 0-4.4-3.2-7.7-8.3-7Zm-2.2-13c-5.5.2-9.3 4.4-9.3 10 0 4.9 3.1 9.3 8.1 11.5l-2.9-16.9c-.2-1.3-.4-2.6-.4-3.8v-.8Zm1.1-33.2c-3.6 4.5-6.4 9.1-6.4 14.6 0 3 .8 5.6 2.3 7.9 4.1-5.3 6.7-10.2 6.7-15.9 0-3.6-.9-6.6-2.6-6.6Z"
        fill="var(--d-accent)"
      />
    </svg>
  )
}
