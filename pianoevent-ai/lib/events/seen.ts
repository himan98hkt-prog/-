/**
 * **어디까지 보셨는지.**
 *
 * 구경용 행사를 만들어 드려도, 원장님은 대개 인쇄물 한 번 보시고 닫으신다.
 * 무대 화면과 감동영상은 이 프로그램에서 가장 큰 것인데 거기까지 못 가시는 것이다.
 *
 * 그래서 **열어 보신 화면**을 이 컴퓨터에만 적어 두고, 구경용 행사 띠에
 * "아직 안 보신 것" 을 남겨 둔다. 남은 것이 보이면 끝까지 보신다.
 *
 * `isDone` 과는 다르다. 그쪽은 "해 두셨는가"(자국이 남았는가) 를 보고, 이쪽은
 * **"열어 보셨는가"** 만 본다. 구경은 하는 것이 아니라 보는 것이라서다.
 * 서버에 올리지 않는다 — 원장님이 무엇을 보셨는지는 우리가 알 일이 아니다.
 */
import type { StepKey } from '@/lib/flow/steps'

/** 구경용에서 꼭 보시면 좋은 것들 — 이 프로그램이 무엇인지 여기서 갈린다 */
export const SEEN_STEPS: StepKey[] = ['print', 'stage', 'video', 'live']

export function seenStorageKey(eventId: string): string {
  return `pianoevent.seen.${eventId}`
}

export function parseSeen(raw: string | null): StepKey[] {
  if (!raw) return []
  try {
    const data = JSON.parse(raw)
    if (!Array.isArray(data)) return []
    return data.filter((key): key is StepKey => typeof key === 'string' && SEEN_STEPS.includes(key as StepKey))
  } catch {
    return []
  }
}

/** 본 것에 하나 더한다 (같은 것을 두 번 적지 않는다) */
export function addSeen(seen: StepKey[], step: StepKey): StepKey[] {
  if (!SEEN_STEPS.includes(step) || seen.includes(step)) return seen
  return [...seen, step]
}

/** 아직 안 보신 것 */
export function unseenSteps(seen: StepKey[]): StepKey[] {
  return SEEN_STEPS.filter((key) => !seen.includes(key))
}
