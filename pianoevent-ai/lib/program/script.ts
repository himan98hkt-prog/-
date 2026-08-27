import { formatDuration } from '@/lib/format'
import { findPiece } from '@/lib/program/catalog'
import type { EventStudent, ProgramItem, ProgramPlan, Stage } from '@/lib/types'

/**
 * 사회자 멘트 폴백 생성기.
 * Gemini 키가 없거나 호출이 실패해도 원장이 그대로 읽을 수 있는 대본이 나와야 한다.
 * 아래 지식 베이스는 실제 학원 연주회에서 반복적으로 오르는 곡·작곡가만 담았다.
 */

interface ComposerNote {
  era: string
  blurb: string
}

const COMPOSER_NOTES: Record<string, ComposerNote> = {
  바흐: { era: '바로크', blurb: '한 음 한 음이 서로 대화하듯 얽히는 바로크의 정갈한 음악' },
  bach: { era: '바로크', blurb: '한 음 한 음이 서로 대화하듯 얽히는 바로크의 정갈한 음악' },
  모차르트: { era: '고전', blurb: '맑고 투명한 선율이 그대로 드러나 손끝의 정직함이 필요한 곡' },
  mozart: { era: '고전', blurb: '맑고 투명한 선율이 그대로 드러나 손끝의 정직함이 필요한 곡' },
  베토벤: { era: '고전', blurb: '여린 속삭임과 단단한 울림이 한 곡 안에 함께 담긴 음악' },
  beethoven: { era: '고전', blurb: '여린 속삭임과 단단한 울림이 한 곡 안에 함께 담긴 음악' },
  부르크뮐러: { era: '낭만', blurb: '제목 그대로의 장면이 눈앞에 그려지는, 이야기가 있는 연습곡' },
  burgmuller: { era: '낭만', blurb: '제목 그대로의 장면이 눈앞에 그려지는, 이야기가 있는 연습곡' },
  체르니: { era: '고전', blurb: '손가락의 기초를 다지는 곡이지만 무대에서는 또렷한 리듬이 매력인 음악' },
  czerny: { era: '고전', blurb: '손가락의 기초를 다지는 곡이지만 무대에서는 또렷한 리듬이 매력인 음악' },
  쇼팽: { era: '낭만', blurb: '피아노가 사람의 목소리처럼 노래하는, 낭만의 대표적인 음악' },
  chopin: { era: '낭만', blurb: '피아노가 사람의 목소리처럼 노래하는, 낭만의 대표적인 음악' },
  슈만: { era: '낭만', blurb: '어린 시절의 장면을 짧은 곡에 담아낸 따뜻한 음악' },
  schumann: { era: '낭만', blurb: '어린 시절의 장면을 짧은 곡에 담아낸 따뜻한 음악' },
  드뷔시: { era: '근대', blurb: '색이 번지듯 화음이 흐르는, 그림 같은 음악' },
  debussy: { era: '근대', blurb: '색이 번지듯 화음이 흐르는, 그림 같은 음악' },
  차이콥스키: { era: '낭만', blurb: '노래하듯 흐르는 선율에 러시아의 서정이 담긴 음악' },
  tchaikovsky: { era: '낭만', blurb: '노래하듯 흐르는 선율에 러시아의 서정이 담긴 음악' },
  파헬벨: { era: '바로크', blurb: '같은 화음 위에 선율이 층층이 쌓이는, 누구에게나 익숙한 음악' },
  pachelbel: { era: '바로크', blurb: '같은 화음 위에 선율이 층층이 쌓이는, 누구에게나 익숙한 음악' },
  바다르체프스카: { era: '낭만', blurb: '단정한 아르페지오가 물결처럼 이어지는 소품' },
  엘가: { era: '낭만', blurb: '사랑하는 사람에게 건네는 인사처럼 다정한 음악' },
  리스트: { era: '낭만', blurb: '피아노 한 대로 오케스트라를 그려내는 화려한 음악' },
  liszt: { era: '낭만', blurb: '피아노 한 대로 오케스트라를 그려내는 화려한 음악' },
}

