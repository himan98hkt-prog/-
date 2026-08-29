/**
 * 연주회 그림.
 *
 * 지금까지 포스터에 들어가는 그림이라고는 작은 높은음자리표 하나였다. 그래서 아무리
 * 색과 서체를 맞춰도 "상장" 처럼 보였다 — 가운데가 비고, 무엇에 관한 종이인지
 * 그림으로는 알 수 없었다.
 *
 * 예술회관 포스터가 왜 좋아 보이는지는 대개 셋이다.
 *   1. **큰 그림 하나**가 종이를 지배한다 (피아노 · 건반 · 무대 조명)
 *   2. 글씨가 아주 크고, 그 둘레가 시원하게 비어 있다
 *   3. 바탕에 **깊이**가 있다 (어둠에서 빛으로 번지는 결)
 *
 * 사진은 쓸 수 없다. 저작권이 걸리고, 인터넷 없이 도는 프로그램에 무거운 사진을
 * 실을 수도 없다. 그래서 **직접 그린다** — 그라디언트와 겹으로 그리면 도장 찍은 듯한
 * 클립아트가 아니라 인쇄물에 어울리는 그림이 된다.
 *
 * 모든 그림은 테마 색(`--d-accent` · `--d-ink` …)을 따라간다. 테마를 바꾸면 그림 색도 바뀐다.
 */

let seq = 0
/** 한 종이에 같은 그림을 여러 번 놓아도 그라디언트가 섞이지 않게 */
const uid = (name: string) => `${name}-${(seq += 1)}`

/**
 * 그랜드피아노 — 위에서 내려다본 실루엣.
 *
 * 연주회 포스터에서 가장 많이 쓰이는 모양이다. 곧은 앞면(건반)과 크게 휘어 도는
 * 옆선이 만나 한눈에 피아노인 줄 안다. 뚜껑을 연 선까지 그려 넣어야 납작해 보이지 않는다.
 */
export function GrandPiano({
  width = 460,
  color = 'var(--d-ink)',
  accent = 'var(--d-accent)',
  opacity = 1,
}: {
  width?: number
  color?: string
  accent?: string
  opacity?: number
}) {
  const id = uid('piano')
  return (
    <svg width={width} viewBox="0 0 460 300" fill="none" style={{ opacity, display: 'block' }} aria-hidden>
      <defs>
        <linearGradient id={`${id}-case`} x1="0" y1="0" x2="0.2" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.95" />
          <stop offset="1" stopColor={color} stopOpacity="0.72" />
        </linearGradient>
        <linearGradient id={`${id}-lid`} x1="0" y1="0" x2="0.9" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.88" />
          <stop offset="1" stopColor={color} stopOpacity="0.52" />
        </linearGradient>
      </defs>

      {/* 열어 올린 뚜껑 — 건반 쪽이 높고 꼬리 쪽으로 내려앉는다.
          연주회 사진에서 가장 먼저 눈에 들어오는 것이 이 큰 삼각면이다. */}
      <path d="M104 44 L400 150 L400 162 L104 66 Z" fill={`url(#${id}-lid)`} />
      {/* 뚜껑 안쪽 — 두께가 있어야 종이 조각처럼 보이지 않는다 */}
      <path d="M104 66 L400 162 L400 168 L104 74 Z" fill={color} fillOpacity="0.35" />

      {/* 뚜껑을 받치는 막대 */}
      <path d="M148 62 L172 150" stroke={accent} strokeWidth="4" strokeLinecap="round" opacity="0.95" />

      {/* 몸통 — 꼬리(오른쪽)가 둥글게 닫힌다 */}
      <path
        d="M56 150 L372 150 C406 150 424 166 424 182 C424 198 406 212 372 212 L56 212 Z"
        fill={`url(#${id}-case)`}
      />
      {/* 몸통 옆면의 결 */}
      <path d="M56 158 L392 158" stroke={color} strokeOpacity="0.25" strokeWidth="1.2" />

      {/* 건반 — 앞으로 조금 내민 띠. 흰 건반과 검은 건반이 보여야 피아노가 된다 */}
      <rect x="44" y="212" width="176" height="24" rx="2" fill="#fdfbf6" />
      <g fill={color} fillOpacity="0.92">
        {[0, 1, 3, 4, 5, 7, 8, 10, 11, 12].map((i) => (
          <rect key={i} x={55 + i * 16.4} y="212" width="7" height="14" rx="1" />
        ))}
      </g>
      <rect x="44" y="212" width="176" height="24" rx="2" fill="none" stroke={color} strokeOpacity="0.4" strokeWidth="1.2" />
      {/* 건반 아래 앞판 */}
      <path d="M44 236 L220 236 L220 246 L44 246 Z" fill={color} fillOpacity="0.8" />

      {/* 다리 셋 — 아래로 갈수록 가늘어진다 */}
      <g fill={color} fillOpacity="0.9">
        <path d="M64 246 L84 246 L79 292 L69 292 Z" />
        <path d="M236 212 L256 212 L251 292 L241 292 Z" />
        <path d="M392 212 L412 212 L407 292 L397 292 Z" />
      </g>
      {/* 바닥 그림자 — 떠 있어 보이지 않게 */}
      <ellipse cx="240" cy="294" rx="200" ry="7" fill={color} fillOpacity="0.18" />

      {/* 페달 */}
      <path d="M240 292 L252 292 L252 284 L240 284 Z" fill={accent} fillOpacity="0.7" />
    </svg>
  )
}

