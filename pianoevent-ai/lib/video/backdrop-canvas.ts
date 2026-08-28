import type { DesignTheme } from '@/lib/design/themes'
import type { StageBackdrop } from '@/lib/stage/backdrops'

/**
 * 무대 배경을 캔버스에 그린다.
 *
 * 무대 화면(스크린·PPT)은 SVG 로 그리고, 영상은 캔버스로 그린다.
 * 같은 배경이 두 곳에서 같아 보여야 하므로 `components/stage/backdrops.tsx` 와
 * **같은 좌표·같은 색 규칙**을 쓴다.
 *
 * 색은 두 갈래다.
 *   · `ink` — 화면을 따라가는 색 (어두운 화면에서 뒤바뀐다). 오선처럼 "바탕 위의 선"에.
 *   · `deep` / `light` — 물건의 색. 피아노 검은건반은 어두운 화면에서도 검다.
 */
export function drawBackdrop(
  ctx: CanvasRenderingContext2D,
  id: StageBackdrop,
  theme: DesignTheme,
  w: number,
  h: number,
) {
  if (id === 'plain') return
  const p = theme.palette
  const accent = p.accent
  const soft = p.accentSoft
  const deep = p.ink
  const light = p.paper
  // 영상은 늘 어두운 무대 위에 놓인다 — 바탕 위의 선은 밝은 쪽으로
  const ink = p.paper
  // 기준 크기(1280×720) 로 그린 뒤 실제 크기에 맞춰 늘린다
  const u = h / 720

  ctx.save()
  const W = w
  const H = h

  if (id === 'keys') {
    const whites = 26
    const step = W / whites
    const top = H - 150 * u
    ctx.fillStyle = deep
    ctx.globalAlpha = 0.55
    ctx.fillRect(0, top, W, 150 * u)
    ctx.globalAlpha = 0.62
    ctx.fillStyle = light
    for (let i = 0; i < whites; i += 1) ctx.fillRect(i * step + 1, top + 8 * u, step - 2, 142 * u)
    ctx.globalAlpha = 0.92
    ctx.fillStyle = deep
    for (let i = 0; i < whites; i += 1) {
      if (![1, 2, 4, 5, 6].includes(i % 7)) continue
      ctx.fillRect(i * step + step * 0.62, top + 8 * u, step * 0.62, 88 * u)
    }
    ctx.globalAlpha = 0.9
    ctx.fillStyle = accent
    ctx.fillRect(0, top, W, 7 * u)
    ctx.restore()
    return
  }

  if (id === 'curtain') {
    const side = 250 * u
    for (const [x0, x1] of [
      [0, side],
      [W, W - side],
    ]) {
      const grad = ctx.createLinearGradient(x0, 0, x1, 0)
      grad.addColorStop(0, accent)
      grad.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.globalAlpha = 0.34
      ctx.fillStyle = grad
      ctx.fillRect(Math.min(x0, x1), 0, side, H)
    }
    ctx.globalAlpha = 0.34
    ctx.strokeStyle = accent
    ctx.lineWidth = 2 * u
    for (let i = 0; i < 7; i += 1) {
      ctx.beginPath()
      ctx.moveTo(i * 34 * u, 0)
      ctx.quadraticCurveTo(i * 34 * u + 16 * u, H / 2, i * 34 * u, H)
      ctx.stroke()
      ctx.beginPath()
      ctx.moveTo(W - i * 34 * u, 0)
      ctx.quadraticCurveTo(W - i * 34 * u - 16 * u, H / 2, W - i * 34 * u, H)
      ctx.stroke()
    }
    ctx.globalAlpha = 0.4
    ctx.fillStyle = accent
    ctx.beginPath()
    ctx.moveTo(0, 0)
    ctx.quadraticCurveTo(W / 2, 120 * u, W, 0)
    ctx.closePath()
    ctx.fill()
    ctx.restore()
    return
  }

  if (id === 'spotlight') {
    const grad = ctx.createRadialGradient(W / 2, -H * 0.06, 0, W / 2, -H * 0.06, H * 1.1)
    grad.addColorStop(0, hexAlpha(accent, 0.42))
    grad.addColorStop(0.55, hexAlpha(accent, 0.14))
    grad.addColorStop(1, hexAlpha(accent, 0))
    ctx.fillStyle = grad
    ctx.fillRect(0, 0, W, H)
    ctx.globalAlpha = 0.12
    ctx.fillStyle = accent
    ctx.beginPath()
    ctx.moveTo(W / 2 - 60 * u, 0)
    ctx.lineTo(W / 2 - 330 * u, H)
    ctx.lineTo(W / 2 + 330 * u, H)
    ctx.lineTo(W / 2 + 60 * u, 0)
    ctx.closePath()
    ctx.fill()
    ctx.globalAlpha = 0.16
    ctx.beginPath()
    ctx.ellipse(W / 2, H - 40 * u, 340 * u, 54 * u, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.restore()
    return
  }

  if (id === 'score') {
    ctx.globalAlpha = 0.22
    ctx.strokeStyle = ink
    ctx.lineWidth = 2 * u
    for (const base of [110 * u, 470 * u]) {
      for (let i = 0; i < 5; i += 1) {
        ctx.beginPath()
        ctx.moveTo(-20, base + i * 17 * u)
        ctx.lineTo(W + 20, base + i * 17 * u)
        ctx.stroke()
      }
    }
    ctx.globalAlpha = 0.3
    ctx.fillStyle = accent
    for (const [x, y] of NOTES) {
      ctx.save()
      ctx.translate(x * u, y * u)
      ctx.rotate((-18 * Math.PI) / 180)
      ctx.beginPath()
      ctx.ellipse(0, 0, 13 * u, 9 * u, 0, 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()
      ctx.fillRect(x * u + 10 * u, y * u - 56 * u, 3 * u, 56 * u)
    }
    ctx.restore()
    return
  }

  if (id === 'bokeh') {
    for (const [cx, cy, r] of BOKEH) {
      const grad = ctx.createRadialGradient(cx * u, cy * u, 0, cx * u, cy * u, r * u)
      grad.addColorStop(0, hexAlpha(accent, 0.5))
      grad.addColorStop(0.7, hexAlpha(accent, 0.16))
      grad.addColorStop(1, hexAlpha(accent, 0))
      ctx.fillStyle = grad
      ctx.beginPath()
      ctx.arc(cx * u, cy * u, r * u, 0, Math.PI * 2)
      ctx.fill()
    }
    ctx.restore()
    return
  }

  if (id === 'grand') {
    ctx.globalAlpha = 0.22
    ctx.fillStyle = accent
    ctx.beginPath()
    ctx.moveTo(W - 640 * u, H)
    ctx.quadraticCurveTo(W - 626 * u, H - 128 * u, W - 400 * u, H - 136 * u)
    ctx.quadraticCurveTo(W - 130 * u, H - 145 * u, W - 30 * u, H - 66 * u)
    ctx.lineTo(W - 30 * u, H)
    ctx.closePath()
    ctx.fill()
    ctx.globalAlpha = 0.15
    ctx.beginPath()
    ctx.moveTo(W - 618 * u, H - 134 * u)
    ctx.quadraticCurveTo(W - 440 * u, H - 226 * u, W - 96 * u, H - 168 * u)
    ctx.lineTo(W - 402 * u, H - 136 * u)
    ctx.closePath()
    ctx.fill()
    ctx.globalAlpha = 0.8
    ctx.fillStyle = accent
    ctx.fillRect(0, H - 8 * u, W, 8 * u)
    ctx.restore()
    return
  }

  if (id === 'starry') {
    const grad = ctx.createLinearGradient(0, 0, 0, H)
    grad.addColorStop(0, hexAlpha(deep, 0.55))
    grad.addColorStop(1, hexAlpha(deep, 0))
    ctx.fillStyle = grad
    ctx.fillRect(0, 0, W, H)
    ctx.globalAlpha = 0.55
    ctx.fillStyle = accent
    for (let i = 0; i < 46; i += 1) {
      // 무작위를 쓰지 않는다 — 매번 같은 자리에 찍혀야 미리보기와 영상이 같다
      const x = (((i * 137) % 127) / 127) * W
      const y = (((i * 61) % 89) / 89) * H * 0.72
      const r = ((i % 3) + 1) * u
      ctx.beginPath()
      ctx.arc(x, y, r, 0, Math.PI * 2)
      ctx.fill()
    }
    ctx.restore()
    return
  }

  if (id === 'ribbon') {
    ctx.lineWidth = 5 * u
    for (const [y, color, alpha, width] of [
      [84, accent, 0.7, 5],
      [116, soft, 0.6, 2.5],
      [H / u - 84, accent, 0.7, 5],
      [H / u - 116, soft, 0.6, 2.5],
    ] as [number, string, number, number][]) {
      ctx.globalAlpha = alpha
      ctx.strokeStyle = color
      ctx.lineWidth = width * u
      ctx.beginPath()
      ctx.moveTo(-20, y * u)
      ctx.quadraticCurveTo(W / 3, (y - 64) * u, W / 2, (y - 10) * u)
      ctx.quadraticCurveTo((W * 2) / 3, (y + 44) * u, W + 20, (y - 38) * u)
      ctx.stroke()
    }
    ctx.restore()
    return
  }

  // arc
  ctx.globalAlpha = 0.5
  ctx.strokeStyle = accent
  ctx.lineWidth = 6 * u
  ctx.beginPath()
  ctx.moveTo(W / 2 - 430 * u, H)
  ctx.lineTo(W / 2 - 430 * u, 320 * u)
  ctx.ellipse(W / 2, 320 * u, 430 * u, 320 * u, 0, Math.PI, 0)
  ctx.lineTo(W / 2 + 430 * u, H)
  ctx.stroke()
  ctx.globalAlpha = 0.7
  ctx.fillStyle = accent
  ctx.fillRect(0, H - 10 * u, W, 10 * u)
  ctx.restore()
}

const NOTES: [number, number][] = [
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
]

const BOKEH: [number, number, number][] = [
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

/** #RRGGBB + 투명도 → rgba(). 캔버스 그러데이션은 투명도를 색 안에 넣어야 한다 */
export function hexAlpha(hex: string, alpha: number): string {
  const value = hex.replace('#', '')
  const full = value.length === 3 ? value.split('').map((c) => c + c).join('') : value
  const r = parseInt(full.slice(0, 2), 16) || 0
  const g = parseInt(full.slice(2, 4), 16) || 0
  const b = parseInt(full.slice(4, 6), 16) || 0
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}
