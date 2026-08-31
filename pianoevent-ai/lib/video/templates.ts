import type { StageBackdrop } from '@/lib/stage/backdrops'
import type { PhotoShape } from '@/lib/stage/layouts'
import type { CaptionPlace } from '@/lib/video/storyboard'

/**
 * 감동영상 템플릿.
 *
 * 한 편의 영상이 어떤 얼굴을 하고 있을지 고르는 것이다.
 *   · 사진을 **화면 꽉** 채울지, **액자에 담아** 배경 위에 얹을지
 *   · 어떤 **무대 배경**을 깔지 (건반 · 커튼 · 조명 …)
 *   · 사진이 어떻게 **움직일지** (천천히 다가가기 · 물러나기 · 옆으로 흐르기)
 *
 * 장면마다 원장님이 고친 글자 자리는 템플릿보다 우선한다.
 */

export type PhotoFit =
  /** 화면을 꽉 채운다 — 사진이 주인공 */
  | 'full'
  /** 배경 위에 액자로 얹는다 */
  | 'frame'
  /** 한쪽 절반을 채운다 */
  | 'half'
  /** 하얀 테를 두른 인화지처럼 */
  | 'polaroid'

export type PhotoMotion = 'in' | 'out' | 'left' | 'right' | 'still'

export interface VideoTemplate {
  id: string
  name: string
  hint: string
  fit: PhotoFit
  backdrop: StageBackdrop
  shape: PhotoShape
  motion: PhotoMotion
  /** 이 템플릿이 기본으로 쓰는 글자 자리 */
  caption: CaptionPlace
  /** 사진을 조금 어둡게 깔아 글자를 살릴지 (0 = 그대로) */
  dim: number
}