/**
 * 건반 — 앞으로 다가오는 원근.
 *
 * 종이 아래쪽을 가로질러 깔면, 보는 사람이 피아노 앞에 앉은 자리에 서게 된다.
 * 멀어질수록 어두워지게 해야 평면 그림이 아니라 공간이 된다.
 */
export function KeysPerspective({
  width = 900,
  height = 220,
  color = 'var(--d-ink)',
  glow = 'var(--d-accent)',
}: {
  width?: number
  height?: number
  color?: string
  glow?: string
}) {
  const id = uid('keys')
  const KEYS = 24
  return (
    <svg width={width} height={height} viewBox="0 0 900 220" fill="none" style={{ display: 'block' }} aria-hidden>
      <defs>
        <linearGradient id={`${id}-fade`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.9" />
          <stop offset="0.55" stopColor={color} stopOpacity="0.12" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
        <radialGradient id={`${id}-glow`} cx="0.5" cy="0" r="0.9">
          <stop offset="0" stopColor={glow} stopOpacity="0.5" />
          <stop offset="1" stopColor={glow} stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* 흰 건반 — 위(먼 쪽)가 좁고 아래(가까운 쪽)가 넓다 */}
      {Array.from({ length: KEYS }).map((_, i) => {
        const t0 = i / KEYS
        const t1 = (i + 1) / KEYS
        const near0 = t0 * 900
        const near1 = t1 * 900
        const far0 = 210 + t0 * 480
        const far1 = 210 + t1 * 480
        return (
          <path
            key={i}
            d={`M${far0 + 1} 24 L${far1 - 1} 24 L${near1 - 2} 216 L${near0 + 2} 216 Z`}
            fill="#fdfbf6"
            fillOpacity={0.93 - t0 * 0.06}
          />
        )
      })}

      {/* 검은 건반 */}
      {Array.from({ length: KEYS }).map((_, i) => {
        if ([2, 6, 9, 13, 16, 20, 23].includes(i % 24) === false && ![0, 1, 3, 4, 5, 7, 8, 10, 11, 12, 14, 15, 17, 18, 19, 21, 22].includes(i)) return null
        if ([2, 6, 9, 13, 16, 20].includes(i) === false) return null
        const t = (i + 0.72) / KEYS
        const tw = 0.56 / KEYS
        const near0 = t * 900
        const near1 = (t + tw) * 900
        const far0 = 210 + t * 480
        const far1 = 210 + (t + tw) * 480
        return (
          <path key={`b${i}`} d={`M${far0} 24 L${far1} 24 L${near1} 150 L${near0} 150 Z`} fill={color} fillOpacity="0.95" />
        )
      })}

      {/* 멀어질수록 어둠에 잠긴다 */}
      <rect x="0" y="0" width="900" height="220" fill={`url(#${id}-fade)`} />
      {/* 위에서 내려오는 빛 */}
      <rect x="0" y="0" width="900" height="150" fill={`url(#${id}-glow)`} />
    </svg>
  )
}

/**
 * 무대 조명 — 위에서 내려오는 빛줄기.
 *
 * 어두운 바탕에 이것 하나만 깔아도 "무대" 가 된다. 빛이 닿는 자리에 제목을 놓는다.
 */