const PIECE_NOTES: { keyword: string[]; blurb: string }[] = [
  { keyword: ['엘리제', 'elise'], blurb: '누구나 첫 소절을 흥얼거릴 수 있는 곡이지만, 여린 소리를 끝까지 고르게 유지하기가 가장 어렵습니다' },
  { keyword: ['소녀의 기도', 'maiden'], blurb: '한 소녀의 기도를 그대로 옮겨 놓은 듯한 곡으로, 물결치는 아르페지오가 인상적입니다' },
  { keyword: ['아라베스크'], blurb: '오른손과 왼손이 서로를 쫓아가듯 달리는, 짧지만 또렷한 곡입니다' },
  { keyword: ['인벤션', 'invention'], blurb: '두 개의 선율이 각자 걸어가면서도 하나의 음악이 되는, 바흐의 대화 같은 곡입니다' },
  { keyword: ['미뉴에트', 'minuet'], blurb: '옛 궁정의 춤곡으로, 우아한 3박자의 걸음이 곡 전체를 이끕니다' },
  { keyword: ['터키', 'turkish'], blurb: '행진하는 군악대의 소리를 피아노로 옮긴, 경쾌한 리듬의 곡입니다' },
  { keyword: ['월광', 'moonlight'], blurb: '고요한 물 위에 달빛이 내려앉은 듯한 첫 악장이 오래도록 남는 곡입니다' },
  { keyword: ['캐논', 'canon'], blurb: '같은 선율이 시간을 두고 겹겹이 쌓이며 점점 풍성해지는 곡입니다' },
  { keyword: ['젓가락', 'chopsticks'], blurb: '둘이 마주 앉아야 완성되는, 듣는 사람까지 즐거워지는 곡입니다' },
  { keyword: ['소나티네', 'sonatine', 'sonatina'], blurb: '작은 소나타라는 이름처럼, 또렷한 구성 속에 밝은 성격이 담긴 곡입니다' },
  { keyword: ['녹턴', 'nocturne'], blurb: '밤의 노래라는 뜻 그대로, 왼손의 잔잔한 물결 위로 오른손이 노래하는 곡입니다' },
  { keyword: ['왈츠', 'waltz'], blurb: '세 박자에 몸이 먼저 반응하는, 춤추는 듯한 곡입니다' },
]

const norm = (v: string) => v.trim().toLowerCase().replace(/\s+/g, '')

function composerNote(composer: string): ComposerNote | null {
  const key = norm(composer)
  if (!key) return null
  for (const [name, note] of Object.entries(COMPOSER_NOTES)) {
    if (key.includes(norm(name))) return note
  }
  return null
}

function pieceNote(title: string): string | null {
  const key = norm(title)
  for (const entry of PIECE_NOTES) {
    if (entry.keyword.some((k) => key.includes(norm(k)))) return entry.blurb
  }
  return null
}

/** 곡 해설 한 줄 — 곡 사전 → 옛 키워드 → 작곡가 → 난이도 순으로 떨어진다 */
export function pieceCommentary(student: EventStudent): string {
  // 곡 사전에 있는 곡이면 그 곡을 위해 쓰인 해설을 그대로 쓴다
  const catalog = findPiece(student.piece_title)
  if (catalog) return catalog.blurb

  const byPiece = pieceNote(student.piece_title)
  if (byPiece) return byPiece

  const byComposer = composerNote(student.composer)
  if (byComposer) return `${byComposer.era} 시대의 ${byComposer.blurb}입니다`

  switch (student.level) {
    case 'beginner':
      return '작은 손으로 짚어 가는 한 음 한 음에 지난 계절의 연습이 담겨 있는 곡입니다'
    case 'intermediate':
      return '양손이 각자의 역할을 지키며 하나의 노래를 만들어 가는 곡입니다'
    case 'advanced':
      return '긴 호흡과 고른 손끝이 함께 필요한, 오늘 무대에서도 손꼽히는 난이도의 곡입니다'
    case 'ensemble':
      return '서로의 소리를 들어야만 완성되는, 함께 연주하는 즐거움이 담긴 곡입니다'
  }
}

