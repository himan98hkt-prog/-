import { formatWallClock } from '@/lib/format'
import type { EventRecord, ProgramPlan } from '@/lib/types'

/**
 * 리허설 시간표.
 *
 * 연주회 당일 아침 원장이 가장 많이 쓰는 시간이 여기다.
 * 전원을 한 번에 부르면 대기실이 터지고, 한 명씩 부르면 30명분 시각을 손으로 계산해야 한다.
 * 그래서 실제 현장에서 쓰는 방식은 "조 단위 소집"이다 — 5명씩 묶어 같은 시각에 부르고,
 * 무대는 순서대로 한 명씩 올린다. 문자도 30통이 아니라 6통이면 된다.
 *
 * 순서표가 이미 있으므로 시각은 전부 계산할 수 있다.
 */

export interface RehearsalOptions {
  /** 리허설 시작 — 행사 시작 몇 분 전인지 */
  start_before_min: number
  /** 학생 1인당 무대 리허설 시간(초) */
  per_student_sec: number
  /** 학생 사이 전환(초) — 인사·착석·의자 높이 */
  turnover_sec: number
  /** 몇 명마다 쉬는지. 0 이면 쉬는 시간 없음 */
  break_every: number
  break_sec: number
  /** 리허설이 끝나고 개회까지 비워 두는 시간(초) — 객석 개방·무대 정리 */
  buffer_sec: number
  /** 한 조에 몇 명을 묶을지 — 소집 문자 단위 */
  group_size: number
  /** 조별 소집은 첫 연주자보다 몇 분 먼저인지 */
  call_before_min: number
}

export const DEFAULT_REHEARSAL_OPTIONS: RehearsalOptions = {
  start_before_min: 150,
  per_student_sec: 180,
  turnover_sec: 30,
  break_every: 10,
  break_sec: 300,
  buffer_sec: 30 * 60,
  group_size: 5,
  call_before_min: 15,
}

export interface RehearsalSlot {
  order_no: number
  student_name: string
  piece_title: string
  composer: string
  /** 개회 시각 기준 오프셋(초). 리허설은 개회 전이므로 음수 */
  stage_offset_sec: number
  duration_sec: number
  /** 몇 조인지 (1부터) */
  group: number
}

export interface RehearsalGroup {
  group: number
  /** 소집 시각 — 개회 기준 오프셋(초) */
  call_offset_sec: number
  members: RehearsalSlot[]
}

export interface RehearsalBreak {
  after_order_no: number
  offset_sec: number
  duration_sec: number
}

export interface RehearsalPlan {
  slots: RehearsalSlot[]
  groups: RehearsalGroup[]
  breaks: RehearsalBreak[]
  /** 리허설 시작·종료 (개회 기준 오프셋 초) */
  start_offset_sec: number
  end_offset_sec: number
  /** 리허설이 끝난 뒤 개회까지 남는 여유(초). 음수면 시간이 모자라다 */
  slack_sec: number
  warnings: string[]
}

/**
 * 순서표 순서 그대로 리허설을 돌린다.
 * 실제 무대 순서와 리허설 순서를 맞춰야 학생이 자기 자리를 기억한다.
 */
export function buildRehearsal(
  plan: ProgramPlan,
  options: Partial<RehearsalOptions> = {},
): RehearsalPlan {
  const opt = { ...DEFAULT_REHEARSAL_OPTIONS, ...options }
  const start = -opt.start_before_min * 60

  const slots: RehearsalSlot[] = []
  const breaks: RehearsalBreak[] = []
  let cursor = start

  plan.items.forEach((item, index) => {
    if (opt.break_every > 0 && index > 0 && index % opt.break_every === 0) {
      breaks.push({
        after_order_no: plan.items[index - 1].order_no,
        offset_sec: cursor,
        duration_sec: opt.break_sec,
      })
      cursor += opt.break_sec
    }

    slots.push({
      order_no: item.order_no,
      student_name: item.student.student_name,
      piece_title: item.student.piece_title,
      composer: item.student.composer,
      stage_offset_sec: cursor,
      duration_sec: opt.per_student_sec,
      group: Math.floor(index / Math.max(1, opt.group_size)) + 1,
    })
    cursor += opt.per_student_sec + opt.turnover_sec
  })

  const end = slots.length > 0 ? cursor - opt.turnover_sec : start

  const groups: RehearsalGroup[] = []
  for (const slot of slots) {
    let group = groups.find((g) => g.group === slot.group)
    if (!group) {
      group = { group: slot.group, call_offset_sec: 0, members: [] }
      groups.push(group)
    }
    group.members.push(slot)
  }
  for (const group of groups) {
    // 조의 첫 연주자보다 조금 먼저 부른다 — 옷 갈아입고 손 푸는 시간
    group.call_offset_sec = group.members[0].stage_offset_sec - opt.call_before_min * 60
  }

  const slack = -end - opt.buffer_sec

  const warnings: string[] = []
  if (slots.length === 0) {
    warnings.push('순서표가 아직 없어 리허설 시간표를 만들 수 없습니다. 순서표부터 만들어 주세요.')
  } else if (slack < 0) {
    const short = Math.ceil(-slack / 60)
    warnings.push(
      `리허설이 개회 ${Math.ceil(opt.buffer_sec / 60)}분 전까지 끝나지 않습니다. ${short}분이 모자랍니다. ` +
        `1인당 시간을 줄이거나 시작을 ${short}분 앞당기세요.`,
    )
  }
  if (groups.length > 0 && groups[0].call_offset_sec < -4 * 60 * 60) {
    warnings.push('첫 조 소집이 개회 4시간 전보다 이릅니다. 아이들이 지칩니다 — 1인당 시간을 줄여 보세요.')
  }
  if (opt.per_student_sec < 90) {
    warnings.push('1인당 리허설이 1분 30초 미만입니다. 무대 인사와 의자 조절만으로도 그 시간이 갑니다.')
  }

  return {
    slots,
    groups,
    breaks,
    start_offset_sec: start,
    end_offset_sec: end,
    slack_sec: slack,
    warnings,
  }
}

/** 조별 소집 문자 — 원장이 단톡방에 그대로 붙여 넣는다 */
export function rehearsalCallMessage(
  event: EventRecord,
  group: RehearsalGroup,
  academyName: string,
): string {
  const call = formatWallClock(event.event_at, group.call_offset_sec)
  const names = group.members.map((m) => m.student_name).join(', ')
  const first = formatWallClock(event.event_at, group.members[0].stage_offset_sec)

  return [
    `[${academyName}] ${event.title} 리허설 안내 (${group.group}조)`,
    '',
    `대상 · ${names}`,
    `도착 · ${call}까지 ${event.venue || '공연장'} 도착`,
    `무대 · ${first}부터 순서대로 진행합니다`,
    '',
    '연주할 옷과 신발을 그대로 신고 와 주세요.',
    '악보는 꼭 챙겨 주시고, 도착하면 접수처에 이름을 말씀해 주세요.',
  ].join('\n')
}

/** 원장이 참고할 소요 시간 요약 */
export function rehearsalSummary(plan: RehearsalPlan): string {
  if (plan.slots.length === 0) return '순서표 없음'
  const totalMin = Math.round((plan.end_offset_sec - plan.start_offset_sec) / 60)
  return `${plan.slots.length}명 · ${plan.groups.length}개 조 · 총 ${totalMin}분`
}
