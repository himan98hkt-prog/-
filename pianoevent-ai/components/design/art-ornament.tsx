import { ORNAMENT_ART } from '@/lib/design/art'

/**
 * 밖에서 만들어 넣은 금박 장식(월계관·모서리·오선).
 *
 * 미드저니는 배경이 비치는 그림을 주지 않아 **검은 바탕에 금선**으로 그리게 했다.
 * 그대로 얹으면 밝은 종이에서 검은 네모가 된다.
 *
 * 그래서 그림을 색이 아니라 **모양(마스크)** 으로 쓴다 —
 * 밝은 곳(금선)만 남기고 검은 곳은 뚫어 낸 뒤, 그 자리를 테마 강조색으로 칠한다.
 * 오려 내기와 달리 가장자리가 부드럽게 남고, 어느 종이색에서도 같은 결과가 나온다.
 * 덤으로 **테마 색을 그대로 입는다** — 남색 테마에서는 남색 월계관이 된다.
 *
 * `mask-mode: luminance` 를 모르는 브라우저에서는 아무것도 그리지 않는다.
 * 장식은 없어도 인쇄물이 성립하므로, 깨진 네모를 보여 드리는 것보다 낫다.
 */
export function ArtOrnament({
  id,
  width,
  height,
  color = 'var(--d-accent)',
  opacity = 0.85,
  fit = 'contain',
}: {
  id: string
  /** 숫자는 px 다. 종이 크기를 따라가야 하면 '100%' 처럼 CSS 값을 준다 */
  width: number | string
  /** 정사각이 아닌 것(상장 테두리)만 따로 준다 */
  height?: number | string
  color?: string
  opacity?: number
  /** 종이 전체에 까는 그림은 cover 로 채운다 — A4·A5·가로에서 여백이 생기지 않게 */
  fit?: 'contain' | 'cover'
}) {
  const art = ORNAMENT_ART.find((o) => o.id === id)
  if (!art) return null
  const mask = `url(${art.src}) center / ${fit} no-repeat`

  return (
    <div
      aria-hidden
      className="art-ornament"
      style={{
        width,
        height: height ?? width,
        opacity,
        background: color,
        WebkitMask: mask,
        mask,
        maskMode: 'luminance',
        // 사파리·구형 크로미움은 접두사 붙은 이름만 안다. 타입에 없어 이렇게 넣는다
        ['WebkitMaskMode' as string]: 'luminance',
      }}
    />
  )
}
