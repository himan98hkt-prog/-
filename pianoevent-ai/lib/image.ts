/**
 * 브라우저에서 이미지를 줄여 data URI 로 바꾼다.
 *
 * 원장이 휴대폰으로 찍은 사진은 4~8MB 다. 그대로 저장하면 인쇄물 화면이 느려지고
 * 저장소가 금방 찬다. 인쇄에 필요한 해상도(A4 폭 기준 약 1600px)까지만 줄인다.
 */

export interface ShrinkOptions {
  /** 긴 변 최대 픽셀 */
  maxEdge: number
  /** JPEG 품질 (0~1) */
  quality: number
}

export const PHOTO_SHRINK: ShrinkOptions = { maxEdge: 1600, quality: 0.82 }
export const LOGO_SHRINK: ShrinkOptions = { maxEdge: 512, quality: 0.92 }
/**
 * 학생 얼굴 사진 — 한 반이 30명이면 30장이 보관함에 들어간다.
 * 무대 화면(1280×720)과 영상(1920×1080)에 쓰기에 충분하면서 저장소를 채우지 않는 크기.
 */
export const FACE_SHRINK: ShrinkOptions = { maxEdge: 1000, quality: 0.78 }

export function shrinkOptionsFor(kind: 'logo' | 'symbol' | 'photo'): ShrinkOptions {
  return kind === 'photo' ? PHOTO_SHRINK : LOGO_SHRINK
}

/** SVG 는 이미 벡터라 줄일 것이 없다. 그대로 data URI 로 읽는다. */
function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(new Error('파일을 읽지 못했습니다.'))
    reader.readAsDataURL(file)
  })
}

export async function shrinkImage(file: File, options: ShrinkOptions): Promise<string> {
  if (!file.type.startsWith('image/')) {
    throw new Error('이미지 파일만 올릴 수 있습니다. (jpg, png, webp, svg)')
  }
  if (file.type === 'image/svg+xml') return readAsDataUrl(file)

  const dataUrl = await readAsDataUrl(file)
  const image = await new Promise<HTMLImageElement>((resolve, reject) => {
    const el = new Image()
    el.onload = () => resolve(el)
    el.onerror = () => reject(new Error('이미지를 열지 못했습니다. 다른 파일로 시도해 주세요.'))
    el.src = dataUrl
  })

  const scale = Math.min(1, options.maxEdge / Math.max(image.width, image.height))
  const width = Math.max(1, Math.round(image.width * scale))
  const height = Math.max(1, Math.round(image.height * scale))

  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) return dataUrl

  // 투명 배경(png 로고)을 유지해야 하므로 로고는 png 로, 사진은 용량이 작은 jpeg 로
  const keepAlpha = file.type === 'image/png' || file.type === 'image/webp'
  if (!keepAlpha) {
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, width, height)
  }
  ctx.drawImage(image, 0, 0, width, height)

  const out = keepAlpha ? canvas.toDataURL('image/png') : canvas.toDataURL('image/jpeg', options.quality)
  // 줄인 것이 더 크면(작은 png 등) 원본을 쓴다
  return out.length < dataUrl.length ? out : dataUrl
}
