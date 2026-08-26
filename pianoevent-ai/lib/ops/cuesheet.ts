import { formatDuration } from '@/lib/format'
import type { EventRecord, ProgramPlan } from '@/lib/types'

/**
 * 당일 진행표(큐시트).
 *
 * 연주회를 여러 번 치러 본 원장이 매번 한글·엑셀로 다시 만드는 문서다.
 * "몇 시에 도착해서, 언제 리허설하고, 언제 객석을 열고, 누가 무엇을 하는가."
 * 행사 시작 시각과 순서표만 있으면 전부 계산할 수 있으므로 자동으로 만든다.
 */

export type CueOwner = '원장' | '사회자' | '스태프' | '강사' | '전체'

export interface CueItem {
  /** 개회(=행사 시작) 시각 기준 분. 음수는 개회 전 */
  offset_min: number
  duration_min: number
  title: string
  detail: string
  owner: CueOwner
  /** 연주 진행 구간인지 — 인쇄물에서 다르게 표시한다 */
  kind: 'prep' | 'stage' | 'close'
}

export interface CueSheetOptions {
  /** 공연장 도착 시각 (개회 몇 분 전) */
  arrive_before_min: number
  /** 리허설 시간(분) */
  rehearsal_min: number
  /** 객석 개방 시각 (개회 몇 분 전) */
  house_open_before_min: number
  /** 시상·단체사진 등 마무리 시간(분) */
  closing_min: number
}

export const DEFAULT_CUE_OPTIONS: CueSheetOptions = {
  arrive_before_min: 120,
  rehearsal_min: 40,
  house_open_before_min: 30,
  closing_min: 20,
}

/** 리허설은 인원수에 따라 늘어난다 — 1인당 2분 + 여유 10분 */
export function suggestedRehearsalMin(performerCount: number): number {
  if (performerCount === 0) return 20
  return Math.min(120, Math.max(20, Math.round(performerCount * 2) + 10))
}

export function buildCueSheet(
  event: EventRecord,
  plan: ProgramPlan,
  options: CueSheetOptions = DEFAULT_CUE_OPTIONS,
): CueItem[] {
  const performers = plan.items.length
  const items: CueItem[] = []

  const arrive = -Math.abs(options.arrive_before_min)
  const rehearsalStart = arrive + 30
  const rehearsalMin = Math.max(10, options.rehearsal_min)
  const briefing = -Math.abs(options.house_open_before_min) - 10
  const houseOpen = -Math.abs(options.house_open_before_min)

  items.push(
    {
      offset_min: arrive,
      duration_min: 30,
      title: '공연장 도착 · 현장 점검',
      detail: '피아노 위치와 의자 높이, 조명, 마이크, 콘센트, 대기실 위치를 확인합니다.',
      owner: '원장',
      kind: 'prep',
    },
    {
      offset_min: arrive + 10,
      duration_min: 20,
      title: '피아노 상태 확인',
      detail: '조율 상태와 페달 작동을 직접 눌러 확인하고, 건반을 닦아 둡니다.',
      owner: '원장',
      kind: 'prep',
    },
    {
      offset_min: rehearsalStart,
      duration_min: rehearsalMin,
      title: `무대 리허설 (${performers}명)`,
      detail: '순서대로 입·퇴장 동선과 인사, 첫 두 마디만 확인합니다. 곡 전체를 치지 않습니다.',
      owner: '전체',
      kind: 'prep',
    },
    {
      offset_min: briefing,
      duration_min: 10,
      title: '스태프 브리핑',
      detail: '대기실 인솔, 무대 옆 대기, 촬영 위치, 안내 데스크, 응급 상황 담당을 정합니다.',
      owner: '스태프',
      kind: 'prep',
    },
    {
      offset_min: houseOpen,
      duration_min: Math.max(5, Math.abs(houseOpen) - 5),
      title: '객석 개방 · 프로그램 배부',
      detail: '입구에서 순서지를 나눠 드리고, 좌석과 화장실 위치를 안내합니다.',
      owner: '스태프',
      kind: 'prep',
    },
    {
      offset_min: -10,
      duration_min: 5,
      title: '연주자 집합 · 순서 확인',
      detail: '대기실에서 이름표를 나눠 주고 순서를 한 번 더 확인합니다. 화장실을 먼저 다녀오게 합니다.',
      owner: '강사',
      kind: 'prep',
    },
    {
      offset_min: -5,
      duration_min: 5,
      title: '착석 안내 방송',
      detail: '휴대전화 무음, 촬영 시 플래시 금지, 곡이 끝난 뒤 박수를 안내합니다.',
      owner: '사회자',
      kind: 'prep',
    },
    {
      offset_min: 0,
      duration_min: 3,
      title: '개회 · 사회자 오프닝',
      detail: '오프닝 멘트를 읽고 첫 연주자를 소개합니다.',
      owner: '사회자',
      kind: 'stage',
    },
  )

  // 연주 진행 — 순서표의 시각을 그대로 옮긴다
  const breaksByOrder = new Map(plan.breaks.map((b) => [b.after_order_no, b]))
  for (const item of plan.items) {
    const brk = breaksByOrder.get(item.order_no - 1)
    if (brk) {
      items.push({
        offset_min: Math.round(brk.start_offset_sec / 60) + 3,
        duration_min: Math.round(brk.duration_sec / 60),
        title: brk.label,
        detail: '객석 환기, 대기 중인 연주자 물 한 모금, 다음 순서 재확인.',
        owner: '스태프',
        kind: 'stage',
      })
    }

    items.push({
      offset_min: Math.round(item.start_offset_sec / 60) + 3,
      duration_min: Math.max(1, Math.round(item.duration_sec / 60)),
      title: `${item.order_no}. ${item.student.student_name}`,
      detail: `${item.student.piece_title}${item.student.composer ? ` / ${item.student.composer}` : ''} · ${formatDuration(
        item.duration_sec,
      )}`,
      owner: '사회자',
      kind: 'stage',
    })
  }

  const afterProgram = Math.round(plan.total_sec / 60) + 3

  items.push(
    {
      offset_min: afterProgram,
      duration_min: 5,
      title: '시상 · 참가 상장 전달',
      detail: '이름을 부르면 무대로 나와 받도록 미리 안내합니다. 상장은 순서대로 정렬해 둡니다.',
      owner: '원장',
      kind: 'close',
    },
    {
      offset_min: afterProgram + 5,
      duration_min: 5,
      title: '단체 사진 촬영',
      detail: '학생 전체 → 반별 → 가족 사진 순으로 찍으면 줄이 엉키지 않습니다.',
      owner: '스태프',
      kind: 'close',
    },
    {
      offset_min: afterProgram + 10,
      duration_min: Math.max(3, options.closing_min - 10),
      title: '원장 인사 · 폐회 멘트',
      detail: '클로징 멘트를 읽고, 사진 공유 방법과 다음 일정을 안내합니다.',
      owner: '사회자',
      kind: 'close',
    },
    {
      offset_min: afterProgram + options.closing_min,
      duration_min: 30,
      title: '정리 · 분실물 확인',
      detail: '대기실과 객석을 돌며 분실물을 확인하고, 대관 상태를 원래대로 되돌립니다.',
      owner: '전체',
      kind: 'close',
    },
  )

  return items.sort((a, b) => a.offset_min - b.offset_min)
}

/** 큐시트 전체가 몇 시간짜리인지 (도착부터 정리까지) */
export function cueSheetSpanMin(items: CueItem[]): number {
  if (items.length === 0) return 0
  const start = items[0].offset_min
  const end = Math.max(...items.map((i) => i.offset_min + i.duration_min))
  return end - start
}
