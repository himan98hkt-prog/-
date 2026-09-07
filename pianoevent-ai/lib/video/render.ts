import type { DesignTheme } from '@/lib/design/themes'
import type { PhotoShape } from '@/lib/stage/layouts'
import { drawBackdrop, hexAlpha } from '@/lib/video/backdrop-canvas'
import { isCalmScene, type SceneIconId, type VideoScene } from '@/lib/video/storyboard'
import {
  DEFAULT_VIDEO_TEMPLATE,
  resolveTransition,
  type PhotoMotion,
  type TransitionKind,
  type VideoTemplate,
} from '@/lib/video/templates'

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
/** 자막이 떠오르는 시간(초) */
export const CAPTION_FADE_SEC = 0.35

/**
 * 이 장면으로 넘어올 때 겹치는 시간.
 * 장면이 짧으면 겹치는 구간이 장면의 절반을 먹는다 — 길이에 맞춰 줄인다.
 */
export function fadeFor(seconds: number): number {
  return Math.min(CROSSFADE_SEC, Math.max(0.15, seconds * 0.25))
}

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

export interface VisibleScene {
  index: number
  local: number
  /** 그림의 진하기 */
  alpha: number
  /**
   * 글자의 진하기.
   *
   * 넘어가는 동안 두 장면의 자막이 함께 읽히면 이름이 겹쳐 찍힌 것처럼 보인다.
   * 그래서 그림만 겹쳐 넘기고, 자막은 **넘어가기가 끝난 뒤에** 떠오르게 한다.
   */
  textAlpha: number
  /**
   * 이 장면으로 넘어오는 중인가 — 0(막 시작) ~ 1(다 들어옴).
   * 1 이면 넘어옴이 끝나 제자리에 있는 장면이다.
   */
  enter: number
  /** 어떤 방식으로 넘어오는가 */
  transition: TransitionKind
}

/**
 * 지금 시각에 보이는 장면.
 *
 * 넘어가는 동안에는 앞 장면이 아래에 그대로 남고 뒤 장면이 그 위로 진해진다.
 * 앞 장면이 먼저 사라지면 그 사이 바탕색이 비쳐 화면이 한 번 껌뻑인다.
 */
export function scenesAt(timeline: Timeline, seconds: number): VisibleScene[] {
  const out: VisibleScene[] = []
  for (let i = 0; i < timeline.scenes.length; i += 1) {
    const scene = timeline.scenes[i]
    const start = timeline.starts[i]
    const end = start + scene.seconds
    const last = i === timeline.scenes.length - 1
    const nextFade = last ? 0 : fadeFor(timeline.scenes[i + 1].seconds)
    const until = last ? end : end + nextFade
    if (seconds < start || seconds >= until) continue

    const local = seconds - start
    const fadeIn = i > 0 ? fadeFor(scene.seconds) : 0
    const alpha = fadeIn > 0 && local < fadeIn ? local / fadeIn : 1

    let textAlpha: number
    if (local > scene.seconds) {
      // 제 시간이 끝나 아래에 남아 있는 장면 — 자막은 먼저 걷는다
      textAlpha = Math.max(0, 1 - (local - scene.seconds) / Math.max(0.001, nextFade))
    } else if (local < fadeIn) {
      textAlpha = 0
    } else {
      textAlpha = Math.min(1, (local - fadeIn) / CAPTION_FADE_SEC)
    }

    const enter = fadeIn > 0 ? Math.min(1, local / fadeIn) : 1
    out.push({
      index: i,
      local,
      alpha,
      textAlpha,
      enter,
      transition: resolveTransition(scene.transition, i, isCalmScene(scene.kind)),
    })
  }
  return out
}

