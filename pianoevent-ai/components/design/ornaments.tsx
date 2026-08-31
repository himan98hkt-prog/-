import { ArtOrnament } from '@/components/design/art-ornament'
import type { OrnamentId } from '@/lib/design/themes'

/**
 * 인쇄물 장식. 전부 직접 그린 인라인 SVG 라 외부 이미지·폰트 아이콘에 의존하지 않는다.
 * 색은 테마 CSS 변수(--d-accent, --d-line)를 따른다.
 */

/** 제목 아래 들어가는 가로 장식 */
/**
 * 밖에서 만들어 넣은 금박 그림을 쓰는 장식.
 *
 * 손으로 그린 SVG 보다 훨씬 곱다. 색이 아니라 **모양**으로 쓰므로(`ArtOrnament`)
 * 테마 강조색을 그대로 입는다 — 남색 테마에서는 남색 구분선이 된다.
 */
const ART_DIVIDER: Partial<Record<OrnamentId, { id: string; ratio: number }>> = {
  foil: { id: 'divider', ratio: 0.3 },
  // 정사각 그림은 세로가 크기를 정한다. 크게 잡았더니 높은음자리표가 242px 로 나와
  // 종이를 차지하고 아래쪽 것은 잘려 나갔다 — 장식은 글을 받쳐야지 밀어내면 안 된다
  lyre: { id: 'clef', ratio: 0.4 },
  keys: { id: 'piano-mark', ratio: 0.4 },
}

