/**
 * 인쇄물을 **미리 정해 드린다.**
 *
 * 지금까지 인쇄물 화면은 원장님께 두 가지를 물었다 — 양식 50종 중 무엇, 테마 100종 중 무엇.
 * 고르시는 것이 즐거운 분도 계시지만, 대부분은 **고를 것이 있다는 사실 자체**에서 멈추신다.
 *
 * 감동영상 화면에서 이미 하고 있는 방식을 그대로 가져온다 —
 * 하나를 미리 정해 두고 "이대로 뽑으셔도 됩니다" 라고 먼저 말한다.
 * 바꾸고 싶으실 때만 아래를 손보시면 된다.
 *
 * 정하는 규칙은 단순하다. **행사 달에 어울리는 테마**와, 순서표가 있으면 순서지가
 * 붙는 관객용 한 벌. 지어내지 않고 이미 있는 것에서 고른다.
 */
import { getTheme, seasonalThemeIds } from '@/lib/design/themes'
import { getTemplate } from '@/lib/design/templates'

export interface DesignPick {
  themeId: string
  templateId: string
  /** 함께 뽑으시면 좋은 한 벌 */
  packId: string
  /** 왜 이것을 골랐는지 — 원장님이 읽으실 한 줄 */
  why: string
}

/** 행사 달 (1~12). 날짜가 이상하면 이번 달로 본다 */
export function eventMonth(iso: string, now = new Date()): number {
  const at = new Date(iso)
  return (Number.isNaN(at.getTime()) ? now : at).getMonth() + 1
}

const SEASON_WORD: Record<number, string> = {
  3: '봄',
  4: '봄',
  5: '봄',
  6: '여름',
  7: '여름',
  8: '여름',
  9: '가을',
  10: '가을',
  11: '가을',
  12: '겨울',
  1: '겨울',
  2: '겨울',
}

/**
 * 이 행사에 어울리는 인쇄물 한 벌.
 *
 * 원장님이 이미 골라 두신 것이 있으면 **건드리지 않는다.** 고르신 것을 덮으면
 * 다음에 여실 때 딴것이 떠 있어 더 놀라신다.
 */
export function recommendDesign(input: {
  eventAt: string
  hasProgram: boolean
  /** 이미 고르신 것 */
  themeId?: string | null
  templateId?: string | null
  now?: Date
}): DesignPick {
  const month = eventMonth(input.eventAt, input.now)
  const seasonal = seasonalThemeIds(month)
  const themeId = input.themeId ?? seasonal[0]
  // 순서표가 있으면 순서지가 들어간 포스터를, 없으면 순서 없이도 되는 포스터를
  const templateId = input.templateId ?? (input.hasProgram ? 'poster-program' : 'poster-classic')

  return {
    themeId,
    templateId,
    packId: input.hasProgram ? 'audience' : 'booklet',
    why: input.themeId
      ? '지난번에 고르신 그대로입니다.'
      : `${month}월 연주회에 어울리는 ${SEASON_WORD[month]} 느낌으로 골라 두었습니다.`,
  }
}

/** 화면에 적을 한 줄 — "가을 느낌 · 어텀 메이플 · 포스터 + 순서" */
export function describePick(pick: DesignPick): string {
  return `${getTheme(pick.themeId).name} · ${getTemplate(pick.templateId).name}`
}