const INTRO_TEMPLATES = [
  (name: string) => `${name} 학생을 무대로 모시겠습니다`,
  (name: string) => `이어서 ${name} 학생의 연주가 있겠습니다`,
  (name: string) => `다음 무대는 ${name} 학생입니다`,
  (name: string) => `${name} 학생이 준비한 무대입니다`,
]

/** 학생 한 명분 사회자 멘트 (2~3문장). index 로 문형을 돌려 같은 말이 반복되지 않게 한다. */
export function buildStudentScript(item: ProgramItem, index: number, total: number): string {
  const s = item.student
  const composer = s.composer.trim()
  const piece = composer ? `${composer}의 「${s.piece_title}」` : `「${s.piece_title}」`
  const lines: string[] = []

  if (item.stage === 'opening') {
    lines.push(`오늘 연주회의 문을 여는 첫 무대입니다.`)
  } else if (item.stage === 'finale') {
    lines.push(`오늘의 마지막 무대입니다.`)
  } else if (item.stage === 'ensemble' && index > 0) {
    lines.push(`이번에는 함께 호흡을 맞춘 무대를 준비했습니다.`)
  }

  lines.push(`${INTRO_TEMPLATES[index % INTRO_TEMPLATES.length](s.student_name)}. 연주곡은 ${piece}입니다.`)
  lines.push(`${pieceCommentary(s)}.`)

  if (s.note && s.note.trim()) {
    lines.push(`${s.student_name} 학생은 ${s.note.trim()}.`)
  }

  if (item.stage === 'finale' || index === total - 1) {
    lines.push(`오늘 무대를 위해 가장 오래 준비한 곡입니다. 큰 박수로 맞아 주시기 바랍니다.`)
  } else {
    lines.push(`따뜻한 박수로 맞아 주시기 바랍니다.`)
  }

  return lines.join(' ')
}

export interface McScript {
  opening: string
  closing: string
  /** event_students.id → 멘트 */
  byStudentId: Record<string, string>
}

export function buildMcScript(
  plan: ProgramPlan,
  meta: { eventTitle: string; academyName: string; totalSec?: number },
): McScript {
  const total = plan.items.length
  const runtime = formatDuration(meta.totalSec ?? plan.total_sec)

  const opening = [
    `안녕하십니까. ${meta.academyName} ${meta.eventTitle}에 오신 학부모님과 내빈 여러분, 진심으로 환영합니다.`,
    `오늘 무대에는 모두 ${total}명의 연주자가 오르며, 약 ${runtime} 동안 함께합니다.`,
    `연주 중에는 휴대전화를 무음으로 해 주시고, 한 곡이 끝난 뒤 박수로 아이들의 용기에 답해 주시기 바랍니다.`,
    `그럼 지금부터 ${meta.eventTitle}를 시작하겠습니다.`,
  ].join(' ')

  const closing = [
    `이것으로 ${meta.academyName} ${meta.eventTitle}의 모든 순서를 마칩니다.`,
    `오늘 무대에 선 ${total}명의 연주자들에게 다시 한번 큰 박수 부탁드립니다.`,
    `아이들이 한 곡을 끝까지 마쳤다는 것, 그 자체가 오늘의 가장 큰 성취입니다.`,
    `끝까지 자리를 지켜 주신 학부모님께 깊이 감사드리며, 조심히 돌아가시기 바랍니다.`,
  ].join(' ')

  const byStudentId: Record<string, string> = {}
  plan.items.forEach((item, index) => {
    byStudentId[item.student.id] = buildStudentScript(item, index, total)
  })

  return { opening, closing, byStudentId }
}

export function stageHeadline(stage: Stage): string {
  switch (stage) {
    case 'opening':
      return '막을 여는 무대'
    case 'beginner':
      return '첫 무대에 서는 연주자들'
    case 'intermediate':
      return '한 뼘 더 자란 연주'
    case 'ensemble':
      return '함께 만드는 소리'
    case 'finale':
      return '오늘의 마지막 무대'
  }
}