export function OrnamentDivider({ id, width = 220 }: { id: OrnamentId; width?: number }) {
  const stroke = 'var(--d-accent)'

  if (id === 'none') return null

  const art = ART_DIVIDER[id]
  if (art) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <ArtOrnament id={art.id} width={width} height={Math.round(width * art.ratio)} opacity={0.9} />
      </div>
    )
  }

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

  if (id === 'cherry') {
    return (
      <svg width={width} height="24" viewBox="0 0 220 24" fill="none" aria-hidden>
        <path d="M12 12h82M126 12h82" stroke={stroke} strokeOpacity="0.45" strokeLinecap="round" />
        <g transform="translate(110 12)">
          {[0, 72, 144, 216, 288].map((a) => (
            <ellipse key={a} cx="0" cy="-5.4" rx="3.1" ry="5.2" fill={stroke} fillOpacity="0.72" transform={`rotate(${a})`} />
          ))}
          <circle r="1.7" fill={stroke} />
        </g>
        <circle cx="98" cy="8" r="1.3" fill={stroke} fillOpacity="0.5" />
        <circle cx="122" cy="16" r="1.3" fill={stroke} fillOpacity="0.5" />
      </svg>
    )
  }

  if (id === 'snow') {
    return (
      <svg width={width} height="22" viewBox="0 0 220 22" fill="none" aria-hidden>
        <path d="M14 11h82M124 11h82" stroke={stroke} strokeOpacity="0.4" strokeLinecap="round" strokeDasharray="1 5" />
        <g transform="translate(110 11)" stroke={stroke} strokeLinecap="round">
          {[0, 60, 120].map((a) => (
            <line key={a} x1="-8.5" y1="0" x2="8.5" y2="0" strokeWidth="1.1" transform={`rotate(${a})`} />
          ))}
          {[0, 60, 120, 180, 240, 300].map((a) => (
            <path key={a} d="M5.4 0l2.4-2.4M5.4 0l2.4 2.4" strokeWidth="0.8" strokeOpacity="0.85" transform={`rotate(${a})`} />
          ))}
        </g>
      </svg>
    )
  }

  if (id === 'maple') {
    return (
      <svg width={width} height="24" viewBox="0 0 220 24" fill="none" aria-hidden>
        <path d="M12 12h84M124 12h84" stroke={stroke} strokeOpacity="0.45" strokeLinecap="round" />
        <g transform="translate(110 12)">
          <path
            d="M0-9l3.1 5.6 5.6-1.4-2.4 4.6 5.1 1.1-4.6 3.1 2 3.4-5.3-.8L2.7 9 0 5.6-2.7 9l-.8-2.4-5.3.8 2-3.4-4.6-3.1 5.1-1.1-2.4-4.6 5.6 1.4L0-9Z"
            fill={stroke}
            fillOpacity="0.8"
          />
          <path d="M0 5.6V11" stroke={stroke} strokeWidth="0.9" strokeLinecap="round" />
        </g>
      </svg>
    )
  }

  if (id === 'ribbon') {
    return (
      <svg width={width} height="22" viewBox="0 0 220 22" fill="none" aria-hidden>
        <path d="M10 11h86M124 11h86" stroke={stroke} strokeOpacity="0.45" strokeLinecap="round" />
        <g transform="translate(110 10)">
          <path d="M-1.4 0C-4-4-8.5-5-10.5-2.6-12.3-.4-9.8 2.6-5.4 3l4-1.6Z" fill={stroke} fillOpacity="0.78" />
          <path d="M1.4 0C4-4 8.5-5 10.5-2.6 12.3-.4 9.8 2.6 5.4 3l-4-1.6Z" fill={stroke} fillOpacity="0.78" />
          <path d="M-2.6 2.4-6 9.4M2.6 2.4 6 9.4" stroke={stroke} strokeOpacity="0.6" strokeLinecap="round" />
          <circle cy="0.6" r="2" fill={stroke} />
        </g>
      </svg>
    )
  }

  if (id === 'heart') {
    return (
      <svg width={width} height="22" viewBox="0 0 220 22" fill="none" aria-hidden>
        <path d="M14 11h80M126 11h80" stroke={stroke} strokeOpacity="0.4" strokeLinecap="round" strokeDasharray="2 5" />
        <path
          d="M110 17c-8-5.4-8-11.4-3.6-12.4 2.2-.5 3.6 1 3.6 2.2 0-1.2 1.4-2.7 3.6-2.2C118 5.6 118 11.6 110 17Z"
          fill={stroke}
          fillOpacity="0.85"
        />
        <path d="M98 11c1.8-2.4 4-2.4 5.4 0-1.8 2.4-4 2.4-5.4 0ZM122 11c-1.8-2.4-4-2.4-5.4 0 1.8 2.4 4 2.4 5.4 0Z" fill={stroke} fillOpacity="0.45" />
      </svg>
    )
  }

  if (id === 'pearl') {
    return (
      <svg width={width} height="16" viewBox="0 0 220 16" fill="none" aria-hidden>
        <path d="M0 8h72M148 8h72" stroke={stroke} strokeOpacity="0.28" />
        {[78, 88, 98, 110, 122, 132, 142].map((x, i) => (
          <circle key={x} cx={x} cy="8" r={i === 3 ? 3.4 : 3.4 - Math.abs(i - 3) * 0.7} fill={stroke} fillOpacity={0.85 - Math.abs(i - 3) * 0.14} />
        ))}
      </svg>
    )
  }

  if (id === 'sun') {
    return (
      <svg width={width} height="24" viewBox="0 0 220 24" fill="none" aria-hidden>
        <path d="M6 12c16-6 32 6 48 0s32-6 48 0" stroke={stroke} strokeOpacity="0.45" strokeLinecap="round" />
        <path d="M118 12c16-6 32 6 48 0s32-6 48 0" stroke={stroke} strokeOpacity="0.45" strokeLinecap="round" />
        <g transform="translate(110 12)">
          <circle r="4.4" fill={stroke} fillOpacity="0.85" />
          {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
            <line key={a} x1="0" y1="-7" x2="0" y2="-9.6" stroke={stroke} strokeWidth="1.2" strokeLinecap="round" transform={`rotate(${a})`} />
          ))}
        </g>
      </svg>
    )
  }

  if (id === 'candle') {
    return (
      <svg width={width} height="26" viewBox="0 0 220 26" fill="none" aria-hidden>
        <path d="M10 18h88M122 18h88" stroke={stroke} strokeOpacity="0.4" strokeLinecap="round" />
        <g transform="translate(110 0)">
          <path d="M0 3c3 3.4 4.4 5.6 4.4 7.8 0 2.6-2 4.4-4.4 4.4s-4.4-1.8-4.4-4.4C-4.4 8.6-3 6.4 0 3Z" fill={stroke} fillOpacity="0.85" />
          <path d="M0 7.4c1.2 1.6 1.8 2.6 1.8 3.6 0 1.2-.8 2-1.8 2s-1.8-.8-1.8-2c0-1 .6-2 1.8-3.6Z" fill="var(--d-paper)" fillOpacity="0.55" />
          <rect x="-3" y="16.4" width="6" height="9" rx="1" fill={stroke} fillOpacity="0.55" />
        </g>
      </svg>
    )
  }

  if (id === 'ivy') {
    return (
      <svg width={width} height="22" viewBox="0 0 220 22" fill="none" aria-hidden>
        <path d="M6 11c14 0 14-6 28-6s14 6 28 6 14-6 28-6" stroke={stroke} strokeOpacity="0.45" fill="none" strokeLinecap="round" />
        <path d="M124 11c14 0 14-6 28-6s14 6 28 6 14-6 28-6" stroke={stroke} strokeOpacity="0.45" fill="none" strokeLinecap="round" />
        {[[100, 8], [110, 14], [120, 8]].map(([x, y]) => (
          <path key={`${x}-${y}`} d={`M${x} ${y}c5-1.6 7.4-5 7.4-9.6-4.8 1-7.8 4.4-7.4 9.6Z`} fill={stroke} fillOpacity="0.6" />
        ))}
      </svg>
    )
  }

  if (id === 'note') {
    return (
      <svg width={width} height="24" viewBox="0 0 220 24" fill="none" aria-hidden>
        <path d="M8 12h88M124 12h88" stroke={stroke} strokeOpacity="0.35" strokeLinecap="round" />
        <path
          d="M104 6.6v9.8a3.4 3.4 0 1 1-1.8-3V4.4l14-3.4v11a3.4 3.4 0 1 1-1.8-3V3.6l-10.4 3Z"
          fill={stroke}
          fillOpacity="0.9"
        />
      </svg>
    )
  }

  if (id === 'arch') {
    return (
      <svg width={width} height="22" viewBox="0 0 220 22" fill="none" aria-hidden>
        <path d="M4 18h84M132 18h84" stroke={stroke} strokeOpacity="0.4" strokeLinecap="round" />
        <path d="M96 18V11a14 14 0 0 1 28 0v7" stroke={stroke} strokeWidth="1.3" fill="none" />
        <path d="M100 18v-7a10 10 0 0 1 20 0v7" stroke={stroke} strokeOpacity="0.4" fill="none" />
        <path d="M92 18h36" stroke={stroke} strokeWidth="1.6" strokeLinecap="round" />
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
  // 금박 모서리 그림은 **오른쪽 아래**에 그려져 있다. 나머지 세 자리는 돌려서 쓴다
  if (id === 'deco' || id === 'foil') {
    const spin = { br: 0, bl: 90, tl: 180, tr: 270 }[position]
    const place = {
      tl: { top: 0, left: 0 },
      tr: { top: 0, right: 0 },
      bl: { bottom: 0, left: 0 },
      br: { bottom: 0, right: 0 },
    }[position]
    return (
      <div aria-hidden style={{ position: 'absolute', ...place, transform: `rotate(${spin}deg)`, pointerEvents: 'none' }}>
        <ArtOrnament id="corner" width={size * 1.6} opacity={0.75} />
      </div>
    )
  }
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
      case 'cherry':
        return (
          <>
            <path d="M8 46C8 24 24 8 46 8" stroke={stroke} strokeOpacity="0.45" fill="none" />
            <g transform="translate(34 18)">
              {[0, 72, 144, 216, 288].map((a) => (
                <ellipse key={a} cx="0" cy="-5" rx="2.8" ry="4.8" fill={stroke} fillOpacity="0.6" transform={`rotate(${a})`} />
              ))}
              <circle r="1.5" fill={stroke} />
            </g>
            <circle cx="16" cy="34" r="1.6" fill={stroke} fillOpacity="0.45" />
          </>
        )
      case 'snow':
        return (
          <>
            <g transform="translate(20 20)" stroke={stroke} strokeLinecap="round">
              {[0, 60, 120].map((a) => (
                <line key={a} x1="-9" y1="0" x2="9" y2="0" strokeWidth="1" strokeOpacity="0.8" transform={`rotate(${a})`} />
              ))}
              {[0, 60, 120, 180, 240, 300].map((a) => (
                <path key={a} d="M5.6 0l2.4-2.4M5.6 0l2.4 2.4" strokeWidth="0.7" strokeOpacity="0.6" transform={`rotate(${a})`} />
              ))}
            </g>
            <circle cx="44" cy="12" r="1.4" fill={stroke} fillOpacity="0.5" />
            <circle cx="12" cy="44" r="1.1" fill={stroke} fillOpacity="0.4" />
          </>
        )
      case 'maple':
        return (
          <>
            <path d="M8 48C8 24 24 8 48 8" stroke={stroke} strokeOpacity="0.45" fill="none" />
            <g transform="translate(28 24) scale(0.9)">
              <path
                d="M0-9l3.1 5.6 5.6-1.4-2.4 4.6 5.1 1.1-4.6 3.1 2 3.4-5.3-.8L2.7 9 0 5.6-2.7 9l-.8-2.4-5.3.8 2-3.4-4.6-3.1 5.1-1.1-2.4-4.6 5.6 1.4L0-9Z"
                fill={stroke}
                fillOpacity="0.6"
              />
            </g>
            <circle cx="46" cy="14" r="1.6" fill={stroke} fillOpacity="0.4" />
          </>
        )
      case 'ribbon':
        return (
          <>
            <path d="M6 52V6h46" stroke={stroke} strokeOpacity="0.55" fill="none" />
            <g transform="translate(26 20)">
              <path d="M-1.2 0C-3.4-3.4-7.2-4.2-8.8-2.2-10.4-.4-8.2 2.2-4.6 2.6l3.4-1.4Z" fill={stroke} fillOpacity="0.65" />
              <path d="M1.2 0C3.4-3.4 7.2-4.2 8.8-2.2 10.4-.4 8.2 2.2 4.6 2.6L1.2 1.2Z" fill={stroke} fillOpacity="0.65" />
              <circle cy="0.6" r="1.7" fill={stroke} />
            </g>
          </>
        )
      case 'heart':
        return (
          <>
            <path d="M8 44C8 24 24 8 44 8" stroke={stroke} strokeOpacity="0.4" fill="none" strokeDasharray="2 5" />
            <path
              d="M28 30c-7-4.8-7-10 -3.2-10.9 1.9-.4 3.2.9 3.2 2 0-1.1 1.3-2.4 3.2-2C35 20 35 25.2 28 30Z"
              fill={stroke}
              fillOpacity="0.7"
            />
            <circle cx="14" cy="14" r="1.8" fill={stroke} fillOpacity="0.5" />
          </>
        )
      case 'pearl':
        return (
          <>
            <path d="M8 52V8h44" stroke={stroke} strokeOpacity="0.35" fill="none" />
            {[14, 24, 34, 44].map((v, i) => (
              <circle key={v} cx={v} cy="8" r={3 - i * 0.4} fill={stroke} fillOpacity={0.7 - i * 0.12} />
            ))}
            {[18, 28, 38].map((v, i) => (
              <circle key={v} cx="8" cy={v} r={2.6 - i * 0.4} fill={stroke} fillOpacity={0.6 - i * 0.12} />
            ))}
          </>
        )
      case 'sun':
        return (
          <>
            <g transform="translate(18 18)">
              <circle r="5" fill={stroke} fillOpacity="0.7" />
              {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
                <line key={a} x1="0" y1="-8" x2="0" y2="-11" stroke={stroke} strokeWidth="1.2" strokeLinecap="round" strokeOpacity="0.7" transform={`rotate(${a})`} />
              ))}
            </g>
            <path d="M8 48c10-5 20 5 30 0s14-3 14-3" stroke={stroke} strokeOpacity="0.35" fill="none" strokeLinecap="round" />
          </>
        )
      case 'candle':
        return (
          <>
            <path d="M10 50C10 26 26 10 50 10" stroke={stroke} strokeOpacity="0.4" fill="none" />
            <g transform="translate(26 20)">
              <path d="M0-8c2.8 3.2 4.2 5.4 4.2 7.4 0 2.4-1.9 4.2-4.2 4.2S-4.2 1.8-4.2-.6C-4.2-2.6-2.8-4.8 0-8Z" fill={stroke} fillOpacity="0.75" />
              <rect x="-2.6" y="4.6" width="5.2" height="8" rx="1" fill={stroke} fillOpacity="0.45" />
            </g>
          </>
        )
      case 'ivy':
        return (
          <>
            <path d="M6 52C6 30 22 12 46 8" stroke={stroke} strokeOpacity="0.5" fill="none" />
            {[
              [14, 38],
              [22, 26],
              [34, 16],
            ].map(([x, y]) => (
              <path key={`${x}-${y}`} d={`M${x} ${y}c5.4-1.6 8-4.8 8-10-5.4 1-8.6 4.6-8 10Z`} fill={stroke} fillOpacity="0.5" />
            ))}
          </>
        )
      case 'note':
        return (
          <>
            <path
              d="M16 20v11a3.2 3.2 0 1 1-1.7-2.8V18l12-2.9v10.4a3.2 3.2 0 1 1-1.7-2.8v-5.5L16 20Z"
              fill={stroke}
              fillOpacity="0.65"
            />
            <circle cx="42" cy="14" r="1.6" fill={stroke} fillOpacity="0.4" />
          </>
        )
      case 'arch':
        return (
          <>
            <path d="M8 54V22a16 16 0 0 1 16-16h30" stroke={stroke} strokeWidth="1.2" strokeOpacity="0.8" fill="none" />
            <path d="M15 54V24a11 11 0 0 1 11-11h28" stroke={stroke} strokeOpacity="0.4" fill="none" />
            <circle cx="24" cy="13" r="1.8" fill={stroke} fillOpacity="0.6" />
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
/** 종이 전체에 아주 옅게 까는 그림 — 눈에 띄면 글씨를 방해한다 */
const ART_BACKDROP: Partial<Record<OrnamentId, { id: string; opacity: number }>> = {
  note: { id: 'staff', opacity: 0.1 },
  stars: { id: 'sparkle', opacity: 0.1 },
  // 금박 테마에는 금가루를 아주 옅게 뿌린다. 검은 종이 위에서 벨벳 위 금가루처럼 보인다
  foil: { id: 'flecks', opacity: 0.08 },
}

export function OrnamentBackdrop({ id }: { id: OrnamentId }) {
  const art = ART_BACKDROP[id]
  if (art) {
    return (
      <div aria-hidden style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <ArtOrnament id={art.id} width="100%" height="100%" opacity={art.opacity} fit="cover" />
      </div>
    )
  }

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

  if (id === 'sun' || id === 'candle') {
    return (
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'radial-gradient(90% 45% at 50% 0%, color-mix(in srgb, var(--d-accent) 16%, transparent) 0%, transparent 65%)',
        }}
      />
    )
  }

  if (id === 'snow') {
    return (
      <svg aria-hidden style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} width="100%" height="100%">
        <defs>
          <pattern id="d-snow" width="86" height="86" patternUnits="userSpaceOnUse">
            <circle cx="18" cy="22" r="2" fill="var(--d-accent)" fillOpacity="0.16" />
            <circle cx="60" cy="54" r="1.4" fill="var(--d-accent)" fillOpacity="0.13" />
            <circle cx="38" cy="72" r="1" fill="var(--d-accent)" fillOpacity="0.1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#d-snow)" />
      </svg>
    )
  }

  if (id === 'cherry') {
    return (
      <svg aria-hidden style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} width="100%" height="100%">
        <defs>
          <pattern id="d-cherry" width="104" height="104" patternUnits="userSpaceOnUse">
            <ellipse cx="22" cy="26" rx="3" ry="5" fill="var(--d-accent)" fillOpacity="0.12" transform="rotate(24 22 26)" />
            <ellipse cx="72" cy="62" rx="2.6" ry="4.4" fill="var(--d-accent)" fillOpacity="0.1" transform="rotate(-38 72 62)" />
            <ellipse cx="46" cy="90" rx="2.2" ry="3.6" fill="var(--d-accent)" fillOpacity="0.08" transform="rotate(12 46 90)" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#d-cherry)" />
      </svg>
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
