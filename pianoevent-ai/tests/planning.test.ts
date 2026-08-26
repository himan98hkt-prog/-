import { describe, expect, it } from 'vitest'
import { diagnoseProgram, issueSummary } from '@/lib/program/diagnose'
import { buildProgram } from '@/lib/program/order'
import { buildBudget, DEFAULT_BUDGET_ITEMS, formatWon } from '@/lib/ops/budget'
import { buildRehearsal, rehearsalCallMessage, rehearsalSummary } from '@/lib/ops/rehearsal'
import { buildSeating, seatLabel } from '@/lib/ops/seating'
import type { EventRecord, Rsvp } from '@/lib/types'
import { student } from './helpers'

const EVENT_AT = '2026-09-16T06:00:00.000Z' // 2026-09-16 15:00 KST

const event = {
  id: 'e1',
  academy_id: 'a1',
  title: '제12회 정기 연주회',
  type: 'recital',
  event_at: EVENT_AT,
  venue: '구민회관 소공연장',
  status: 'ready',
  theme: null,
  greeting: null,
  mc_opening: null,
  mc_closing: null,
  program_source: 'rule',
  program_generated_at: null,
  design_theme: null,
  design_template: null,
  design_copy: null,
  photo_url: null,
  created_at: EVENT_AT,
} as EventRecord

function roster(n: number) {
  return Array.from({ length: n }, (_, i) =>
    student(`학생${i + 1}`, i % 3 === 0 ? 'beginner' : 'intermediate', 180),
  )
}

function rsvp(parent: string, name: string, headcount: number, attending = true): Rsvp {
  return {
    id: `r-${name}`,
    event_id: 'e1',
    parent_name: parent,
    student_name: name,
    headcount,
    message: null,
    attending,
    created_at: EVENT_AT,
  }
}

describe('리허설 시간표', () => {
  it('순서표 순서 그대로 무대에 올린다', () => {
    const plan = buildProgram(roster(12))
    const r = buildRehearsal(plan)

    expect(r.slots).toHaveLength(12)
    expect(r.slots.map((s) => s.order_no)).toEqual(plan.items.map((i) => i.order_no))
  })

  it('리허설은 개회 전에 끝난다', () => {
    const r = buildRehearsal(buildProgram(roster(10)))
    expect(r.start_offset_sec).toBeLessThan(0)
    expect(r.end_offset_sec).toBeLessThan(0)
    expect(r.end_offset_sec).toBeGreaterThan(r.start_offset_sec)
  })

  it('조 단위로 묶어 소집한다', () => {
    const r = buildRehearsal(buildProgram(roster(12)), { group_size: 5 })
    expect(r.groups.map((g) => g.members.length)).toEqual([5, 5, 2])
    // 소집은 그 조 첫 연주자보다 앞선다
    for (const g of r.groups) {
      expect(g.call_offset_sec).toBeLessThan(g.members[0].stage_offset_sec)
    }
  })

  it('조가 뒤일수록 늦게 부른다 — 대기실이 터지지 않게', () => {
    const r = buildRehearsal(buildProgram(roster(15)), { group_size: 5 })
    const calls = r.groups.map((g) => g.call_offset_sec)
    expect(calls).toEqual([...calls].sort((a, b) => a - b))
    expect(new Set(calls).size).toBe(calls.length)
  })

  it('중간 쉬는 시간을 넣는다', () => {
    const r = buildRehearsal(buildProgram(roster(21)), { break_every: 10 })
    expect(r.breaks).toHaveLength(2)
  })

  it('시간이 모자라면 몇 분 모자란지 알려 준다', () => {
    const r = buildRehearsal(buildProgram(roster(30)), { start_before_min: 60 })
    expect(r.slack_sec).toBeLessThan(0)
    expect(r.warnings.join(' ')).toMatch(/모자랍니다/)
  })

  it('순서표가 없으면 만들라고 알려 준다', () => {
    const r = buildRehearsal(buildProgram([]))
    expect(r.slots).toHaveLength(0)
    expect(r.warnings.join(' ')).toContain('순서표부터')
  })

  it('소집 문자에 도착 시각과 대상이 들어간다', () => {
    const r = buildRehearsal(buildProgram(roster(6)), { group_size: 3 })
    const text = rehearsalCallMessage(event, r.groups[0], '하모니 피아노학원')

    expect(text).toContain('하모니 피아노학원')
    expect(text).toContain('구민회관 소공연장')
    expect(text).toContain(r.groups[0].members[0].student_name)
    expect(text).toMatch(/오전|오후/)
  })

  it('요약에 인원과 조 수가 나온다', () => {
    const r = buildRehearsal(buildProgram(roster(12)), { group_size: 5 })
    expect(rehearsalSummary(r)).toContain('12명')
    expect(rehearsalSummary(r)).toContain('3개 조')
  })
})

