/**
 * 제목 글씨 크기 맞추기.
 *
 * 포스터 제목은 클수록 좋지만, 「제12회 하모니피아노학원 정기 연주회 및 시상식」처럼
 * 긴 제목이 들어오면 큰 글씨가 석 줄로 무너지고 아래 내용을 밀어낸다.
 * 그 순간 포스터가 아니라 사고가 된다.
 *
 * 글자 수로 줄여 준다. 한글은 한 글자가 대략 한 칸이라 이 셈이면 충분하다.
 * 원장님이 손볼 것은 없다 — 제목을 길게 쓰셔도 판이 무너지지 않는다.
 */
export function fitTitle(title: string, max: number): number {
  const n = [...title.trim()].length
  if (n <= 8) return max
  if (n <= 12) return Math.round(max * 0.8)
  if (n <= 18) return Math.round(max * 0.62)
  if (n <= 26) return Math.round(max * 0.5)
  return Math.round(max * 0.42)
}
