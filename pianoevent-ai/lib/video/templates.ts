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
]

export const DEFAULT_VIDEO_TEMPLATE = VIDEO_TEMPLATES[0]

export function getVideoTemplate(id: string | null | undefined): VideoTemplate {
  return VIDEO_TEMPLATES.find((item) => item.id === id) ?? DEFAULT_VIDEO_TEMPLATE
}