describe('예산·참가비', () => {
  const base = { students: 20, families: 18, guests: 54, items: DEFAULT_BUDGET_ITEMS, academy_share: 0 }

  it('기준에 따라 수량이 곱해진다', () => {
    const b = buildBudget(base)
    const flower = b.lines.find((l) => l.item.id === 'flower')!
    const print = b.lines.find((l) => l.item.id === 'print')!
    const venue = b.lines.find((l) => l.item.id === 'venue')!

    expect(flower.qty).toBe(20) // 학생 1인당
    expect(print.qty).toBe(18) // 가정 1곳당
    expect(venue.qty).toBe(1) // 고정
  })

  it('합계는 줄 금액의 합이다', () => {
    const b = buildBudget(base)
    expect(b.total).toBe(b.lines.reduce((s, l) => s + l.amount, 0))
  })

  it('학원 부담을 빼고 걷을 금액을 낸다', () => {
    const b = buildBudget({ ...base, academy_share: 300_000 })
    expect(b.collect).toBe(b.total - 300_000)
  })

  it('권장 참가비는 1,000원 단위로 올린다', () => {
    const b = buildBudget(base)
    expect(b.suggested_fee % 1000).toBe(0)
    expect(b.suggested_fee).toBeGreaterThanOrEqual(b.per_student)
    expect(b.margin).toBeGreaterThanOrEqual(0)
  })

  it('학원 부담이 총액보다 커도 음수가 되지 않는다', () => {
    const b = buildBudget({ ...base, academy_share: 99_000_000 })
    expect(b.collect).toBe(0)
    expect(b.suggested_fee).toBe(0)
  })

  it('참가비가 5만원을 넘으면 경고한다', () => {
    const b = buildBudget({ ...base, students: 4, families: 4, guests: 12 })
    expect(b.suggested_fee).toBeGreaterThan(50_000)
    expect(b.warnings.join(' ')).toContain('5만원')
  })

  it('소규모에서는 고정비가 원인이라고 짚어 준다', () => {
    const b = buildBudget({ ...base, students: 12, families: 12, guests: 36 })
    expect(b.warnings.join(' ')).toContain('고정비가 전체의')
    expect(b.warnings.join(' ')).toContain('12명')
  })

  it('학생이 많으면 고정비 경고가 사라진다', () => {
    const b = buildBudget({ ...base, students: 40, families: 38, guests: 114 })
    expect(b.warnings.join(' ')).not.toContain('고정비가 전체의')
  })

  it('금액은 한국식 천 단위로 적는다', () => {
    expect(formatWon(1234567)).toBe('1,234,567원')
  })
})

describe('객석 배치', () => {
  it('가족은 한 줄에 붙여 앉힌다', () => {
    const plan = buildSeating([rsvp('김씨', '김민준', 3), rsvp('이씨', '이서연', 2)])
    for (const block of plan.blocks) {
      expect(block.to - block.from + 1).toBe(block.headcount)
    }
  })

  it('연주자석은 비워 둔다', () => {
    const plan = buildSeating([rsvp('김씨', '김민준', 3)], { performer_rows: 2 })
    expect(plan.performer_rows).toEqual([1, 2])
    expect(plan.blocks.every((b) => b.row > 2)).toBe(true)
  })

  it('불참 회신은 자리를 차지하지 않는다', () => {
    const plan = buildSeating([rsvp('김씨', '김민준', 3), rsvp('박씨', '박도윤', 4, false)])
    expect(plan.blocks).toHaveLength(1)
    expect(plan.assigned_seats).toBe(3)
  })

  it('같은 줄에 안 들어가면 다음 줄로 통째로 옮긴다', () => {
    const plan = buildSeating(
      [rsvp('가', '가1', 4), rsvp('나', '나1', 4), rsvp('다', '다1', 4)],
      { seats_per_row: 10, rows: 6, performer_rows: 1, reserve_seats: 0 },
    )
    const third = plan.blocks.find((b) => b.student_name === '다1')!
    expect(third.from).toBe(1)
    expect(third.row).toBe(3)
  })

  it('자리가 모자라면 몇 가정이 남았는지 알려 준다', () => {
    const many = Array.from({ length: 30 }, (_, i) => rsvp(`부모${i}`, `학생${i}`, 4))
    const plan = buildSeating(many, { seats_per_row: 8, rows: 4, performer_rows: 1, reserve_seats: 0 })
    expect(plan.overflow.length).toBeGreaterThan(0)
    expect(plan.warnings.join(' ')).toMatch(/배치되지 않았습니다/)
  })

  it('한 줄보다 큰 가정은 배치하지 않고 남긴다', () => {
    const plan = buildSeating([rsvp('대가족', '대가족아이', 20)], { seats_per_row: 12 })
    expect(plan.blocks).toHaveLength(0)
    expect(plan.overflow).toHaveLength(1)
  })

  it('좌석 표기는 학부모에게 그대로 보낼 수 있다', () => {
    expect(seatLabel({ row: 3, from: 4, to: 6, parent_name: '김', student_name: '김', headcount: 3 })).toBe('3열 4~6번')
    expect(seatLabel({ row: 5, from: 2, to: 2, parent_name: '김', student_name: '김', headcount: 1 })).toBe('5열 2번')
  })
})

