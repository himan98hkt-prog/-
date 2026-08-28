/**
 * 연주회 준비의 **차례**를 한 곳에 적어 둔다.
 *
 * 지금까지 화면은 갈 곳이 열한 군데였다 — 탭 네 개에 단추 일곱 개.
 * 크기도 색도 같았다. 그래서 원장님은 세 가지를 모르셨다.
 *
 *   1. 무엇을 **꼭** 해야 하고 무엇은 안 해도 되는가
 *   2. 지금 내가 **어디**에 있는가
 *   3. 어디까지 했고 **다음은 무엇**인가
 *
 * 세 가지 다 화면 생김새로 답해야 한다. 글로 적어 두면 안 읽으신다.
 * 그래서 여기서 차례·색·다음 걸음을 한 벌로 정하고, 모든 화면이 이것만 본다.
 */

export type StepKey =
  | 'roster'
  | 'program'
  | 'print'
  | 'invite'
  | 'stage'
  | 'video'
  | 'photos'
  | 'live'
  | 'plan'
  | 'prep'
  | 'script'

export interface FlowStep {
  key: StepKey
  /** 꼭 하셔야 하는 세 가지에만 번호가 있다. 나머지는 null */
  no: number | null
  /** 화면 맨 위에 크게 */
  name: string
  /** 좁은 자리에 */
  short: string
  /** 이 화면이 무엇을 하는 곳인지 한 줄 */
  why: string
  /**
   * 화면마다 다른 색.
   * 배경이 다 같으면 어느 화면인지 알 수 없다 — 색이 "여기는 다른 곳" 이라고 말해 준다.
   * HSL 의 색상 각도만 적는다. 진하기는 화면에서 정한다.
   */
  hue: number
  required: boolean
}

/** 꼭 하셔야 하는 세 가지 + 하시면 좋은 것들 */
export const FLOW_STEPS: FlowStep[] = [
  {
    key: 'roster',
    no: 1,
    name: '학생 명단 넣기',
    short: '명단',
    why: '누가 무슨 곡을 치는지 알려 주시면, 나머지는 전부 여기서 만들어집니다.',
    hue: 28,
    required: true,
  },
  {
    key: 'program',
    no: 2,
    name: '순서표 · 사회자 대본 만들기',
    short: '순서표',
    why: '단추 한 번이면 연주 순서와 곡별 멘트가 함께 나옵니다.',
    hue: 210,
    required: true,
  },
  {
    key: 'print',
    no: 3,
    name: '인쇄물 만들기',
    short: '인쇄물',
    why: '포스터와 순서지를 뽑습니다. 뽑기 전에 종이 몇 장인지 먼저 보실 수 있습니다.',
    hue: 152,
    required: true,
  },
  {
    key: 'invite',
    no: null,
    name: '초대장 보내기',
    short: '초대장',
    why: '링크 하나를 단톡방에 보내면 학부모가 참석을 알려 줍니다.',
    hue: 268,
    required: false,
  },
  {
    key: 'script',
    no: null,
    name: '사회자 대본',
    short: '대본',
    why: '오프닝부터 클로징까지, 그대로 읽으시면 되게 적어 두었습니다.',
    hue: 200,
    required: false,
  },
  {
    key: 'stage',
    no: null,
    name: '무대 화면',
    short: '무대 화면',
    why: '연주회장 스크린에 띄우는 화면입니다. 파워포인트로도 받으실 수 있습니다.',
    hue: 250,
    required: false,
  },
  {
    key: 'video',
    no: null,
    name: '감동영상',
    short: '영상',
    why: '아이 사진과 음악으로 한 편을 만듭니다. 마지막에 트시면 됩니다.',
    hue: 330,
    required: false,
  },
  {
    key: 'photos',
    no: null,
    name: '사진 모으기',
    short: '사진',
    why: '리허설·당일에 휴대폰으로 찍어 바로 넣습니다.',
    hue: 190,
    required: false,
  },
  {
    key: 'plan',
    no: null,
    name: '리허설 · 예산 · 좌석',
    short: '리허설',
    why: '리허설 시간표와 대략의 예산, 좌석 배치를 잡습니다.',
    hue: 40,
    required: false,
  },
  {
    key: 'prep',
    no: null,
    name: '진행 준비',
    short: '준비',
    why: '연주회 날까지 무엇을 언제 하면 되는지 날짜별로 짚어 드립니다.',
    hue: 96,
    required: false,
  },
  {
    key: 'live',
    no: null,
    name: '당일 진행',
    short: '당일',
    why: '연주회 당일 무대 옆에서 휴대폰으로 보시는 화면입니다.',
    hue: 0,
    required: false,
  },
]

export const REQUIRED_STEPS = FLOW_STEPS.filter((s) => s.required)
export const EXTRA_STEPS = FLOW_STEPS.filter((s) => !s.required)

