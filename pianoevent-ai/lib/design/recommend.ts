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
import { DESIGN_THEMES, getTheme, seasonalThemeIds, type ThemeFamily } from '@/lib/design/themes'
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
  // 세 장 중 첫 장이 곧 이 답이다. 두 곳에서 따로 정하면 화면과 설명이 어긋난다
  const { kind: _kind, label: _label, ...pick } = recommendDesigns(input)[0]
  return pick
}

/** 화면에 적을 한 줄 — "가을 느낌 · 어텀 메이플 · 포스터 + 순서" */
export function describePick(pick: DesignPick): string {
  return `${getTheme(pick.themeId).name} · ${getTemplate(pick.templateId).name}`
}

/* ────────────────────────────────────────────────────────────────────────────
 * 세 장만 보여 드리기
 *
 * 하나만 정해 드리면 "이게 마음에 안 드는데 어쩌지" 에서 다시 막히신다. 그렇다고
 * 100종을 펼치면 처음으로 돌아간다. 사람이 한눈에 견주는 수는 **셋**이다.
 *
 * 셋을 무엇으로 가를 것인가 — 양식(형태)이 아니라 **느낌**으로 가른다.
 * 양식은 "순서표가 있는가" 로 이미 정해지고, 원장님 눈에 다르게 보이는 것은 색과 장식이다.
 * 그래서 셋 다 같은 양식이고, 계절 · 담백 · 화려 로만 갈린다. 눌러 보시면 그림이 바뀐다.
 * ──────────────────────────────────────────────────────────────────────────── */

export type SuggestionKind = 'chosen' | 'season' | 'plain' | 'fancy'

export interface DesignSuggestion extends DesignPick {
  kind: SuggestionKind
  /** 카드에 적을 한마디 */
  label: string
}

/** 그 성격 묶음에서 아직 안 쓴 테마 하나 */
function pickFamily(family: ThemeFamily, used: Set<string>): string | null {
  return DESIGN_THEMES.find((theme) => theme.family === family && !used.has(theme.id))?.id ?? null
}

/**
 * 견주어 보실 세 장.
 *
 * 첫 장이 곧 `recommendDesign` 의 답이다 — 그대로 뽑으셔도 되는 것.
 * 이미 고르신 것이 있으면 그것이 첫 장으로 오고, 나머지 둘이 딴 길로 붙는다.
 */
export function recommendDesigns(input: {
  eventAt: string
  hasProgram: boolean
  themeId?: string | null
  templateId?: string | null
  now?: Date
}): DesignSuggestion[] {
  const month = eventMonth(input.eventAt, input.now)
  const templateId = input.templateId ?? (input.hasProgram ? 'poster-program' : 'poster-classic')
  const packId = input.hasProgram ? 'audience' : 'booklet'
  const out: DesignSuggestion[] = []
  const used = new Set<string>()

  const add = (kind: SuggestionKind, themeId: string | null, label: string, why: string) => {
    if (!themeId || used.has(themeId)) return
    used.add(themeId)
    out.push({ kind, themeId, templateId, packId, label, why })
  }

  // 자리 셋이 늘 같아야 한다 — 이대로 / 담백 / 화려.
  // 자리가 매번 바뀌면 "아까 그건 어디 갔지" 가 된다.
  if (input.themeId) {
    add('chosen', input.themeId, '지난번에 고르신 것', '지난번에 고르신 그대로입니다.')
  } else {
    add(
      'season',
      seasonalThemeIds(month)[0],
      '이걸로 하시면 됩니다',
      `${month}월 연주회에 어울리는 ${SEASON_WORD[month]} 느낌으로 골라 두었습니다.`,
    )
  }
  add('plain', pickFamily('modern', used), '담백한 쪽', '장식을 덜고 글씨와 사진을 크게 놓았습니다.')
  add('fancy', pickFamily('classic', used), '화려한 쪽', '금선과 장식이 들어간 정통 연주회 느낌입니다.')

  return out.slice(0, 3)
}
