import type { Rsvp } from '@/lib/types'

/**
 * 객석 배치.
 *
 * 참석 회신은 이미 쌓이는데, 그걸 좌석으로 바꾸는 건 여전히 손이다.
 * 가족은 붙어 앉아야 하고, 연주자는 앞쪽에서 바로 무대로 나가야 하고,
 * 당일 온 손님을 위한 여유석도 남겨야 한다.
 *
 * 홀마다 구조가 다르므로 "한 줄에 몇 석, 몇 줄" 두 숫자만 받는다.
 * 그 이상 복잡해지면 원장이 직접 고치는 편이 빠르다.
 */

export interface SeatingOptions {
  /** 한 줄 좌석 수 */
  seats_per_row: number
  /** 줄 수 */
  rows: number
  /** 앞에서 몇 줄을 연주자석으로 비워 둘지 */
  performer_rows: number
  /** 당일 방문·스태프용으로 남길 좌석 수 */
  reserve_seats: number
}

export const DEFAULT_SEATING_OPTIONS: SeatingOptions = {
  seats_per_row: 12,
  rows: 10,
  performer_rows: 2,
  reserve_seats: 10,
}

export interface SeatBlock {
  /** 줄 번호 (1부터, 무대에서 가까운 쪽이 1) */
  row: number
  /** 시작 좌석 번호 (1부터) */
  from: number
  to: number
  parent_name: string
  student_name: string
  headcount: number
}

export interface SeatingPlan {
  blocks: SeatBlock[]
  /** 연주자석으로 비워 둔 줄 번호 */
  performer_rows: number[]
  total_seats: number
  /** 관객에게 배정할 수 있는 좌석 */
  assignable_seats: number
  assigned_seats: number
  free_seats: number
  /** 자리를 못 받은 가정 */
  overflow: { parent_name: string; student_name: string; headcount: number }[]
  warnings: string[]
}

/** 가정 단위로 붙여 앉힌다. 줄을 넘겨야 하면 다음 줄 첫 자리부터 통째로 옮긴다. */
export function buildSeating(rsvps: Rsvp[], options: Partial<SeatingOptions> = {}): SeatingPlan {
  const opt = { ...DEFAULT_SEATING_OPTIONS, ...options }
  const attending = rsvps.filter((r) => r.attending)

  const performerRows: number[] = []
  for (let r = 1; r <= Math.min(opt.performer_rows, opt.rows); r += 1) performerRows.push(r)

  const totalSeats = opt.seats_per_row * opt.rows
  const audienceRows = Math.max(0, opt.rows - performerRows.length)
  const assignable = Math.max(0, audienceRows * opt.seats_per_row - Math.max(0, opt.reserve_seats))

  // 인원이 많은 가정부터 앉힌다 — 큰 덩어리가 줄을 넘어가면 빈자리가 많이 남는다
  const queue = [...attending].sort((a, b) => b.headcount - a.headcount || a.student_name.localeCompare(b.student_name, 'ko'))

  const blocks: SeatBlock[] = []
  const overflow: SeatingPlan['overflow'] = []

  let row = performerRows.length + 1
  let next = 1
  let assigned = 0

  for (const rsvp of queue) {
    const need = Math.max(1, rsvp.headcount)

    if (need > opt.seats_per_row) {
      overflow.push({ parent_name: rsvp.parent_name, student_name: rsvp.student_name, headcount: need })
      continue
    }
    if (next + need - 1 > opt.seats_per_row) {
      row += 1
      next = 1
    }
    if (row > opt.rows || assigned + need > assignable) {
      overflow.push({ parent_name: rsvp.parent_name, student_name: rsvp.student_name, headcount: need })
      continue
    }

    blocks.push({
      row,
      from: next,
      to: next + need - 1,
      parent_name: rsvp.parent_name,
      student_name: rsvp.student_name,
      headcount: need,
    })
    next += need
    assigned += need
  }

  blocks.sort((a, b) => a.row - b.row || a.from - b.from)

  const warnings: string[] = []
  if (overflow.length > 0) {
    const short = overflow.reduce((s, o) => s + o.headcount, 0)
    warnings.push(
      `${overflow.length}가정 ${short}석이 배치되지 않았습니다. 줄을 ${Math.ceil(short / opt.seats_per_row)}줄 더 놓거나 ` +
        '가정당 인원을 제한해 다시 안내하세요.',
    )
  }
  if (assignable > 0 && assigned / assignable > 0.92) {
    warnings.push('배정률이 92%를 넘습니다. 당일 방문 가족이 앉을 자리가 거의 없습니다.')
  }
  if (attending.length > 0 && assigned / Math.max(1, attending.length) < 2) {
    warnings.push('가정당 평균 좌석이 2석 미만입니다. 회신 인원이 실제보다 적게 들어왔을 수 있습니다.')
  }
  if (performerRows.length === 0) {
    warnings.push('연주자석이 없습니다. 아이들이 객석 뒤에서 무대까지 걸어 나와야 합니다.')
  }

  return {
    blocks,
    performer_rows: performerRows,
    total_seats: totalSeats,
    assignable_seats: assignable,
    assigned_seats: assigned,
    free_seats: Math.max(0, assignable - assigned),
    overflow,
    warnings,
  }
}

/** "3열 4~6번" 처럼 학부모에게 그대로 보낼 수 있는 표기 */
export function seatLabel(block: SeatBlock): string {
  return block.from === block.to ? `${block.row}열 ${block.from}번` : `${block.row}열 ${block.from}~${block.to}번`
}
