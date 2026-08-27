import { formatDuration, formatWallClock } from '@/lib/format'
import { pieceCommentary } from '@/lib/program/script'
import { STAGE_LABEL, type EventRecord, type ProgramPlan, type Stage } from '@/lib/types'

/**
 * 무대 스크린 슬라이드.
 *
 * 연주회장 스크린(빔프로젝터·TV)에 띄우는 화면이다.
 * 지금까지 원장님들은 이걸 파워포인트로 매년 다시 만들었다 —
 * 연주자 12명이면 슬라이드 12장을 손으로 치고, 순서가 바뀌면 12장을 다시 옮겼다.
 *
 * 순서표가 이미 있으므로 슬라이드는 전부 계산할 수 있다.
 * 순서를 바꾸면 스크린도 같이 바뀐다. 그것이 이 기능의 전부이자 요점이다.
 */

export type StageSlideKind =
  | 'standby' // 입장 대기 — 개회 전에 계속 띄워 둔다
  | 'agenda' // 오늘의 순서 한눈에
  | 'section' // 부 전환 (초급부 · 앙상블 …)
  | 'performance' // 연주자 한 명
  | 'intermission' // 휴식
  | 'closing' // 폐회 인사

export interface StageSlide {
  id: string
  kind: StageSlideKind
  /** 큰 글씨 — 스크린에서 맨 뒷줄까지 읽혀야 한다 */
  title: string
  /** 제목 위 작은 글씨 */
  eyebrow?: string
  /** 제목 아래 한 줄 */
  subtitle?: string
  /** 본문 — 곡 해설·안내문 */
  body?: string
  /** 목록 슬라이드(오늘의 순서)에서만 쓴다 */
  lines?: { no: string; name: string; piece: string }[]
  /** 화면 구석의 순서 번호 표시 (예: 7 / 12) */
  counter?: string
  /** 예상 시각 — 사회자 화면에만 뜬다 */
  at?: string
  /** 사회자용 — 다음 슬라이드가 무엇인지 */
  next?: string
}

export interface StageDeckOptions {
  /** 곡 해설을 스크린에 띄울지. 끄면 이름과 곡만 크게 보여 준다 */
  show_commentary: boolean
  /** 부(초급·중급·앙상블) 전환 슬라이드를 넣을지 */
  show_sections: boolean
  /** 오늘의 순서 슬라이드를 넣을지 */
  show_agenda: boolean
}

export const DEFAULT_STAGE_OPTIONS: StageDeckOptions = {
  show_commentary: true,
  show_sections: true,
  show_agenda: true,
}

/** 한 화면에 무리 없이 들어가는 순서 줄 수. 넘으면 순서 슬라이드를 나눈다 */
const AGENDA_ROWS = 12

function sectionCopy(stage: Stage): { title: string; subtitle: string } {
  switch (stage) {
    case 'opening':
      return { title: '여는 무대', subtitle: '오늘의 문을 엽니다' }
    case 'beginner':
      return { title: '첫 무대', subtitle: '처음 관객 앞에 서는 연주자들입니다' }
    case 'intermediate':
      return { title: '한 뼘 더', subtitle: '작년보다 한 곡 더 어려워진 연주입니다' }
    case 'ensemble':
      return { title: '함께 치는 무대', subtitle: '둘이 한 대의 피아노를 나눠 씁니다' }
    case 'finale':
      return { title: '마지막 무대', subtitle: '오늘의 끝을 맡은 연주입니다' }
  }
}

/**
 * 순서표에서 스크린 슬라이드를 만든다.
 * 순수 함수 — 화면도 브라우저도 필요 없다. 그래서 시험할 수 있고, 인터넷도 필요 없다.
 */
export function buildStageDeck(
  event: EventRecord,
  plan: ProgramPlan,
  academyName: string,
  options: StageDeckOptions = DEFAULT_STAGE_OPTIONS,
): StageSlide[] {
  const slides: StageSlide[] = []
  const total = plan.items.length

  slides.push({
    id: 'standby',
    kind: 'standby',
    eyebrow: academyName,
    title: event.title,
    subtitle: event.venue ? event.venue : '',
    body: '잠시 후 연주를 시작합니다.\n휴대전화는 무음으로 해 주시고, 곡이 끝난 뒤 박수로 응원해 주세요.',
  })

  if (options.show_agenda && total > 0) {
    const rows = plan.items.map((item) => ({
      no: String(item.order_no),
      name: item.student.student_name,
      piece: item.student.piece_title || '연주곡',
    }))
    const pages = Math.ceil(rows.length / AGENDA_ROWS)
    for (let page = 0; page < pages; page += 1) {
      slides.push({
        id: `agenda-${page + 1}`,
        kind: 'agenda',
        eyebrow: pages > 1 ? `오늘의 순서 ${page + 1} / ${pages}` : '오늘의 순서',
        title: `${total}명 · ${formatDuration(plan.total_sec)}`,
        lines: rows.slice(page * AGENDA_ROWS, (page + 1) * AGENDA_ROWS),
      })
    }
  }

  let lastStage: Stage | null = null

  for (const item of plan.items) {
    if (options.show_sections && item.stage !== lastStage) {
      const copy = sectionCopy(item.stage)
      slides.push({
        id: `section-${item.stage}-${item.order_no}`,
        kind: 'section',
        eyebrow: STAGE_LABEL[item.stage],
        title: copy.title,
        subtitle: copy.subtitle,
      })
      lastStage = item.stage
    }

    const student = item.student
    slides.push({
      id: `performance-${student.id}`,
      kind: 'performance',
      eyebrow: `${item.order_no}번째 무대`,
      title: student.student_name,
      subtitle: [student.piece_title, student.composer].filter(Boolean).join(' · '),
      body: options.show_commentary ? pieceCommentary(student) : undefined,
      counter: `${item.order_no} / ${total}`,
      at: formatWallClock(event.event_at, item.start_offset_sec),
    })

    const pause = plan.breaks.find((entry) => entry.after_order_no === item.order_no)
    if (pause) {
      slides.push({
        id: `intermission-${item.order_no}`,
        kind: 'intermission',
        eyebrow: '잠시 쉬어 갑니다',
        title: pause.label,
        subtitle: `${Math.round(pause.duration_sec / 60)}분 후 2부를 시작합니다`,
        body: '자리를 비우실 때는 조용히 이동해 주세요.',
      })
    }
  }

  slides.push({
    id: 'closing',
    kind: 'closing',
    eyebrow: academyName,
    title: '고맙습니다',
    subtitle: '오늘 무대에 선 모든 연주자에게 박수를 보내 주세요',
    body: '사진 촬영은 폐회 후 무대 앞에서 진행합니다.',
  })

  // 사회자 화면에 "다음: …" 을 띄우기 위해 뒤에서부터 채운다
  for (let i = 0; i < slides.length - 1; i += 1) {
    const following = slides[i + 1]
    slides[i].next = following.kind === 'performance' ? `${following.title} · ${following.subtitle ?? ''}` : following.title
  }
  slides[slides.length - 1].next = ''

  return slides
}

export const STAGE_SLIDE_W = 1280
export const STAGE_SLIDE_H = 720