function cover(
  ctx: CanvasRenderingContext2D,
  source: CanvasImageSource,
  sw: number,
  sh: number,
  w: number,
  h: number,
  zoom: number,
  drift: number,
  originX = 0,
  originY = 0,
) {
  if (!sw || !sh) return
  const scale = Math.max(w / sw, h / sh) * zoom
  const dw = sw * scale
  const dh = sh * scale
  // 천천히 흐르게 — 가로가 남으면 좌우로, 세로가 남으면 위아래로
  const slackX = dw - w
  const slackY = dh - h
  const dx = originX - slackX / 2 + slackX * 0.5 * drift
  const dy = originY - slackY / 2 + slackY * 0.5 * drift * 0.6
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

/** 학원 로고를 화면 어느 구석에 둘지 */
export type LogoPlace = 'none' | 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'

export const LOGO_PLACES: { id: LogoPlace; label: string }[] = [
  { id: 'none', label: '넣지 않기' },
  { id: 'top-left', label: '왼쪽 위' },
  { id: 'top-right', label: '오른쪽 위' },
  { id: 'bottom-left', label: '왼쪽 아래' },
  { id: 'bottom-right', label: '오른쪽 아래' },
]

export function getLogoPlace(id: string | null | undefined): LogoPlace {
  return LOGO_PLACES.some((item) => item.id === id) ? (id as LogoPlace) : 'none'
}

/** 화면에 얹는 학원 로고 — 이미 다 읽어 둔 것만 받는다 */
export interface LogoMark {
  image: CanvasImageSource
  width: number
  height: number
  place: LogoPlace
}

export interface RenderOptions {
  width: number
  height: number
  theme: DesignTheme
  academyName: string
  /** 영상 템플릿 — 사진을 어떻게 놓고 어떤 배경을 깔지 */
  template?: VideoTemplate
  /**
   * 학원 로고.
   *
   * 무대 화면에는 학원 로고가 들어가는데 영상에는 빠져 있었다.
   * 영상은 학부모 휴대폰으로 돌아다니는 물건이라, 구석에 작게라도 있어야
   * 어느 학원 것인지 남는다. 장면 위에 **따로** 그린다 —
   * 장면이 겹쳐 넘어갈 때 로고까지 깜빡이면 눈에 거슬린다.
   */
  logo?: LogoMark | null
}

/** 로고를 화면 구석에 그린다. 화면 높이의 7% 남짓 — 있는 줄은 알되 방해하지 않는 크기 */
export function drawLogo(ctx: CanvasRenderingContext2D, logo: LogoMark, w: number, h: number) {
  if (logo.place === 'none' || !logo.width || !logo.height) return
  const boxH = h * 0.072
  const scale = boxH / logo.height
  const drawW = logo.width * scale
  const drawH = boxH
  const margin = h * 0.045
  const top = logo.place === 'top-left' || logo.place === 'top-right'
  const left = logo.place === 'top-left' || logo.place === 'bottom-left'
  const x = left ? margin : w - margin - drawW
  const y = top ? margin : h - margin - drawH

  ctx.save()
  ctx.globalAlpha = 0.9
  // 밝은 사진 위에서도 로고가 보이도록 아주 옅은 그림자만 깐다
  ctx.shadowColor = 'rgba(0,0,0,0.45)'
  ctx.shadowBlur = h * 0.02
  ctx.drawImage(logo.image, x, y, drawW, drawH)
  ctx.restore()
}

/** 사진 창 모양대로 캔버스에 길을 낸다 (그 안에만 그려진다) */
function shapePath(ctx: CanvasRenderingContext2D, shape: PhotoShape, x: number, y: number, w: number, h: number) {
  const r = Math.min(w, h)
  ctx.beginPath()
  switch (shape) {
    case 'circle':
      ctx.arc(x + w / 2, y + h / 2, r / 2, 0, Math.PI * 2)
      return
    case 'oval':
      ctx.ellipse(x + w / 2, y + h / 2, w / 2, h * 0.42, 0, 0, Math.PI * 2)
      return
    case 'hexagon': {
      const pts: [number, number][] = [
        [0.5, 0],
        [0.95, 0.25],
        [0.95, 0.75],
        [0.5, 1],
        [0.05, 0.75],
        [0.05, 0.25],
      ]
      pts.forEach(([fx, fy], i) => {
        const px = x + fx * w
        const py = y + fy * h
        if (i === 0) ctx.moveTo(px, py)
        else ctx.lineTo(px, py)
      })
      ctx.closePath()
      return
    }
    case 'diamond':
      ctx.moveTo(x + w / 2, y)
      ctx.lineTo(x + w, y + h / 2)
      ctx.lineTo(x + w / 2, y + h)
      ctx.lineTo(x, y + h / 2)
      ctx.closePath()
      return
    case 'arch': {
      const top = Math.min(w / 2, h * 0.42)
      ctx.moveTo(x, y + h)
      ctx.lineTo(x, y + top)
      ctx.ellipse(x + w / 2, y + top, w / 2, top, 0, Math.PI, 0)
      ctx.lineTo(x + w, y + h)
      ctx.closePath()
      return
    }
    case 'leaf': {
      const c = r * 0.48
      ctx.moveTo(x + c, y)
      ctx.lineTo(x + w, y)
      ctx.lineTo(x + w, y + h - c)
      ctx.quadraticCurveTo(x + w, y + h, x + w - c, y + h)
      ctx.lineTo(x, y + h)
      ctx.lineTo(x, y + c)
      ctx.quadraticCurveTo(x, y, x + c, y)
      ctx.closePath()
      return
    }
    case 'rounded': {
      const c = Math.min(36 * (h / 720), r / 2)
      ctx.moveTo(x + c, y)
      ctx.arcTo(x + w, y, x + w, y + h, c)
      ctx.arcTo(x + w, y + h, x, y + h, c)
      ctx.arcTo(x, y + h, x, y, c)
      ctx.arcTo(x, y, x + w, y, c)
      ctx.closePath()
      return
    }
    default:
      ctx.rect(x, y, w, h)
  }
}

/** 템플릿이 정한 움직임 — 사진이 살아 있는 것처럼 보이게 하는 최소한의 장치 */
function motionOf(motion: PhotoMotion, progress: number): { zoom: number; drift: number } {
  switch (motion) {
    case 'in':
      return { zoom: 1 + progress * 0.08, drift: progress - 0.5 }
    case 'out':
      return { zoom: 1.08 - progress * 0.08, drift: 0.5 - progress }
    case 'left':
      return { zoom: 1.06, drift: 0.5 - progress }
    case 'right':
      return { zoom: 1.06, drift: progress - 0.5 }
    case 'still':
      return { zoom: 1.01, drift: 0 }
  }
}

/** 한 장면 안에서 사진이 넘어갈 때 겹치는 시간(초) */
export const PHOTO_BLEND_SEC = 0.4

/** 이 장면에서 보여 줄 사진들 (한 장뿐이면 한 장짜리 목록) */
export function sceneShots(scene: VideoScene): string[] {
  if (scene.images && scene.images.length > 0) return scene.images
  return scene.image ? [scene.image] : []
}

/**
 * 한 장면에 사진이 여러 장이면 시간을 똑같이 나눠 갖는다.
 *
 * 넘어갈 때는 앞 사진 위로 다음 사진이 진해진다 — 딱 끊기면 사진이
 * "바뀐" 게 아니라 화면이 "튄" 것처럼 보인다.
 */
export function photoSlot(count: number, seconds: number, local: number): { index: number; alpha: number } {
  if (count <= 1) return { index: 0, alpha: 1 }
  const span = seconds / count
  const index = Math.min(count - 1, Math.max(0, Math.floor(local / Math.max(0.001, span))))
  if (index === 0) return { index, alpha: 1 }
  const into = local - index * span
  const blend = Math.min(PHOTO_BLEND_SEC, span * 0.5)
  return { index, alpha: blend > 0 ? Math.min(1, into / blend) : 1 }
}

/** 한 장면을 그린다 (alpha 는 호출하는 쪽에서 이미 걸어 둔다) */
function drawScene(
  ctx: CanvasRenderingContext2D,
  scene: VideoScene,
  local: number,
  sources: FrameSource,
  options: RenderOptions,
  textAlpha: number,
) {
  const { width: w, height: h, theme } = options
  const template = options.template ?? DEFAULT_VIDEO_TEMPLATE
  const p = theme.palette
  const progress = Math.min(1, local / Math.max(0.001, scene.seconds))
  const unitScale = h / 720

  ctx.fillStyle = p.ink
  ctx.fillRect(0, 0, w, h)

  const shots = scene.clip ? [] : sceneShots(scene)
  const slot = photoSlot(shots.length, scene.seconds, local)
  const media = scene.clip
    ? sources.videos.get(scene.clip)
    : shots[slot.index]
      ? sources.images.get(shots[slot.index])
      : null
  // 넘어가는 중이면 앞 사진이 아래에 남는다
  const under = slot.alpha < 1 && shots[slot.index - 1] ? sources.images.get(shots[slot.index - 1]) : null
  const width = media ? ('videoWidth' in media ? media.videoWidth : media.naturalWidth || media.width) : 0
  const height = media ? ('videoHeight' in media ? media.videoHeight : media.naturalHeight || media.height) : 0
  // 동영상은 늘 꽉 채운다 — 액자에 담으면 원장님이 찍은 영상이 작아진다
  const fit = scene.clip ? 'full' : template.fit
  // 장면마다 고르신 움직임이 템플릿보다 우선한다
  const { zoom, drift } = motionOf(scene.motion ?? template.motion, progress)

  /**
   * 사진 한 장을 그린다. 장면 안에서 사진이 넘어가는 중이면 두 번 불린다 —
   * 앞 사진을 그대로 깔고 그 위에 다음 사진을 진하게.
   */
  const paint = (target: CanvasImageSource, tw: number, th: number, ox = 0, oy = 0, alpha = 1) => {
    if (alpha >= 1) {
      cover(ctx, target, width, height, tw, th, zoom, drift, ox, oy)
      return
    }
    ctx.save()
    ctx.globalAlpha *= alpha
    cover(ctx, target, width, height, tw, th, zoom, drift, ox, oy)
    ctx.restore()
  }
  const paintPair = (tw: number, th: number, ox = 0, oy = 0) => {
    if (!media) return
    if (under) {
      const uw = 'naturalWidth' in under ? under.naturalWidth || under.width : width
      const uh = 'naturalHeight' in under ? under.naturalHeight || under.height : height
      cover(ctx, under, uw, uh, tw, th, zoom, drift, ox, oy)
    }
    paint(media, tw, th, ox, oy, under ? slot.alpha : 1)
  }

  if (media && width && height && fit !== 'full') {
    // 배경을 먼저 깔고 그 위에 사진을 액자로 얹는다
    const bg = ctx.createLinearGradient(0, 0, w, h)
    bg.addColorStop(0, p.ink)
    bg.addColorStop(1, p.band)
    ctx.fillStyle = bg
    ctx.fillRect(0, 0, w, h)
    drawBackdrop(ctx, template.backdrop, theme, w, h)

    if (fit === 'half') {
      const halfW = w * 0.52
      ctx.save()
      ctx.beginPath()
      ctx.rect(0, 0, halfW, h)
      ctx.clip()
      paintPair(halfW, h)
      ctx.restore()
    } else {
      // frame · polaroid — 가운데 왼쪽에 정사각 액자
      const box = Math.min(h * 0.62, w * 0.42)
      const bx = fit === 'polaroid' ? w * 0.5 - box / 2 : w * 0.28 - box / 2
      const by = h * 0.42 - box / 2
      if (fit === 'polaroid') {
        // 인화지 — 하얀 테를 두르고 살짝 기울인다
        ctx.save()
        ctx.translate(bx + box / 2, by + box / 2)
        ctx.rotate((-2.5 * Math.PI) / 180)
        ctx.translate(-(bx + box / 2), -(by + box / 2))
        ctx.fillStyle = p.paper
        ctx.shadowColor = 'rgba(0,0,0,0.45)'
        ctx.shadowBlur = 30 * unitScale
        ctx.shadowOffsetY = 14 * unitScale
        ctx.fillRect(bx - 18 * unitScale, by - 18 * unitScale, box + 36 * unitScale, box + 78 * unitScale)
        ctx.shadowColor = 'transparent'
        ctx.save()
        ctx.beginPath()
        ctx.rect(bx, by, box, box)
        ctx.clip()
        paintPair(box, box, bx, by)
        ctx.restore()
        ctx.restore()
      } else {
        // 액자 테 — 사진과 같은 모양으로 한 겹
        ctx.save()
        ctx.fillStyle = p.accent
        shapePath(ctx, template.shape, bx - 14 * unitScale, by - 14 * unitScale, box + 28 * unitScale, box + 28 * unitScale)
        ctx.fill()
        ctx.fillStyle = p.paper
        shapePath(ctx, template.shape, bx - 7 * unitScale, by - 7 * unitScale, box + 14 * unitScale, box + 14 * unitScale)
        ctx.fill()
        ctx.restore()
        ctx.save()
        shapePath(ctx, template.shape, bx, by, box, box)
        ctx.clip()
        paintPair(box, box, bx, by)
        ctx.restore()
      }
    }
    if (template.dim > 0) {
      ctx.fillStyle = `rgba(0,0,0,${template.dim})`
      ctx.fillRect(0, 0, w, h)
    }
  } else if (media && width && height) {
    paintPair(w, h)
    // 사진 위에 무대 배경을 얹는다 (조명·별밤처럼 겹쳐 쓰는 배경)
    drawBackdrop(ctx, template.backdrop, theme, w, h)
    if (template.dim > 0) {
      ctx.fillStyle = `rgba(0,0,0,${template.dim})`
      ctx.fillRect(0, 0, w, h)
    }
    // 자막이 읽히도록 그 자리에 어둠을 깐다
    const place = scene.caption ?? template.caption
    if (place === 'bottom') {
      const shade = ctx.createLinearGradient(0, h * 0.45, 0, h)
      shade.addColorStop(0, 'rgba(0,0,0,0)')
      shade.addColorStop(1, 'rgba(0,0,0,0.72)')
      ctx.fillStyle = shade
      ctx.fillRect(0, h * 0.45, w, h * 0.55)
    } else if (place === 'top') {
      const shade = ctx.createLinearGradient(0, 0, 0, h * 0.5)
      shade.addColorStop(0, 'rgba(0,0,0,0.78)')
      shade.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = shade
      ctx.fillRect(0, 0, w, h * 0.5)
    } else if (place === 'center') {
      ctx.fillStyle = 'rgba(0,0,0,0.42)'
      ctx.fillRect(0, 0, w, h)
    }
  } else {
    // 사진이 없으면 테마 색과 무대 배경으로 — 빈 화면이 뜨지 않는다
    const bg = ctx.createLinearGradient(0, 0, w, h)
    bg.addColorStop(0, p.ink)
    bg.addColorStop(1, p.band)
    ctx.fillStyle = bg
    ctx.fillRect(0, 0, w, h)
    drawBackdrop(ctx, template.backdrop, theme, w, h)
  }

  const unit = h / 1080
  const pad = 96 * unit
  // 액자·반쪽 템플릿은 사진이 화면을 다 덮지 않으므로 글자를 가운데 정렬하지 않는다
  const centered = !(media && width && height)

  // 액자·반쪽 템플릿은 사진이 왼쪽에 있으므로 글자를 오른쪽 빈자리에 놓는다
  const textLeft = fit === 'frame' ? w * 0.54 : fit === 'half' ? w * 0.57 : pad
  const textWidth = (centered ? w : w - textLeft) - pad
  ctx.textBaseline = 'alphabetic'
  ctx.textAlign = centered ? 'center' : 'left'
  const x = centered ? w / 2 : textLeft
  let y = h - pad

  // 위쪽 얇은 띠 — 어느 장면이든 학원 것임을 알아보게 (그림에 속하므로 자막과 함께 흐려지지 않는다)
  ctx.fillStyle = p.accent
  ctx.fillRect(0, 0, w, 8 * unit)

  // 여기서부터는 글자다 — 넘어가는 동안에는 흐리게 두어 두 이름이 겹쳐 읽히지 않게 한다
  const sceneAlpha = ctx.globalAlpha
  ctx.globalAlpha = sceneAlpha * textAlpha

  if (centered) {
    // 표지·마무리 — 글자 덩어리 전체 높이를 재서 가운데에 놓는다.
    // 눈대중으로 밀면 학원 이름이 제목 위에 겹쳐 찍힌다.
    const eyebrowSize = 30 * unit
    const titleSize = Math.round((scene.headline && scene.headline.length > 14 ? 88 : 112) * unit)
    const subSize = 40 * unit
    const lineStep = titleSize * 1.18
    const gapAfterEyebrow = 46 * unit
    const gapBeforeSub = 54 * unit

    ctx.font = `700 ${titleSize}px ${theme.fonts.display}`
    const lines = wrap(ctx, scene.headline ?? '', w - pad * 2)

    // 응원을 보내 주신 분의 아이 얼굴 — 글 위에 동그랗게 작게
    const badgeImg = scene.badge ? sources.images.get(scene.badge) : null
    const badgeSize = badgeImg ? h * 0.2 : 0
    const gapAfterBadge = badgeImg ? 40 * unit : 0

    const blockHeight =
      badgeSize +
      gapAfterBadge +
      (scene.eyebrow ? eyebrowSize + gapAfterEyebrow : 0) +
      lines.length * lineStep +
      (scene.sub ? gapBeforeSub + subSize : 0)

    let top = h / 2 - blockHeight / 2

    if (badgeImg && badgeSize > 0) {
      const bw = badgeImg.naturalWidth || badgeImg.width
      const bh = badgeImg.naturalHeight || badgeImg.height
      const bx = w / 2 - badgeSize / 2
      ctx.save()
      // 테를 한 겹 둘러 어두운 바탕에서도 얼굴이 떠 보이게
      ctx.fillStyle = p.accent
      ctx.beginPath()
      ctx.arc(w / 2, top + badgeSize / 2, badgeSize / 2 + 4 * unit, 0, Math.PI * 2)
      ctx.fill()
      ctx.beginPath()
      ctx.arc(w / 2, top + badgeSize / 2, badgeSize / 2, 0, Math.PI * 2)
      ctx.clip()
      cover(ctx, badgeImg, bw, bh, badgeSize, badgeSize, 1, 0, bx, top)
      ctx.restore()
      top += badgeSize + gapAfterBadge
    }

    if (scene.eyebrow) {
      ctx.font = `600 ${Math.round(eyebrowSize)}px ${theme.fonts.body}`
      ctx.fillStyle = p.accent
      ctx.fillText(scene.eyebrow, x, top + eyebrowSize)
      top += eyebrowSize + gapAfterEyebrow
    }

    ctx.font = `700 ${titleSize}px ${theme.fonts.display}`
    ctx.fillStyle = p.paper
    lines.forEach((line, index) => ctx.fillText(line, x, top + titleSize * 0.86 + index * lineStep))
    top += lines.length * lineStep

    if (scene.sub) {
      ctx.font = `500 ${Math.round(subSize)}px ${theme.fonts.body}`
      ctx.fillStyle = p.accentSoft
      ctx.fillText(scene.sub, x, top + gapBeforeSub + subSize * 0.8)
    }
    return
  }

  // 사진 위 자막 — 자리는 장면마다 고른다 (얼굴을 가리지 않게)
  const place = scene.caption ?? template.caption
  if (place === 'none') {
    ctx.globalAlpha = sceneAlpha
    return
  }

  const headlineSize = Math.round(96 * unit)
  const subSize = Math.round(42 * unit)
  const eyebrowSize = Math.round(30 * unit)

  if (place === 'center') {
    // 가운데 — 감동 문구를 화면 한가운데 크게
    ctx.textAlign = 'center'
    const cx = w / 2
    const lines = (() => {
      ctx.font = `700 ${headlineSize}px ${theme.fonts.display}`
      return wrap(ctx, scene.headline ?? '', w - pad * 2)
    })()
    const step = headlineSize * 1.2
    const blockH = lines.length * step + (scene.sub ? subSize * 2 : 0)
    let top = h / 2 - blockH / 2
    ctx.font = `700 ${headlineSize}px ${theme.fonts.display}`
    ctx.fillStyle = '#ffffff'
    lines.forEach((line, index) => ctx.fillText(line, cx, top + headlineSize * 0.86 + index * step))
    top += lines.length * step
    if (scene.sub) {
      ctx.font = `500 ${subSize}px ${theme.fonts.body}`
      ctx.fillStyle = 'rgba(255,255,255,0.92)'
      ctx.fillText(scene.sub, cx, top + subSize)
    }
    ctx.globalAlpha = sceneAlpha
    return
  }

  if (place === 'top') {
    let top = pad * 0.7
    if (scene.eyebrow) {
      ctx.font = `600 ${eyebrowSize}px ${theme.fonts.body}`
      ctx.fillStyle = p.accent
      ctx.fillText(scene.eyebrow, x, top + eyebrowSize)
      top += eyebrowSize + 18 * unit
    }
    if (scene.headline) {
      ctx.font = `700 ${headlineSize}px ${theme.fonts.display}`
      ctx.fillStyle = '#ffffff'
      const lines = wrap(ctx, scene.headline, textWidth)
      lines.forEach((line, index) => ctx.fillText(line, x, top + headlineSize * 0.86 + index * headlineSize * 1.14))
      top += headlineSize * (1 + (lines.length - 1) * 1.14) + 10 * unit
    }
    if (scene.sub) {
      ctx.font = `500 ${subSize}px ${theme.fonts.body}`
      ctx.fillStyle = 'rgba(255,255,255,0.92)'
      ctx.fillText(scene.sub, x, top + subSize * 0.9)
    }
    ctx.globalAlpha = sceneAlpha
    return
  }

  // bottom — 아래에서 위로 쌓는다
  if (scene.sub) {
    ctx.font = `500 ${subSize}px ${theme.fonts.body}`
    ctx.fillStyle = 'rgba(255,255,255,0.92)'
    ctx.fillText(scene.sub, x, y)
    y -= 66 * unit
  }
  if (scene.headline) {
    ctx.font = `700 ${headlineSize}px ${theme.fonts.display}`
    ctx.fillStyle = '#ffffff'
    ctx.fillText(scene.headline, x, y)
    y -= 96 * unit
  }
  if (scene.eyebrow) {
    ctx.font = `600 ${eyebrowSize}px ${theme.fonts.body}`
    ctx.fillStyle = p.accent
    ctx.fillText(scene.eyebrow, x, y)
  }
  ctx.globalAlpha = sceneAlpha
}

/** 지금 시각의 화면을 통째로 그린다 */
/**
 * 넘어오는 장면을 어떻게 얹을 것인가.
 *
 * 캔버스에서 할 수 있는 일은 결국 셋이다 — **옮기기 · 키우기 · 오려내기**.
 * 그 셋을 조합해 전환을 만든다. 밖에서 라이브러리를 가져오지 않으므로
 * 인터넷 없이도 돌고, 설치본이 무거워지지 않는다.
 *
 * `enter` 는 0(막 들어옴) → 1(제자리). 부드럽게 보이도록 가속을 한 번 먹인다.
 */
function easeOut(t: number): number {
  const p = Math.min(1, Math.max(0, t))
  return 1 - (1 - p) * (1 - p) * (1 - p)
}

/**
 * 전환에 맞춰 붓을 옮겨 두고, 남은 진하기를 돌려준다.
 *
 * 돌려주는 값을 그대로 `globalAlpha` 로 쓴다 — 밀기·오려내기처럼 **자리로 보여 주는**
 * 전환은 1을 돌려준다(반투명하게 겹치면 두 장면이 비쳐 지저분해진다).
 */
export function applyTransition(
  ctx: CanvasRenderingContext2D,
  kind: TransitionKind,
  enter: number,
  alpha: number,
  w: number,
  h: number,
): number {
  if (enter >= 1) return alpha
  const p = easeOut(enter)

  switch (kind) {
    case 'slide-left':
      ctx.translate((1 - p) * w, 0)
      return 1
    case 'slide-right':
      ctx.translate(-(1 - p) * w, 0)
      return 1
    case 'slide-up':
      ctx.translate(0, (1 - p) * h)
      return 1
    case 'slide-down':
      ctx.translate(0, -(1 - p) * h)
      return 1
    case 'zoom-in': {
      const scale = 0.72 + 0.28 * p
      ctx.translate(w / 2, h / 2)
      ctx.scale(scale, scale)
      ctx.translate(-w / 2, -h / 2)
      return p
    }
    case 'zoom-out': {
      const scale = 1.35 - 0.35 * p
      ctx.translate(w / 2, h / 2)
      ctx.scale(scale, scale)
      ctx.translate(-w / 2, -h / 2)
      return p
    }
    case 'circle': {
      // 모서리까지 덮으려면 대각선의 절반이 필요하다
      const radius = Math.hypot(w, h) / 2
      ctx.beginPath()
      ctx.arc(w / 2, h / 2, radius * p, 0, Math.PI * 2)
      ctx.clip()
      return 1
    }
    case 'wipe': {
      ctx.beginPath()
      ctx.rect(0, 0, w * p, h)
      ctx.clip()
      return 1
    }
    case 'blinds': {
      const bands = 8
      const band = h / bands
      ctx.beginPath()
      for (let i = 0; i < bands; i += 1) ctx.rect(0, i * band, w, band * p)
      ctx.clip()
      return 1
    }
    case 'fade':
    case 'auto':
    default:
      return alpha
  }
}

/**
 * 장면에 얹는 작은 그림 — 전부 선으로 그린다.
 *
 * 그림 파일을 가져오면 저작권을 확인해야 하고 설치본도 무거워진다.
 * 선으로 그리면 테마 강조색을 그대로 입고, 아무리 키워도 안 깨진다.
 */
function iconPath(ctx: CanvasRenderingContext2D, id: SceneIconId, s: number) {
  const p = new Path2D()
  switch (id) {
    case 'heart':
      p.moveTo(0, s * 0.32)
      p.bezierCurveTo(-s * 0.9, -s * 0.35, -s * 0.35, -s * 0.95, 0, -s * 0.4)
      p.bezierCurveTo(s * 0.35, -s * 0.95, s * 0.9, -s * 0.35, 0, s * 0.32)
      break
    case 'note':
      p.ellipse(-s * 0.28, s * 0.5, s * 0.32, s * 0.24, -0.35, 0, Math.PI * 2)
      p.moveTo(s * 0.02, s * 0.5)
      p.lineTo(s * 0.02, -s * 0.7)
      p.lineTo(s * 0.62, -s * 0.5)
      p.lineTo(s * 0.62, -s * 0.22)
      p.lineTo(s * 0.02, -s * 0.42)
      break
    case 'star':
    case 'sparkle': {
      const points = id === 'star' ? 5 : 4
      const inner = id === 'star' ? 0.42 : 0.24
      for (let i = 0; i < points * 2; i += 1) {
        const r = i % 2 === 0 ? s : s * inner
        const a = (Math.PI / points) * i - Math.PI / 2
        const x = Math.cos(a) * r
        const y = Math.sin(a) * r
        if (i === 0) p.moveTo(x, y)
        else p.lineTo(x, y)
      }
      p.closePath()
      break
    }
    case 'flower':
      for (let i = 0; i < 6; i += 1) {
        const a = (Math.PI / 3) * i
        p.moveTo(0, 0)
        p.ellipse(Math.cos(a) * s * 0.45, Math.sin(a) * s * 0.45, s * 0.3, s * 0.18, a, 0, Math.PI * 2)
      }
      break
    case 'clap':
      for (let i = 0; i < 3; i += 1) {
        const a = -Math.PI / 2 + (i - 1) * 0.55
        p.moveTo(Math.cos(a) * s * 0.35, Math.sin(a) * s * 0.35)
        p.lineTo(Math.cos(a) * s, Math.sin(a) * s)
      }
      p.moveTo(-s * 0.5, s * 0.55)
      p.quadraticCurveTo(0, s * 0.15, s * 0.5, s * 0.55)
      break
    case 'trophy':
      p.moveTo(-s * 0.5, -s * 0.7)
      p.lineTo(s * 0.5, -s * 0.7)
      p.lineTo(s * 0.34, s * 0.1)
      p.lineTo(-s * 0.34, s * 0.1)
      p.closePath()
      p.moveTo(-s * 0.18, s * 0.1)
      p.lineTo(-s * 0.18, s * 0.5)
      p.lineTo(s * 0.18, s * 0.5)
      p.lineTo(s * 0.18, s * 0.1)
      p.moveTo(-s * 0.55, s * 0.7)
      p.lineTo(s * 0.55, s * 0.7)
      break
    case 'ribbon':
      p.ellipse(0, -s * 0.3, s * 0.42, s * 0.42, 0, 0, Math.PI * 2)
      p.moveTo(-s * 0.24, s * 0.05)
      p.lineTo(-s * 0.44, s * 0.85)
      p.lineTo(0, s * 0.5)
      p.lineTo(s * 0.44, s * 0.85)
      p.lineTo(s * 0.24, s * 0.05)
      break
    case 'piano':
      p.rect(-s, -s * 0.5, s * 2, s)
      for (let i = 1; i < 5; i += 1) {
        const x = -s + (s * 2 * i) / 5
        p.moveTo(x, -s * 0.5)
        p.lineTo(x, s * 0.5)
      }
      break
    case 'cake':
      p.rect(-s * 0.75, -s * 0.1, s * 1.5, s * 0.8)
      p.moveTo(-s * 0.75, s * 0.2)
      p.lineTo(s * 0.75, s * 0.2)
      p.moveTo(0, -s * 0.1)
      p.lineTo(0, -s * 0.6)
      break
  }
  return p
}

export interface IconMark {
  id: SceneIconId
  /** 화면 짧은 변 대비 크기 (0.08 = 아담, 0.2 = 큼) */
  size: number
  color: string
}

export function drawSceneIcon(ctx: CanvasRenderingContext2D, mark: IconMark, w: number, h: number, alpha: number) {
  const s = Math.min(w, h) * mark.size
  const pad = Math.min(w, h) * 0.07
  ctx.save()
  ctx.globalAlpha = alpha
  ctx.translate(w - pad - s, pad + s)
  ctx.lineWidth = Math.max(2, s * 0.1)
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.strokeStyle = mark.color
  ctx.fillStyle = hexAlpha(mark.color, 0.18)
  const path = iconPath(ctx, mark.id, s)
  ctx.fill(path)
  ctx.stroke(path)
  ctx.restore()
}

export function renderFrame(
  ctx: CanvasRenderingContext2D,
  timeline: Timeline,
  seconds: number,
  sources: FrameSource,
  options: RenderOptions,
  /**
   * 멈춰 있는 화면인가.
   *
   * 재생 중에는 장면이 서로 겹치며 넘어가고 자막도 뒤늦게 떠오른다.
   * 그런데 **멈춰서 보고 있을 때** 그 순간이 하필 넘어가는 중이면,
   * 들어오는 장면은 아직 투명(0)이라 원장님 눈에는 **앞 장면 사진에 글자가 없는**
   * 이상한 화면이 뜬다. 콘티에서 장면을 눌렀을 때가 딱 그 지점이다.
   *
   * 그래서 멈춘 화면에서는 겹침을 걷어내고 **그 장면 하나만 또렷하게** 그린다.
   */
  still = false,
) {
  const { width: w, height: h } = options
  ctx.save()
  ctx.globalAlpha = 1
  ctx.fillStyle = options.theme.palette.ink
  ctx.fillRect(0, 0, w, h)
  const visible = scenesAt(timeline, seconds)

  if (still) {
    const front = visible[visible.length - 1]
    if (front) {
      ctx.globalAlpha = 1
      drawScene(ctx, timeline.scenes[front.index], front.local, sources, options, 1)
    }
  } else {
    for (const { index, local, alpha, textAlpha, enter, transition } of visible) {
      ctx.save()
      // 옮기기·오려내기는 붓을 움직이므로, 장면마다 되돌려 놓아야 다음 장면이 어긋나지 않는다
      ctx.globalAlpha = applyTransition(ctx, transition, enter, alpha, w, h)
      drawScene(ctx, timeline.scenes[index], local, sources, options, textAlpha)
      ctx.restore()
    }
  }

  /*
   * 작은 그림은 **맨 앞 장면 것만** 얹는다.
   *
   * 겹쳐 넘어가는 동안 두 장면의 그림이 함께 뜨면 화면 구석이 어수선해진다.
   * 자막을 늦게 띄우는 것과 같은 이유다.
   */
  const front = visible[visible.length - 1]
  const frontScene = front ? timeline.scenes[front.index] : null
  if (frontScene?.icon) {
    drawSceneIcon(
      ctx,
      { id: frontScene.icon, size: 0.11, color: options.theme.palette.accent },
      w,
      h,
      still ? 1 : front!.textAlpha,
    )
  }

  // 로고는 장면 위에 한 번만 — 겹쳐 넘어가는 동안에도 그대로 붙어 있다
  if (options.logo) {
    ctx.globalAlpha = 1
    drawLogo(ctx, options.logo, w, h)
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
