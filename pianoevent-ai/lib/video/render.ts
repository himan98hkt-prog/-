import type { DesignTheme } from '@/lib/design/themes'
import type { VideoScene } from '@/lib/video/storyboard'

/**
 * 한 프레임을 캔버스에 그린다.
 *
 * 미리보기와 실제로 뽑는 영상이 **같은 함수**를 쓴다. 보이는 대로 나온다.
 * 사진은 천천히 확대되며(켄 번스) 장면 사이는 겹쳐 넘어간다 — 정지 사진이
 * 살아 있는 것처럼 보이는 가장 단순한 방법이다.
 */

export interface FrameSource {
  /** 이미 다 읽어 둔 사진. 그릴 때 새로 읽지 않는다 (끊긴다) */
  images: Map<string, HTMLImageElement>
  /** 재생 중인 동영상 */
  videos: Map<string, HTMLVideoElement>
}

/** 장면 사이 겹쳐 넘어가는 시간(초) */
export const CROSSFADE_SEC = 0.6

export interface Timeline {
  scenes: VideoScene[]
  /** 각 장면의 시작 시각(초) */
  starts: number[]
  total: number
}

export function buildTimeline(scenes: VideoScene[]): Timeline {
  const starts: number[] = []
  let clock = 0
  for (const scene of scenes) {
    starts.push(clock)
    clock += scene.seconds
  }
  return { scenes, starts, total: clock }
}

/**
 * 지금 시각에 보이는 장면.
 *
 * 넘어가는 동안에는 **두 장면이 겹쳐야** 한다. 앞 장면이 먼저 사라지면
 * 그 0.6초 동안 바탕색이 비쳐 화면이 한 번 껌뻑인다.
 * 그래서 앞 장면은 제 시간이 끝난 뒤에도 겹치는 시간만큼 아래에 그대로 남고,
 * 뒤 장면이 그 위로 서서히 진해진다.
 */
export function scenesAt(timeline: Timeline, seconds: number): { index: number; local: number; alpha: number }[] {
  const out: { index: number; local: number; alpha: number }[] = []
  for (let i = 0; i < timeline.scenes.length; i += 1) {
    const start = timeline.starts[i]
    const end = start + timeline.scenes[i].seconds
    const last = i === timeline.scenes.length - 1
    // 뒤에 장면이 있으면 겹치는 시간만큼 더 남아 있는다
    const until = last ? end : end + CROSSFADE_SEC
    if (seconds < start || seconds >= until) continue
    const local = seconds - start
    const alpha = i > 0 && local < CROSSFADE_SEC ? local / CROSSFADE_SEC : 1
    out.push({ index: i, local, alpha })
  }
  return out
}

/**
 * 사진을 화면에 꽉 차게 그린다.
 *
 * 원본을 그대로 넘겨야 한다 — 크기만 따로 받는다. 이미지 요소를 복사하면
 * (`{...img}`) 캔버스가 그리지 못하는 평범한 객체가 되어 버린다.
 */
function cover(
  ctx: CanvasRenderingContext2D,
  source: CanvasImageSource,
  sw: number,
  sh: number,
  w: number,
  h: number,
  zoom: number,
  drift: number,
) {
  if (!sw || !sh) return
  const scale = Math.max(w / sw, h / sh) * zoom
  const dw = sw * scale
  const dh = sh * scale
  // 천천히 흐르게 — 가로가 남으면 좌우로, 세로가 남으면 위아래로
  const slackX = dw - w
  const slackY = dh - h
  const dx = -slackX / 2 + slackX * 0.5 * drift
  const dy = -slackY / 2 + slackY * 0.5 * drift * 0.6
  ctx.drawImage(source, dx, dy, dw, dh)
}

function wrap(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const words = text.split(' ')
  const lines: string[] = []
  let line = ''
  for (const word of words) {
    const next = line ? `${line} ${word}` : word
    if (ctx.measureText(next).width > maxWidth && line) {
      lines.push(line)
      line = word
    } else {
      line = next
    }
  }
  if (line) lines.push(line)
  return lines.slice(0, 3)
}

export interface RenderOptions {
  width: number
  height: number
  theme: DesignTheme
  academyName: string
}