export function getStep(key: StepKey): FlowStep {
  return FLOW_STEPS.find((s) => s.key === key) ?? FLOW_STEPS[0]
}

/** 화면 주소 */
export function stepHref(key: StepKey, eventId: string): string {
  switch (key) {
    case 'roster':
      return `/events/${eventId}?tab=roster`
    case 'program':
      return `/events/${eventId}?tab=program`
    case 'plan':
      return `/events/${eventId}?tab=plan`
    case 'prep':
      return `/events/${eventId}?tab=prep`
    case 'print':
      return `/events/${eventId}/design`
    default:
      return `/events/${eventId}/${key}`
  }
}

/**
 * 어디까지 하셨는지 — 화면이 스스로 판단할 수 있게 사실만 받는다.
 *
 * 곁들이(초대장·무대 화면·영상…)도 하셨는지 표시한다. 안 해도 되는 것이지만
 * **해 두신 것을 또 하러 들어가시는 일**은 없어야 한다. 모르는 것은 그냥 비워 둔다.
 */
export interface FlowState {
  hasStudents: boolean
  hasProgram: boolean
  hasPrint: boolean
  /** 초대장 링크를 실제로 여신 적이 있는가 (회신이 있으면 보내신 것이다) */
  hasInvite?: boolean
  /** 무대 화면 설정을 저장해 두셨는가 */
  hasStage?: boolean
  /** 감동영상 설정을 저장해 두셨는가 */
  hasVideo?: boolean
  /** 아이 사진이 한 장이라도 붙어 있는가 */
  hasPhotos?: boolean
  /** 당일 진행을 실제로 돌리신 적이 있는가 */
  hasLive?: boolean
}

export function isDone(key: StepKey, state: FlowState): boolean {
  switch (key) {
    case 'roster':
      return state.hasStudents
    case 'program':
      return state.hasProgram
    case 'print':
      return state.hasPrint
    case 'invite':
      return state.hasInvite === true
    case 'stage':
      return state.hasStage === true
    case 'video':
      return state.hasVideo === true
    case 'photos':
      return state.hasPhotos === true
    case 'live':
      return state.hasLive === true
    // 대본·리허설·진행 준비는 "끝났다" 를 가릴 만한 자국이 남지 않는다.
    // 억지로 판단해 ✓ 를 붙이면 안 한 것을 했다고 하는 셈이라 그냥 비워 둔다.
    default:
      return false
  }
}

export interface Progress {
  done: number
  total: number
  /** 지금 하셔야 할 것. 셋 다 끝났으면 null */
  next: FlowStep | null
  allDone: boolean
}

/**
 * 앞 단계가 안 끝났으면 그것이 "지금 할 것" 이다.
 * 뒤엣것부터 하셔도 되지만, 화면이 권하는 것은 늘 앞엣것이어야 헷갈리지 않는다.
 */
export function progress(state: FlowState): Progress {
  const done = REQUIRED_STEPS.filter((s) => isDone(s.key, state)).length
  const next = REQUIRED_STEPS.find((s) => !isDone(s.key, state)) ?? null
  return { done, total: REQUIRED_STEPS.length, next, allDone: next === null }
}

/** 이 화면 다음에 갈 곳 — 화면 맨 아래 단추 하나 */
export function nextAfter(key: StepKey, state: FlowState): FlowStep | null {
  const step = getStep(key)
  if (step.required) {
    // 아직 안 끝난 다음 필수 단계
    const after = REQUIRED_STEPS.filter((s) => (s.no ?? 0) > (step.no ?? 0))
    const notDone = after.find((s) => !isDone(s.key, state))
    if (notDone) return notDone
    // 뒤가 다 끝났는데 앞이 비었으면 앞으로 되돌려 보낸다
    const missing = REQUIRED_STEPS.find((s) => !isDone(s.key, state))
    if (missing && missing.key !== key) return missing
    return null
  }
  // 곁들이 화면에서는 아직 안 끝난 필수 단계로 돌려보낸다
  return progress(state).next
}

/** "2 / 3 단계" — 좁은 자리에 */
export function progressLabel(state: FlowState): string {
  const { done, total } = progress(state)
  return `${done} / ${total}`
}

/**
 * 화면 색 — 배경, 띠, 글자.
 * 아주 옅게만 쓴다. 화면이 알록달록해지면 그것대로 못 읽으신다.
 */
export function stepTone(key: StepKey): { bg: string; band: string; ink: string; soft: string } {
  const { hue } = getStep(key)
  return {
    bg: `hsl(${hue} 60% 97%)`,
    band: `hsl(${hue} 55% 45%)`,
    ink: `hsl(${hue} 45% 26%)`,
    soft: `hsl(${hue} 55% 92%)`,
  }
}
