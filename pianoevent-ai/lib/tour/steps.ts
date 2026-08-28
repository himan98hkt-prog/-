/**
 * 처음 켰을 때 안내.
 *
 * 설명서를 만들어 두어도 원장님은 안 여신다. 처음 화면에서 무엇을 눌러야 하는지
 * 몰라 멈추시기 때문이다. 그래서 첫 화면에 작은 쪽지를 띄운다.
 *
 * 규칙 세 가지를 지킨다.
 *  1. 화면을 가리지 않는다 — 덮개(모달)를 쓰지 않는다. 안내를 보면서 눌러 보실 수 있어야 한다.
 *  2. 다섯 걸음을 넘기지 않는다 — 그 이상이면 아무도 끝까지 안 본다.
 *  3. 한 번 닫으면 다시 뜨지 않는다. 다시 보고 싶으실 때는 설명서에서 여신다.
 */

export interface TourStep {
  title: string
  body: string
  /** 이 걸음에서 눌러 보실 곳 */
  where: string
}

export const TOUR_KEY = 'pianoevent.tour.v1'

export const TOUR_STEPS: TourStep[] = [
  {
    title: '3분이면 됩니다',
    body: '연주회 준비에 꼭 하셔야 하는 것은 세 가지뿐입니다. 나머지는 전부 안 하셔도 됩니다.',
    where: '이 쪽지를 보시면서 눌러 보셔도 됩니다 — 화면을 가리지 않습니다.',
  },
  {
    title: '① 학생 명단 넣기',
    body: '행사를 열고 [학생 명단] 탭에서 [명단 양식 내려받기] 를 누르세요. 예시가 채워진 엑셀 파일이 내려옵니다. 이름만 바꿔 저장하시고, 그 파일을 화면에 끌어다 놓으시면 됩니다.',
    where: '행사 → 학생 명단',
  },
  {
    title: '② AI 순서표 만들기',
    body: '단추 한 번이면 연주 순서와 사회자 멘트가 한 번에 나옵니다. 마음에 안 드는 줄은 눌러서 고치시면 됩니다.',
    where: '행사 → 순서표 · 대본',
  },
  {
    title: '③ 인쇄물 뽑기',
    body: '포스터와 순서지가 이미 만들어져 있습니다. 뽑기 전에 [종이로 보기] 를 누르면 종이 몇 장이 나오는지 먼저 보실 수 있습니다.',
    where: '행사 → 인쇄물 디자인',
  },
  {
    title: '막히시면',
    body: '위쪽 [사용설명서] 에 처음부터 끝까지 적어 두었습니다. 그래도 막히시면 설명서 맨 아래 [막히면 여기] 로 쪽지를 만들어 보내 주세요.',
    where: '머리띠 → 사용설명서',
  },
]

/** 다음 걸음. 마지막에서 더 누르면 -1 — 부르는 쪽에서 닫는다 */
export function nextStep(at: number): number {
  return at >= TOUR_STEPS.length - 1 ? -1 : at + 1
}

export function prevStep(at: number): number {
  return Math.max(0, at - 1)
}

export function stepLabel(at: number): string {
  return `${Math.min(at + 1, TOUR_STEPS.length)} / ${TOUR_STEPS.length}`
}