export const VIDEO_TEMPLATES: VideoTemplate[] = [
  {
    id: 'full-classic',
    name: '꽉 찬 사진',
    hint: '사진이 화면을 가득 채우고 천천히 다가갑니다. 이름은 아래에.',
    fit: 'full',
    backdrop: 'plain',
    shape: 'square',
    motion: 'in',
    caption: 'bottom',
    dim: 0,
  },
  {
    id: 'full-top',
    name: '꽉 찬 사진 · 위 자막',
    hint: '아이 얼굴이 아래쪽에 있는 사진일 때. 이름이 위로 올라갑니다.',
    fit: 'full',
    backdrop: 'plain',
    shape: 'square',
    motion: 'out',
    caption: 'top',
    dim: 0,
  },
  {
    id: 'full-spotlight',
    name: '극장 조명',
    hint: '사진 위로 무대 조명이 내려옵니다. 시상식 전에 틀기 좋습니다.',
    fit: 'full',
    backdrop: 'spotlight',
    shape: 'square',
    motion: 'in',
    caption: 'bottom',
    dim: 0.18,
  },
  {
    id: 'full-starry',
    name: '별밤',
    hint: '저녁 연주회. 사진 위에 밤하늘과 잔별이 얹힙니다.',
    fit: 'full',
    backdrop: 'starry',
    shape: 'square',
    motion: 'left',
    caption: 'bottom',
    dim: 0.22,
  },
  {
    id: 'full-message',
    name: '감동 문구',
    hint: '사진을 어둡게 깔고 문구를 한가운데 크게. 마지막 인사에.',
    fit: 'full',
    backdrop: 'plain',
    shape: 'square',
    motion: 'in',
    caption: 'center',
    dim: 0.45,
  },
  {
    id: 'frame-keys',
    name: '건반 무대',
    hint: '아래에 피아노 건반이 깔리고 사진이 둥근 액자에 담깁니다.',
    fit: 'frame',
    backdrop: 'keys',
    shape: 'rounded',
    motion: 'in',
    caption: 'top',
    dim: 0,
  },
  {
    id: 'frame-curtain',
    name: '무대 커튼',
    hint: '양옆 커튼 사이로 아이 얼굴이 동그랗게. 정기 연주회에.',
    fit: 'frame',
    backdrop: 'curtain',
    shape: 'circle',
    motion: 'still',
    caption: 'top',
    dim: 0,
  },
  {
    id: 'frame-arch',
    name: '아치 무대',
    hint: '가운데를 감싸는 아치 안에 사진. 격식 있는 자리에.',
    fit: 'frame',
    backdrop: 'arc',
    shape: 'arch',
    motion: 'in',
    caption: 'top',
    dim: 0,
  },
  {
    id: 'polaroid-score',
    name: '악보 위 사진',
    hint: '흐릿한 오선 위에 하얀 테를 두른 인화지처럼. 추억 느낌.',
    fit: 'polaroid',
    backdrop: 'score',
    shape: 'square',
    motion: 'still',
    caption: 'top',
    dim: 0,
  },
  {
    id: 'half-bokeh',
    name: '조명 방울 · 반쪽',
    hint: '왼쪽 절반을 사진이 채우고 오른쪽에 이름. 곡 해설을 길게 쓸 때.',
    fit: 'half',
    backdrop: 'bokeh',
    shape: 'square',
    motion: 'right',
    caption: 'top',
    dim: 0,
  },

  /* ── 더 고르실 수 있게 열 가지를 더 뒀습니다 ─────────────────────
     열 가지로는 "우리 학원 느낌" 이 안 나오는 해가 있습니다.
     새로 그리는 것이 아니라, 이미 있는 배경·모양·움직임을 다르게 짝지은 것입니다 —
     그래서 어느 것을 고르셔도 똑같이 잘 나옵니다. */
  {
    id: 'full-grand',
    name: '그랜드피아노',
    hint: '피아노가 놓인 무대 위로 사진이 천천히 물러납니다. 정기 연주회에.',
    fit: 'full',
    backdrop: 'grand',
    shape: 'square',
    motion: 'out',
    caption: 'bottom',
    dim: 0.2,
  },
  {
    id: 'full-ribbon',
    name: '리본 · 사랑스러운',
    hint: '리본 장식 위에 사진이 옆으로 흐릅니다. 유아·초등 발표회에.',
    fit: 'full',
    backdrop: 'ribbon',
    shape: 'square',
    motion: 'left',
    caption: 'bottom',
    dim: 0.25,
  },
  {
    id: 'frame-oval-grand',
    name: '타원 액자 · 무대',
    hint: '무대 위에 타원 액자로. 옛 사진관 느낌이 납니다.',
    fit: 'frame',
    backdrop: 'grand',
    shape: 'oval',
    motion: 'still',
    caption: 'top',
    dim: 0,
  },
  {
    id: 'frame-leaf-score',
    name: '나뭇잎 액자 · 악보',
    hint: '오선 위에 나뭇잎 모양으로 사진이 담깁니다. 가을 연주회에.',
    fit: 'frame',
    backdrop: 'score',
    shape: 'leaf',
    motion: 'in',
    caption: 'top',
    dim: 0,
  },
  {
    id: 'frame-hex-starry',
    name: '별밤 · 육각 액자',
    hint: '별이 뜬 밤 배경에 육각 액자. 겨울 연주회와 잘 어울립니다.',
    fit: 'frame',
    backdrop: 'starry',
    shape: 'hexagon',
    motion: 'still',
    caption: 'top',
    dim: 0,
  },
  {
    id: 'frame-diamond-spot',
    name: '조명 · 마름모 액자',
    hint: '한 줄기 조명 아래 마름모로. 한 아이씩 또렷하게 보여 줄 때.',
    fit: 'frame',
    backdrop: 'spotlight',
    shape: 'diamond',
    motion: 'in',
    caption: 'top',
    dim: 0,
  },
  {
    id: 'polaroid-keys',
    name: '건반 위 인화지',
    hint: '건반 위에 하얀 테를 두른 사진. 연습실 느낌이 납니다.',
    fit: 'polaroid',
    backdrop: 'keys',
    shape: 'square',
    motion: 'still',
    caption: 'bottom',
    dim: 0,
  },
  {
    id: 'polaroid-ribbon',
    name: '리본 위 인화지',
    hint: '리본 배경에 인화지처럼. 아이들 사진이 많을 때 사랑스럽습니다.',
    fit: 'polaroid',
    backdrop: 'ribbon',
    shape: 'square',
    motion: 'left',
    caption: 'bottom',
    dim: 0,
  },
  {
    id: 'half-curtain',
    name: '커튼 · 반쪽',
    hint: '오른쪽 절반이 사진, 왼쪽에 커튼과 이름. 곡 해설이 길 때.',
    fit: 'half',
    backdrop: 'curtain',
    shape: 'square',
    motion: 'left',
    caption: 'top',
    dim: 0,
  },
  {
    id: 'half-arc',
    name: '아치 · 반쪽',
    hint: '아치 배경 옆에 사진 절반. 이름과 곡을 크게 보여 줄 때.',
    fit: 'half',
    backdrop: 'arc',
    shape: 'rounded',
    motion: 'right',
    caption: 'top',
    dim: 0,
  },
]

export const DEFAULT_VIDEO_TEMPLATE = VIDEO_TEMPLATES[0]

export function getVideoTemplate(id: string | null | undefined): VideoTemplate {
  return VIDEO_TEMPLATES.find((item) => item.id === id) ?? DEFAULT_VIDEO_TEMPLATE
}
