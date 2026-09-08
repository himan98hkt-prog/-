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
    title: '카드 세 장만 보세요',
    body: '행사를 여시면 큰 카드 세 장이 먼저 보입니다. 그중 테두리가 진한 카드 하나가 지금 하실 차례입니다. 그것만 누르세요. 끝난 카드에는 ✓ 가 붙습니다.',
    where: '행사 → 행사 하나를 누르면 바로 나옵니다',
  },
  {
    title: '색으로 어디인지 압니다',
    body: '화면마다 바탕색이 다릅니다 — 명단은 주황, 순서표는 파랑, 인쇄물은 초록. 화면 맨 위에는 몇 번째 단계인지와 어디까지 왔는지가 늘 적혀 있습니다.',
    where: '어느 화면이든 맨 위를 보세요',
  },
  {
    title: '다음 단추만 따라가세요',
    body: '화면 맨 위 오른쪽에 [다음 — …] 단추가 늘 있습니다. 그것만 누르시면 순서대로 끝납니다. 길을 외우지 않으셔도 됩니다.',
    where: '화면 맨 위 오른쪽',
  },
  {
    title: '글씨가 작거나 막히시면',
    body: '머리띠의 [글씨 보통] 을 누르면 글씨가 커집니다. 막히시면 [설명서] 에 처음부터 끝까지 적어 두었고, 그래도 막히시면 설명서 맨 아래 [막히면 여기] 로 쪽지를 보내 주세요.',
    where: '머리띠 → 글씨 크기 · 설명서',
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