describe('순서표 정밀 진단', () => {
  it('같은 곡이 겹치면 잡아낸다', () => {
    const plan = buildProgram([
      student('김민준', 'intermediate', 180, { piece_title: '엘리제를 위하여' }),
      student('이서연', 'intermediate', 180, { piece_title: '엘리제를 위하여' }),
      student('박도윤', 'intermediate', 180, { piece_title: '아라베스크' }),
    ])
    const issues = diagnoseProgram(plan)
    expect(issues.some((i) => i.title.includes('같은 곡'))).toBe(true)
  })

  it('연탄곡은 같은 곡이어도 중복으로 잡지 않는다', () => {
    const plan = buildProgram([
      student('김민준', 'intermediate', 180, { piece_title: '아라베스크' }),
      student('임가온', 'ensemble', 120, { piece_title: '젓가락 행진곡' }),
      student('임하람', 'ensemble', 120, { piece_title: '젓가락 행진곡' }),
    ])
    // 두 연탄 주자는 순서가 붙어 있어야 한다
    const pair = plan.items.filter((i) => i.student.piece_title === '젓가락 행진곡')
    expect(Math.abs(pair[0].order_no - pair[1].order_no)).toBe(1)
    expect(diagnoseProgram(plan).some((i) => i.title.includes('같은 곡'))).toBe(false)
  })

  it('연탄이 아닌 같은 곡은 여전히 잡는다', () => {
    const plan = buildProgram([
      student('김민준', 'intermediate', 180, { piece_title: '엘리제를 위하여' }),
      student('이서연', 'intermediate', 180, { piece_title: '엘리제를 위하여' }),
    ])
    expect(diagnoseProgram(plan).some((i) => i.title.includes('같은 곡'))).toBe(true)
  })

  it('형제자매로 보이는 학생이 멀면 붙이라고 한다', () => {
    const list = [
      student('김하윤', 'beginner', 120),
      ...Array.from({ length: 10 }, (_, i) => student(`최학생${i}`, 'intermediate', 180)),
      student('김하준', 'advanced', 300),
    ]
    const issues = diagnoseProgram(buildProgram(list))
    expect(issues.some((i) => i.title.includes('형제자매'))).toBe(true)
  })

  it('휴식 없이 70분을 넘으면 반드시 확인으로 올린다', () => {
    const plan = buildProgram(
      Array.from({ length: 25 }, (_, i) => student(`학생${i}`, 'intermediate', 200)),
      { turnover_sec: 40, intermission_after_sec: 999999, intermission_sec: 0, max_total_sec: 999999 },
    )
    const issue = diagnoseProgram(plan).find((i) => i.id === 'no-break')
    expect(issue?.level).toBe('high')
  })

  it('멘트가 하나도 없으면 만들라고 안내한다', () => {
    const issue = diagnoseProgram(buildProgram(roster(6))).find((i) => i.id === 'missing-script')
    expect(issue?.level).toBe('high')
    expect(issue?.fix).toContain('사회자 대본')
  })

  it('멘트가 모두 있으면 그 항목은 사라진다', () => {
    const filled = roster(6).map((s) => ({ ...s, mc_script: '멘트' }))
    expect(diagnoseProgram(buildProgram(filled)).some((i) => i.id === 'missing-script')).toBe(false)
  })

  it('심각한 것부터 보여 준다', () => {
    const rank = { high: 0, medium: 1, low: 2 }
    const issues = diagnoseProgram(buildProgram(roster(20)))
    const levels = issues.map((i) => rank[i.level])
    expect(levels).toEqual([...levels].sort((a, b) => a - b))
  })

  it('요약은 건수를 등급별로 적는다', () => {
    expect(issueSummary([])).toBe('점검 결과 문제 없음')
    const issues = diagnoseProgram(buildProgram(roster(12)))
    if (issues.length > 0) expect(issueSummary(issues)).toMatch(/건/)
  })

  it('빈 순서표는 진단할 것이 없다', () => {
    expect(diagnoseProgram(buildProgram([]))).toEqual([])
  })
})
