/**
 * 연주자 화면 모양.
 *
 * 공연장에서 스크린을 보면 두 가지가 늘 문제였다.
 *   1. 사진을 작게 넣으면 둘레가 텅 빈다 — 뒷줄에서는 아무것도 안 보인다.
 *   2. 이름을 화면 아래에 두면 **그랜드피아노 뚜껑에 가려** 객석에서 읽히지 않는다.
 *
 * 그래서 여기 있는 모양은 전부 다음 두 가지를 지킨다.
 *   · 사진은 화면을 **꽉** 채운다 (여백을 남기지 않는다)
 *   · 글자는 **위쪽이나 오른쪽**에만 놓는다 — 아래 4분의 1은 비워 둔다
 */

export type StageLayout =
  | 'photo-frame'
  | 'photo-side'
  | 'photo-panel'
  | 'photo-band'
  | 'photo-corner'
  | 'text-hero'
  | 'text-number'
  | 'text-card'

export interface StageLayoutInfo {
  id: StageLayout
  name: string
  hint: string
  /** 아이 사진이 있어야 뜻이 있는 모양인가 */
  needsPhoto: boolean
}

export const STAGE_LAYOUTS: StageLayoutInfo[] = [
  {
    id: 'photo-frame',
    name: '배경 위 사진 액자',
    hint: '연주회 느낌 배경 위에 아이 사진을 액자로 얹습니다. 사진 모양을 고를 수 있습니다.',
    needsPhoto: true,
  },
  {
    id: 'photo-side',
    name: '사진 반쪽 · 글 오른쪽',
    hint: '왼쪽 절반을 사진이 위아래 끝까지 채우고, 오른쪽에 이름과 곡. 가장 안전합니다.',
    needsPhoto: true,
  },
  {
    id: 'photo-panel',
    name: '사진 전체 · 오른쪽 판',
    hint: '사진이 화면을 꽉 채우고 오른쪽에 반투명 판을 얹어 글을 올립니다. 가장 크게 보입니다.',
    needsPhoto: true,
  },
  {
    id: 'photo-band',
    name: '사진 전체 · 위쪽 띠',
    hint: '사진이 화면을 꽉 채우고 위쪽 띠에 이름과 곡. 피아노에 가리지 않습니다.',
    needsPhoto: true,
  },
  {
    id: 'photo-corner',
    name: '사진 전체 · 큰 번호',
    hint: '사진이 꽉 차고 왼쪽 위에 순서 번호, 오른쪽 위에 이름. 무대 진행이 한눈에 보입니다.',
    needsPhoto: true,
  },
  {
    id: 'text-hero',
    name: '이름만 크게',
    hint: '사진 없이 이름과 곡만. 맨 뒷줄에서도 읽힙니다.',
    needsPhoto: false,
  },
  {
    id: 'text-number',
    name: '큰 번호 · 이름',
    hint: '왼쪽에 순서 번호를 크게, 오른쪽에 이름과 곡. 사진이 없어도 허전하지 않습니다.',
    needsPhoto: false,
  },
  {
    id: 'text-card',
    name: '이름 · 곡 · 해설 카드',
    hint: '테마 장식을 두른 카드 안에 이름·곡·해설. 곡 해설을 함께 띄울 때.',
    needsPhoto: false,
  },
]

export const DEFAULT_STAGE_LAYOUT: StageLayout = 'photo-panel'

/**
 * 아이 사진을 담는 창 모양.
 * 동그라미만 있으면 학원마다 다 똑같아 보인다.
 */
export type PhotoShape = 'circle' | 'rounded' | 'square' | 'arch' | 'oval' | 'hexagon' | 'leaf' | 'diamond'

export interface PhotoShapeInfo {
  id: PhotoShape
  name: string
  /** CSS clip-path / border-radius 로 그릴 값 */
  css: { borderRadius?: string; clipPath?: string }
}

export const PHOTO_SHAPES: PhotoShapeInfo[] = [
  { id: 'circle', name: '원형', css: { borderRadius: '50%' } },
  { id: 'rounded', name: '둥근 사각', css: { borderRadius: '36px' } },
  { id: 'square', name: '사각', css: { borderRadius: '0' } },
  { id: 'arch', name: '아치', css: { borderRadius: '50% 50% 14px 14px / 42% 42% 8px 8px' } },
  { id: 'oval', name: '타원', css: { borderRadius: '50% / 42%' } },
  {
    id: 'hexagon',
    name: '육각',
    css: { clipPath: 'polygon(50% 0%, 95% 25%, 95% 75%, 50% 100%, 5% 75%, 5% 25%)' },
  },
  { id: 'leaf', name: '나뭇잎', css: { borderRadius: '48% 6px 48% 6px' } },
  { id: 'diamond', name: '마름모', css: { clipPath: 'polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)' } },
]

export const DEFAULT_PHOTO_SHAPE: PhotoShape = 'rounded'

export function getPhotoShape(id: string | null | undefined): PhotoShape {
  return PHOTO_SHAPES.some((item) => item.id === id) ? (id as PhotoShape) : DEFAULT_PHOTO_SHAPE
}

export function photoShapeInfo(id: PhotoShape): PhotoShapeInfo {
  return PHOTO_SHAPES.find((item) => item.id === id) ?? PHOTO_SHAPES[0]
}

export function getStageLayout(id: string | null | undefined): StageLayout {
  return STAGE_LAYOUTS.some((item) => item.id === id) ? (id as StageLayout) : DEFAULT_STAGE_LAYOUT
}

export function stageLayoutInfo(id: StageLayout): StageLayoutInfo {
  return STAGE_LAYOUTS.find((item) => item.id === id) ?? STAGE_LAYOUTS[0]
}

/**
 * 사진이 없는 아이에게 쓸 대체 모양.
 * 사진용 모양을 그대로 쓰면 빈 상자가 남는다.
 */
export function fallbackLayout(id: StageLayout): StageLayout {
  switch (id) {
    case 'photo-corner':
      return 'text-number'
    case 'photo-band':
    case 'photo-panel':
    case 'photo-side':
    case 'photo-frame':
      return 'text-hero'
    default:
      return id
  }
}

/**
 * 그랜드피아노 뚜껑이 가리는 화면 아래쪽 비율.
 * 이 아래로는 글자를 놓지 않는다.
 */
export const PIANO_SAFE_BOTTOM = 0.24
