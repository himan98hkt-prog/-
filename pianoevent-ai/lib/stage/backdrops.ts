/**
 * 무대 배경 그림.
 *
 * 단색 배경만 있으면 스크린이 발표 자료처럼 보인다. 연주회장에는 연주회의
 * 얼굴이 있어야 한다 — 건반, 무대 커튼, 조명, 악보.
 *
 * 사진을 내려받아 쓰지 않고 **그려 넣는다**(SVG). 그래서
 *   · 인터넷이 없어도 뜨고
 *   · 어느 크기로 키워도 흐려지지 않고
 *   · 테마 108종의 색을 그대로 입는다
 */

export type StageBackdrop =
  | 'plain'
  | 'keys'
  | 'curtain'
  | 'spotlight'
  | 'score'
  | 'bokeh'
  | 'grand'
  | 'starry'
  | 'ribbon'
  | 'arc'

export interface StageBackdropInfo {
  id: StageBackdrop
  name: string
  hint: string
}

export const STAGE_BACKDROPS: StageBackdropInfo[] = [
  { id: 'plain', name: '단색', hint: '테마 색만. 사진이 주인공일 때.' },
  { id: 'keys', name: '건반', hint: '아래쪽에 피아노 건반이 깔립니다.' },
  { id: 'curtain', name: '무대 커튼', hint: '양옆으로 드리운 커튼. 연주회장 느낌.' },
  { id: 'spotlight', name: '무대 조명', hint: '위에서 내려오는 조명 빛.' },
  { id: 'score', name: '악보', hint: '흐릿한 오선과 음표.' },
  { id: 'bokeh', name: '조명 방울', hint: '객석 조명이 번진 듯한 동그란 빛.' },
  { id: 'grand', name: '그랜드피아노', hint: '피아노 실루엣이 한쪽에 앉습니다.' },
  { id: 'starry', name: '별밤', hint: '어두운 하늘과 잔별. 저녁 연주회에.' },
  { id: 'ribbon', name: '리본 띠', hint: '위아래로 흐르는 얇은 띠 장식.' },
  { id: 'arc', name: '아치 무대', hint: '가운데를 감싸는 큰 아치.' },
]

export const DEFAULT_STAGE_BACKDROP: StageBackdrop = 'plain'

export function getStageBackdrop(id: string | null | undefined): StageBackdrop {
  return STAGE_BACKDROPS.some((item) => item.id === id) ? (id as StageBackdrop) : DEFAULT_STAGE_BACKDROP
}

export function stageBackdropInfo(id: StageBackdrop): StageBackdropInfo {
  return STAGE_BACKDROPS.find((item) => item.id === id) ?? STAGE_BACKDROPS[0]
}
