/**
 * **밀렸으면 어쩌라는 말까지.**
 *
 * 지금까지 당일 화면은 "예정보다 12분 늦음" 을 붉게 보여 주기만 했다.
 * 그걸 보시고 원장님이 하실 수 있는 일이 무엇인지는 아무 데도 없었다.
 * 늦었다는 사실은 이미 아신다. 필요한 것은 **무엇을 줄이면 되는가** 다.
 *
 * 연주회에서 줄일 수 있는 것은 사실상 하나 — **사회자 멘트**다.
 * 곡을 빼거나 아이를 자를 수는 없다. 그래서 멘트 길이로 말씀드린다.
 *
 * 숫자는 실제 연주회에서 나온 값이다 — 한 순서의 멘트가 보통 20~30초,
 * 박수와 자리 바꾸는 시간이 15~20초. 한 줄로 줄이면 순서마다 10초쯤 붙고,
 * 스무 순서면 3분이 붙는다.
 */

export type PaceLevel = 'ahead' | 'ok' | 'warn' | 'late'

export interface PaceAdvice {
  level: PaceLevel
  /** 지금 상태 한마디 */
  what: string
  /** 사회자에게 그대로 전할 말 */
  say: string
  /** 왜 그렇게 하면 되는지 */
  why: string
}

/** 한 순서에서 멘트를 줄여 벌 수 있는 시간(초) */
export const SAVED_PER_ITEM_SEC = 10

/**
 * 밀린 시간(초, 양수면 늦음)과 남은 순서 수로 무엇을 하실지 정해 드린다.
 *
 * 남은 순서가 적으면 줄여도 못 따라잡는다. 그럴 때 "멘트를 줄이세요" 라고만 하면
 * 원장님만 급해지고 결과는 같다. 그래서 따라잡을 수 있는지까지 계산해 말씀드린다.
 */
export function paceAdvice(driftSec: number, itemsLeft = 0): PaceAdvice {
  const minutes = driftSec / 60
  const canSave = Math.max(0, itemsLeft) * SAVED_PER_ITEM_SEC
  const savedText = canSave >= 60 ? `${Math.round(canSave / 60)}분` : `${canSave}초`

  if (minutes <= -5) {
    return {
      level: 'ahead',
      what: '예정보다 빠릅니다',
      say: '아이 소개를 한 줄 더 하셔도 됩니다.',
      why: '너무 빨리 끝나면 학부모가 "벌써?" 하십니다. 아이마다 한마디씩 더 얹으세요.',
    }
  }
  if (minutes < 4) {
    return {
      level: 'ok',
      what: '예정대로입니다',
      say: '지금 그대로 하시면 됩니다.',
      why: '4분 안쪽은 연주회에서 늘 생기는 차이입니다. 아무것도 안 하셔도 됩니다.',
    }
  }
  if (minutes < 10) {
    return {
      level: 'warn',
      what: '조금 밀렸습니다',
      say: '멘트를 짧게. 박수가 끝나면 바로 다음 아이를 부르세요.',
      why:
        canSave > 0
          ? `남은 ${itemsLeft}순서에서 멘트를 한 줄씩만 줄이시면 ${savedText}쯤 붙습니다.`
          : '박수 기다리는 시간만 줄여도 순서마다 10초가 붙습니다.',
    }
  }
  return {
    level: 'late',
    what: '많이 밀렸습니다',
    say: '멘트는 이름과 곡만. 곡 해설은 건너뛰세요.',
    why:
      canSave >= driftSec
        ? `남은 ${itemsLeft}순서에서 ${savedText}까지 줄이실 수 있어 따라잡습니다.`
        : '남은 순서로는 다 따라잡기 어렵습니다. 마무리 인사를 짧게 하실 준비도 해 두세요.',
  }
}