/** 한 장면을 그린다 (alpha 는 호출하는 쪽에서 이미 걸어 둔다) */
function drawScene(
  ctx: CanvasRenderingContext2D,
  scene: VideoScene,
  local: number,
  sources: FrameSource,
  options: RenderOptions,
) {
  const { width: w, height: h, theme } = options
  const p = theme.palette
  const progress = Math.min(1, local / Math.max(0.001, scene.seconds))

  ctx.fillStyle = p.ink
  ctx.fillRect(0, 0, w, h)

  const media = scene.clip ? sources.videos.get(scene.clip) : scene.image ? sources.images.get(scene.image) : null
  const width = media ? ('videoWidth' in media ? media.videoWidth : media.naturalWidth || media.width) : 0
  const height = media ? ('videoHeight' in media ? media.videoHeight : media.naturalHeight || media.height) : 0
  if (media && width && height) {
    // 켄 번스 — 1.0 에서 1.08 까지 아주 천천히
    cover(ctx, media, width, height, w, h, 1 + progress * 0.08, progress - 0.5)
    // 자막이 읽히도록 아래쪽에 어둠을 깐다
    const scrim = ctx.createLinearGradient(0, h * 0.45, 0, h)
    scrim.addColorStop(0, 'rgba(0,0,0,0)')
    scrim.addColorStop(1, 'rgba(0,0,0,0.72)')
    ctx.fillStyle = scrim
    ctx.fillRect(0, h * 0.45, w, h * 0.55)
  } else {
    // 사진이 없으면 테마 색으로 — 빈 화면이 뜨지 않는다
    const bg = ctx.createLinearGradient(0, 0, w, h)
    bg.addColorStop(0, p.ink)
    bg.addColorStop(1, p.band)
    ctx.fillStyle = bg
    ctx.fillRect(0, 0, w, h)
  }

  const unit = h / 1080
  const pad = 96 * unit
  const centered = !(media && width && height)

  ctx.textBaseline = 'alphabetic'
  ctx.textAlign = centered ? 'center' : 'left'
  const x = centered ? w / 2 : pad
  let y = centered ? h / 2 - 40 * unit : h - pad

  if (centered) {
    // 표지·마무리 — 가운데 정렬
    if (scene.eyebrow) {
      ctx.font = `600 ${Math.round(30 * unit)}px ${theme.fonts.body}`
      ctx.fillStyle = p.accent
      ctx.fillText(scene.eyebrow, x, y - 90 * unit)
    }
    ctx.font = `700 ${Math.round((scene.headline && scene.headline.length > 14 ? 88 : 112) * unit)}px ${theme.fonts.display}`
    ctx.fillStyle = p.paper
    const lines = wrap(ctx, scene.headline ?? '', w - pad * 2)
    lines.forEach((line, index) => ctx.fillText(line, x, y + index * 120 * unit))
    y += lines.length * 120 * unit
    if (scene.sub) {
      ctx.font = `500 ${Math.round(40 * unit)}px ${theme.fonts.body}`
      ctx.fillStyle = p.accentSoft
      ctx.fillText(scene.sub, x, y + 48 * unit)
    }
    return
  }

  // 사진 위 — 아래쪽 자막
  if (scene.sub) {
    ctx.font = `500 ${Math.round(42 * unit)}px ${theme.fonts.body}`
    ctx.fillStyle = 'rgba(255,255,255,0.92)'
    ctx.fillText(scene.sub, x, y)
    y -= 66 * unit
  }
  if (scene.headline) {
    ctx.font = `700 ${Math.round(96 * unit)}px ${theme.fonts.display}`
    ctx.fillStyle = '#ffffff'
    ctx.fillText(scene.headline, x, y)
    y -= 96 * unit
  }
  if (scene.eyebrow) {
    ctx.font = `600 ${Math.round(30 * unit)}px ${theme.fonts.body}`
    ctx.fillStyle = p.accent
    ctx.fillText(scene.eyebrow, x, y)
  }

  // 위쪽 얇은 띠 — 어느 장면이든 학원 것임을 알아보게
  ctx.fillStyle = p.accent
  ctx.fillRect(0, 0, w, 8 * unit)
}

/** 지금 시각의 화면을 통째로 그린다 */
export function renderFrame(
  ctx: CanvasRenderingContext2D,
  timeline: Timeline,
  seconds: number,
  sources: FrameSource,
  options: RenderOptions,
) {
  const { width: w, height: h } = options
  ctx.save()
  ctx.globalAlpha = 1
  ctx.fillStyle = options.theme.palette.ink
  ctx.fillRect(0, 0, w, h)
  for (const { index, local, alpha } of scenesAt(timeline, seconds)) {
    ctx.globalAlpha = alpha
    drawScene(ctx, timeline.scenes[index], local, sources, options)
  }
  ctx.restore()
}

/**
 * 이 브라우저가 뽑을 수 있는 영상 형식 중 가장 널리 열리는 것을 고른다.
 * H.264 MP4 가 첫째다 — 파워포인트에 넣을 수 있고 휴대폰에서도 열린다.
 */
export const RECORD_TYPES = [
  'video/mp4;codecs="avc1.42E01E,mp4a.40.2"',
  'video/mp4;codecs="avc1.4d002a,mp4a.40.2"',
  'video/mp4;codecs=avc1',
  'video/webm;codecs="vp9,opus"',
  'video/webm;codecs="vp8,opus"',
  'video/webm',
  'video/mp4',
]

export function pickRecordType(): string | null {
  if (typeof MediaRecorder === 'undefined') return null
  return RECORD_TYPES.find((type) => MediaRecorder.isTypeSupported(type)) ?? null
}

/** 실제로 만들어진 파일이 무엇인지 — 원장님께 그대로 알려 준다 */
export function describeRecordType(mimeType: string): { ext: string; label: string; note: string } {
  const isMp4 = mimeType.includes('mp4')
  const h264 = /avc1|h264/i.test(mimeType)
  if (isMp4 && h264) {
    return {
      ext: 'mp4',
      label: 'MP4 (H.264)',
      note: '파워포인트에 넣거나 카카오톡으로 보낼 수 있습니다.',
    }
  }
  if (isMp4) {
    return {
      ext: 'mp4',
      label: 'MP4 (VP9)',
      note: '크롬·엣지에서 열립니다. 파워포인트에 넣으려면 크롬 최신판에서 다시 만들어 주세요.',
    }
  }
  return {
    ext: 'webm',
    label: 'WebM',
    note:
      '크롬·엣지에서 열립니다. 재생 막대에 길이가 안 뜰 수 있지만 재생은 됩니다. ' +
      '파워포인트에 넣거나 카카오톡으로 보내시려면 크롬 최신판에서 다시 만들어 주세요.',
  }
}
