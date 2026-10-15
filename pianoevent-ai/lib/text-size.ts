/**
 * 글씨 크기.
 *
 * 이 프로그램을 쓰시는 분들은 대개 눈이 편치 않으시다. 화면을 확대하는 법
 * (Ctrl 을 누른 채 + 를 누른다)을 아시는 분은 드물고, 아셔도 그러면 화면이
 * 통째로 커져 표가 옆으로 넘친다.
 *
 * 그래서 **글씨만** 키운다. 세 단계뿐이다 — 고를 것이 많으면 그것대로 짐이 된다.
 */

export type TextSize = 'normal' | 'big' | 'huge'

export const TEXT_SIZE_KEY = 'pianoevent.text'

export interface TextSizeInfo {
  id: TextSize
  label: string
  /** 화면 전체 글씨에 곱하는 값 */
  scale: number
}

export const TEXT_SIZES: TextSizeInfo[] = [
  { id: 'normal', label: '보통', scale: 1 },
  { id: 'big', label: '크게', scale: 1.15 },
  { id: 'huge', label: '아주 크게', scale: 1.3 },
]

export function getTextSize(id: string | null | undefined): TextSizeInfo {
  return TEXT_SIZES.find((s) => s.id === id) ?? TEXT_SIZES[0]
}

/** 다음 단계로 — 단추 하나로 돌려 쓰신다. 끝에서 누르면 처음으로 */
export function nextTextSize(id: TextSize): TextSize {
  const at = TEXT_SIZES.findIndex((s) => s.id === id)
  return TEXT_SIZES[(at + 1) % TEXT_SIZES.length].id
}

/**
 * 뿌리 글씨 크기(px).
 *
 * 브라우저 기본이 16px 이다. rem 으로 짠 화면이라 이 값만 바꾸면 글씨·여백이
 * 함께 커진다 — 글자만 커지고 상자가 그대로면 글이 상자를 뚫는다.
 */
export function rootFontPx(id: TextSize): number {
  return Math.round(16 * getTextSize(id).scale)
}
