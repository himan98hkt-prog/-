import type { DesignTheme } from '@/lib/design/themes'
import { STAGE_SLIDE_H, STAGE_SLIDE_W } from '@/lib/stage/deck'
import type { StageBackdrop } from '@/lib/stage/backdrops'

/**
 * 무대 배경 — 사진이 아니라 그림(SVG)이다.
 * 인터넷 없이 뜨고, 테마 색을 그대로 입고, 아무리 키워도 흐려지지 않는다.
 */
export function StageBackdropView({
  id,
  theme,
  dark,
}: {
  id: StageBackdrop
  theme: DesignTheme
  dark: boolean
}) {
  if (id === 'plain') return null

  const p = theme.palette
  /**
   * 색을 두 갈래로 나눠 쓴다.
   *
   * · `ink` / `paper` — **화면을 따라가는** 색. 어두운 화면에서는 뒤바뀐다.
   *   오선처럼 "바탕 위에 보여야 하는 선"에 쓴다.
   * · `deep` / `light` — **물건의 색**. 어느 화면에서든 그대로다.
   *   피아노 검은건반은 어두운 화면에서도 검다. 뒤바꾸면 건반이 뒤집힌다.
   */
  const ink = dark ? p.paper : p.ink
  const deep = p.ink
  const light = p.paper
  const accent = p.accent
  const soft = p.accentSoft
  const W = STAGE_SLIDE_W
  const H = STAGE_SLIDE_H

  const common = {
    // 테마 장식(OrnamentBackdrop)과 구별되게 표시해 둔다 — 검사와 인쇄에서 찾아야 한다
    className: 'stage-backdrop',
    'aria-hidden': true as const,
    style: { position: 'absolute' as const, inset: 0, pointerEvents: 'none' as const },
    viewBox: `0 0 ${W} ${H}`,
    preserveAspectRatio: 'none' as const,
    width: '100%',
    height: '100%',
  }

  if (id === 'keys') {
    // 아래쪽에 건반 한 줄 — 흰건반 위에 검은건반
    const whites = 26
    const step = W / whites
    const top = H - 150
    return (
      <svg {...common}>
        <rect x={0} y={top} width={W} height={150} fill={deep} opacity={dark ? 0.55 : 0.16} />
        {Array.from({ length: whites }, (_, i) => (
          <rect
            key={`w${i}`}
            x={i * step + 1}
            y={top + 8}
            width={step - 2}
            height={142}
            fill={light}
            opacity={dark ? 0.62 : 0.92}
          />
        ))}
        {Array.from({ length: whites }, (_, i) => i)
          .filter((i) => [1, 2, 4, 5, 6].includes(i % 7))
          .map((i) => (
            <rect
              key={`b${i}`}
              x={i * step + step * 0.62}
              y={top + 8}
              width={step * 0.62}
              height={88}
              rx={3}
              fill={deep}
              opacity={0.92}
            />
          ))}
        <rect x={0} y={top} width={W} height={7} fill={accent} opacity={0.9} />
      </svg>
    )
  }

  if (id === 'curtain') {
    const folds = 7
    const side = 250
    return (
      <svg {...common}>
        <defs>
          <linearGradient id="curtain-l" x1="0" x2="1">
            <stop offset="0%" stopColor={accent} stopOpacity={dark ? 0.5 : 0.36} />
            <stop offset="100%" stopColor={accent} stopOpacity={0} />
          </linearGradient>
          <linearGradient id="curtain-r" x1="1" x2="0">
            <stop offset="0%" stopColor={accent} stopOpacity={dark ? 0.5 : 0.36} />
            <stop offset="100%" stopColor={accent} stopOpacity={0} />
          </linearGradient>
        </defs>
        <rect x={0} y={0} width={side} height={H} fill="url(#curtain-l)" />
        <rect x={W - side} y={0} width={side} height={H} fill="url(#curtain-r)" />
        {Array.from({ length: folds }, (_, i) => (
          <path
            key={`fl${i}`}
            d={`M ${i * 34} 0 Q ${i * 34 + 16} ${H / 2} ${i * 34} ${H}`}
            stroke={accent}
            strokeWidth={2}
            fill="none"
            opacity={dark ? 0.34 : 0.22}
          />
        ))}
        {Array.from({ length: folds }, (_, i) => (
          <path
            key={`fr${i}`}
            d={`M ${W - i * 34} 0 Q ${W - i * 34 - 16} ${H / 2} ${W - i * 34} ${H}`}
            stroke={accent}
            strokeWidth={2}
            fill="none"
            opacity={dark ? 0.34 : 0.22}
          />
        ))}
        <path d={`M 0 0 Q ${W / 2} 120 ${W} 0 L ${W} 0 L 0 0 Z`} fill={accent} opacity={dark ? 0.4 : 0.28} />
      </svg>
    )
  }

  if (id === 'spotlight') {
    return (
      <svg {...common}>
        <defs>
          <radialGradient id="spot" cx="50%" cy="-6%" r="78%">
            <stop offset="0%" stopColor={accent} stopOpacity={dark ? 0.42 : 0.3} />
            <stop offset="55%" stopColor={accent} stopOpacity={dark ? 0.14 : 0.1} />
            <stop offset="100%" stopColor={accent} stopOpacity={0} />
          </radialGradient>
        </defs>
        <rect x={0} y={0} width={W} height={H} fill="url(#spot)" />
        <path d={`M ${W / 2 - 60} 0 L ${W / 2 - 330} ${H} L ${W / 2 + 330} ${H} L ${W / 2 + 60} 0 Z`} fill={accent} opacity={dark ? 0.12 : 0.07} />
        <ellipse cx={W / 2} cy={H - 40} rx={340} ry={54} fill={accent} opacity={dark ? 0.16 : 0.1} />
      </svg>
    )
  }

  if (id === 'score') {
    const lines = [0, 1, 2, 3, 4]
    return (
      <svg {...common}>
        {[110, 470].map((base) => (
          <g key={base} opacity={dark ? 0.22 : 0.16}>
            {lines.map((i) => (
              <line key={i} x1={-20} y1={base + i * 17} x2={W + 20} y2={base + i * 17} stroke={ink} strokeWidth={2} />
            ))}
          </g>
        ))}
        {[
          [180, 144],
          [330, 178],
          [520, 127],
          [700, 161],
          [880, 144],
          [1060, 178],
          [250, 504],
          [470, 538],
          [760, 487],
          [1010, 521],
        ].map(([x, y], i) => (
          <g key={i} opacity={dark ? 0.3 : 0.22}>
            <ellipse cx={x} cy={y} rx={13} ry={9} fill={accent} transform={`rotate(-18 ${x} ${y})`} />
            <rect x={x + 10} y={y - 56} width={3} height={56} fill={accent} />
          </g>
        ))}
      </svg>
    )
  }

  if (id === 'bokeh') {
    const dots = [
      [140, 120, 70],
      [1120, 180, 96],
      [300, 560, 54],
      [980, 600, 74],
      [640, 90, 44],
      [1210, 460, 60],
      [60, 420, 48],
      [820, 300, 36],
      [430, 260, 30],
    ]
    return (
      <svg {...common}>
        <defs>
          <radialGradient id="bok">
            <stop offset="0%" stopColor={accent} stopOpacity={dark ? 0.5 : 0.34} />
            <stop offset="70%" stopColor={accent} stopOpacity={dark ? 0.16 : 0.11} />
            <stop offset="100%" stopColor={accent} stopOpacity={0} />
          </radialGradient>
        </defs>
        {dots.map(([cx, cy, r], i) => (
          <circle key={i} cx={cx} cy={cy} r={r} fill="url(#bok)" />
        ))}
      </svg>
    )
  }

  if (id === 'grand') {
    // 오른쪽 아래에 앉은 그랜드피아노 실루엣
    return (
      <svg {...common}>
        {/*
          글자는 화면 위쪽에 있으므로 피아노는 아래 4분의 1 안에만 앉힌다.
          실루엣은 강조색으로 옅게 — 어두운 화면에서 잉크색을 쓰면 배경과 같아져 사라지고,
          종이색을 쓰면 회색 덩어리처럼 튄다.
        */}
        <g opacity={dark ? 0.22 : 0.16} fill={accent}>
          <path
            d={`M ${W - 640} ${H} Q ${W - 626} ${H - 128} ${W - 400} ${H - 136} Q ${W - 130} ${H - 145} ${W - 30} ${H - 66} L ${W - 30} ${H} Z`}
          />
          <path
            d={`M ${W - 618} ${H - 134} Q ${W - 440} ${H - 226} ${W - 96} ${H - 168} L ${W - 402} ${H - 136} Z`}
            opacity={0.7}
          />
        </g>
        <rect x={0} y={H - 8} width={W} height={8} fill={accent} opacity={0.8} />
      </svg>
    )
  }

  if (id === 'starry') {
    const stars = Array.from({ length: 46 }, (_, i) => {
      // 늘 같은 자리에 찍히게 — 무작위를 쓰면 인쇄와 화면이 달라진다
      const x = ((i * 137) % 127) / 127
      const y = ((i * 61) % 89) / 89
      return [Math.round(x * W), Math.round(y * (H * 0.72)), (i % 3) + 1]
    })
    return (
      <svg {...common}>
        <defs>
          <linearGradient id="night" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={deep} stopOpacity={dark ? 0.55 : 0.22} />
            <stop offset="100%" stopColor={deep} stopOpacity={0} />
          </linearGradient>
        </defs>
        <rect x={0} y={0} width={W} height={H} fill="url(#night)" />
        {stars.map(([cx, cy, r], i) => (
          <circle key={i} cx={cx} cy={cy} r={r} fill={accent} opacity={0.55} />
        ))}
      </svg>
    )
  }

  if (id === 'ribbon') {
    return (
      <svg {...common}>
        <path d={`M -20 84 Q ${W / 3} 20 ${W / 2} 74 T ${W + 20} 46`} stroke={accent} strokeWidth={5} fill="none" opacity={0.7} />
        <path d={`M -20 116 Q ${W / 3} 52 ${W / 2} 106 T ${W + 20} 78`} stroke={soft} strokeWidth={2.5} fill="none" opacity={0.6} />
        <path d={`M -20 ${H - 84} Q ${W / 3} ${H - 20} ${W / 2} ${H - 74} T ${W + 20} ${H - 46}`} stroke={accent} strokeWidth={5} fill="none" opacity={0.7} />
        <path d={`M -20 ${H - 116} Q ${W / 3} ${H - 52} ${W / 2} ${H - 106} T ${W + 20} ${H - 78}`} stroke={soft} strokeWidth={2.5} fill="none" opacity={0.6} />
      </svg>
    )
  }

  // arc — 가운데를 감싸는 큰 아치
  return (
    <svg {...common}>
      <path
        d={`M ${W / 2 - 430} ${H} L ${W / 2 - 430} 320 A 430 320 0 0 1 ${W / 2 + 430} 320 L ${W / 2 + 430} ${H}`}
        fill="none"
        stroke={accent}
        strokeWidth={6}
        opacity={dark ? 0.5 : 0.34}
      />
      <path
        d={`M ${W / 2 - 396} ${H} L ${W / 2 - 396} 330 A 396 300 0 0 1 ${W / 2 + 396} 330 L ${W / 2 + 396} ${H}`}
        fill="none"
        stroke={soft}
        strokeWidth={2}
        opacity={dark ? 0.4 : 0.3}
      />
      <rect x={0} y={H - 10} width={W} height={10} fill={accent} opacity={0.7} />
    </svg>
  )
}