export function StageBeams({
  width = 900,
  height = 620,
  color = 'var(--d-accent)',
  count = 3,
}: {
  width?: number
  height?: number
  color?: string
  count?: number
}) {
  const id = uid('beam')
  const beams = Array.from({ length: count }).map((_, i) => {
    const x = ((i + 1) / (count + 1)) * 900
    return { x, spread: 150 + i * 24 }
  })
  return (
    <svg width={width} height={height} viewBox="0 0 900 620" fill="none" style={{ display: 'block' }} aria-hidden>
      <defs>
        <linearGradient id={`${id}-b`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.42" />
          <stop offset="0.7" stopColor={color} stopOpacity="0.07" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
        <radialGradient id={`${id}-pool`} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor={color} stopOpacity="0.30" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </radialGradient>
      </defs>
      {beams.map((b, i) => (
        <path key={i} d={`M${b.x - 14} 0 L${b.x + 14} 0 L${b.x + b.spread} 620 L${b.x - b.spread} 620 Z`} fill={`url(#${id}-b)`} />
      ))}
      {/* 바닥에 고이는 빛 */}
      <ellipse cx="450" cy="600" rx="360" ry="70" fill={`url(#${id}-pool)`} />
    </svg>
  )
}

/**
 * 무대 아치 — 객석에서 본 프로시니엄과 커튼.
 *
 * 제목을 이 안에 넣으면 종이가 곧 무대가 된다. 격식 있는 정기 연주회에 어울린다.
 */
export function HallArch({
  width = 720,
  height = 900,
  color = 'var(--d-accent)',
  ink = 'var(--d-ink)',
}: {
  width?: number
  height?: number
  color?: string
  ink?: string
}) {
  const id = uid('arch')
  return (
    <svg width={width} height={height} viewBox="0 0 720 900" fill="none" style={{ display: 'block' }} aria-hidden>
      <defs>
        <linearGradient id={`${id}-drape`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={ink} stopOpacity="0.85" />
          <stop offset="1" stopColor={ink} stopOpacity="0.35" />
        </linearGradient>
      </defs>

      {/* 양옆으로 걷어 둔 커튼 — 줄이 아니라 **면**이라야 천으로 보인다 */}
      <path
        d="M0 0 L150 0 C150 180 96 300 118 470 C138 630 96 760 130 900 L0 900 Z"
        fill={`url(#${id}-drape)`}
      />
      <path
        d="M720 0 L570 0 C570 180 624 300 602 470 C582 630 624 760 590 900 L720 900 Z"
        fill={`url(#${id}-drape)`}
      />
      {/* 천의 주름 */}
      <g stroke={ink} strokeOpacity="0.35" strokeWidth="1.5" fill="none">
        {[38, 74, 110].map((x) => (
          <path key={x} d={`M${x} 0 C${x + 16} 260, ${x - 12} 560, ${x + 10} 900`} />
        ))}
        {[682, 646, 610].map((x) => (
          <path key={x} d={`M${x} 0 C${x - 16} 260, ${x + 12} 560, ${x - 10} 900`} />
        ))}
      </g>

      {/* 위쪽 가림막 */}
      <path d="M0 0 L720 0 L720 96 C560 132 160 132 0 96 Z" fill={`url(#${id}-drape)`} />

      {/* 아치 — 넓고 낮아야 무대가 된다. 좁고 높으면 창문처럼 보인다 */}
      <path
        d="M132 900 L132 400 C132 250 234 150 360 150 C486 150 588 250 588 400 L588 900"
        stroke={color}
        strokeWidth="3"
        fill="none"
        opacity="0.95"
      />
      <path
        d="M156 900 L156 404 C156 268 246 178 360 178 C474 178 564 268 564 404 L564 900"
        stroke={color}
        strokeWidth="1"
        fill="none"
        opacity="0.45"
      />
    </svg>
  )
}

/**
 * 흐르는 오선 — 음악이 지나간 자리.
 *
 * 종이 한쪽을 가볍게 채우는 결. 너무 진하면 글씨를 방해하므로 옅게 깐다.
 */
export function StaffFlow({
  width = 900,
  height = 300,
  color = 'var(--d-accent)',
  opacity = 0.28,
}: {
  width?: number
  height?: number
  color?: string
  opacity?: number
}) {
  const id = uid('staff')
  return (
    <svg width={width} height={height} viewBox="0 0 900 300" fill="none" style={{ display: 'block', opacity }} aria-hidden>
      <defs>
        <linearGradient id={`${id}-f`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor={color} stopOpacity="0" />
          <stop offset="0.25" stopColor={color} stopOpacity="1" />
          <stop offset="0.78" stopColor={color} stopOpacity="1" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 1, 2, 3, 4].map((i) => (
        <path
          key={i}
          d={`M0 ${120 + i * 15} C220 ${60 + i * 15}, 460 ${190 + i * 15}, 900 ${104 + i * 15}`}
          stroke={`url(#${id}-f)`}
          strokeWidth="1.4"
          fill="none"
        />
      ))}
      {/* 음표 몇 개 — 오선 위에 앉힌다 */}
      {[
        [250, 118],
        [340, 152],
        [455, 168],
        [560, 138],
        [670, 120],
      ].map(([x, y], i) => (
        <g key={i}>
          <ellipse cx={x} cy={y} rx="8.5" ry="6.2" fill={color} transform={`rotate(-18 ${x} ${y})`} />
          <path d={`M${x + 8} ${y - 2} L${x + 8} ${y - 46}`} stroke={color} strokeWidth="2.2" strokeLinecap="round" />
        </g>
      ))}
    </svg>
  )
}

/**
 * 빛망울 — 초점 밖 조명.
 *
 * 어두운 바탕에 뿌리면 공연장의 공기가 생긴다. 규칙적으로 놓으면 무늬처럼 보이므로
 * 자리와 크기를 미리 흩어 둔 값으로 박아 둔다 (다시 그려도 늘 같아야 인쇄가 흔들리지 않는다).
 */
const BOKEH = [
  [86, 92, 34], [214, 48, 18], [318, 128, 46], [430, 62, 22], [556, 118, 30],
  [668, 54, 40], [780, 132, 20], [140, 196, 26], [268, 238, 16], [392, 208, 36],
  [512, 252, 22], [636, 206, 28], [742, 246, 18], [842, 190, 32],
] as const

export function Bokeh({
  width = 900,
  height = 300,
  color = 'var(--d-accent)',
  opacity = 0.5,
}: {
  width?: number
  height?: number
  color?: string
  opacity?: number
}) {
  const id = uid('bokeh')
  return (
    <svg width={width} height={height} viewBox="0 0 900 300" fill="none" style={{ display: 'block', opacity }} aria-hidden>
      <defs>
        <radialGradient id={`${id}-d`} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor={color} stopOpacity="0.55" />
          <stop offset="0.75" stopColor={color} stopOpacity="0.16" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </radialGradient>
      </defs>
      {BOKEH.map(([x, y, r], i) => (
        <circle key={i} cx={x} cy={y} r={r} fill={`url(#${id}-d)`} />
      ))}
    </svg>
  )
}

/**
 * 월계관 — 콩쿠르 · 정기 연주회의 격.
 *
 * 상장처럼 보이지 않게 하려면 잎을 촘촘히 그리고 아래를 열어 두어야 한다.
 */
export function Laurel({ width = 280, color = 'var(--d-accent)' }: { width?: number; color?: string }) {
  const CX = 150
  const CY = 150
  const R = 108

  /**
   * 한쪽 가지.
   *
   * 아래 가운데에서 올라가 위 가까이에서 멎는다. 위아래를 열어 두어야 화환이 되지
   * 도장이 되지 않는다. 잎은 바깥·위를 향해 눕히고, 가운데가 가장 크다.
   */
  const branch = (side: 1 | -1) => {
    const from = 262
    const to = 108
    const n = 13
    return Array.from({ length: n }).map((_, i) => {
      const t = i / (n - 1)
      const deg = from - t * (from - to)
      const rad = (deg * Math.PI) / 180
      const cx = CX + side * Math.cos(rad) * R
      const cy = CY - Math.sin(rad) * R
      const size = 17 - Math.abs(t - 0.45) * 12
      // 잎이 바깥을 보게 — 원의 접선에서 조금 벌린다
      const rot = side === 1 ? 90 - deg + 28 : deg - 90 - 28
      return (
        <ellipse
          key={`${side}-${i}`}
          cx={cx}
          cy={cy}
          rx={size}
          ry={size * 0.4}
          fill={color}
          fillOpacity={0.55 + (1 - Math.abs(t - 0.45)) * 0.4}
          transform={`rotate(${rot} ${cx} ${cy})`}
        />
      )
    })
  }

  return (
    <svg width={width} viewBox="0 0 300 300" fill="none" style={{ display: 'block' }} aria-hidden>
      {/* 가지 줄기 — 잎만 있으면 흩어져 보인다 */}
      <path
        d={`M${CX - Math.cos((262 * Math.PI) / 180) * R} ${CY + Math.sin((262 * Math.PI) / 180) * R}
            A ${R} ${R} 0 0 1 ${CX - Math.cos((108 * Math.PI) / 180) * R} ${CY - Math.sin((108 * Math.PI) / 180) * R}`}
        stroke={color}
        strokeWidth="1.6"
        strokeOpacity="0.5"
        fill="none"
      />
      <path
        d={`M${CX + Math.cos((262 * Math.PI) / 180) * R} ${CY + Math.sin((262 * Math.PI) / 180) * R}
            A ${R} ${R} 0 0 0 ${CX + Math.cos((108 * Math.PI) / 180) * R} ${CY - Math.sin((108 * Math.PI) / 180) * R}`}
        stroke={color}
        strokeWidth="1.6"
        strokeOpacity="0.5"
        fill="none"
      />
      {branch(1)}
      {branch(-1)}
    </svg>
  )
}
