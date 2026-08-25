import { describe, expect, it } from 'vitest'
import { applyOrder, buildProgram, estimateDurationSec, relaxAdjacency } from '@/lib/program/order'
import { DEFAULT_PROGRAM_OPTIONS } from '@/lib/types'
import { student } from './helpers'

describe('estimateDurationSec', () => {
  it('입력값이 있으면 그대로 쓴다', () => {
    expect(estimateDurationSec('beginner', 200)).toBe(200)
  })

  it('없거나 0 이면 난이도 기본값으로 추정한다', () => {
    expect(estimateDurationSec('beginner', null)).toBe(90)
    expect(estimateDurationSec('advanced', 0)).toBe(300)
    expect(estimateDurationSec('ensemble', undefined)).toBe(210)
  })
})

describe('buildProgram', () => {
  const roster = [
    student('가온', 'beginner', 80),
    student('나윤', 'beginner', 100),
    student('다현', 'intermediate', 180),
    student('라온', 'intermediate', 200),
    student('마음', 'advanced', 300),
    student('바다', 'ensemble', 150),
  ]

  it('오프닝은 짧은 중급 곡, 피날레는 가장 어려운 곡이 된다', () => {
    const plan = buildProgram(roster)
    expect(plan.items[0].stage).toBe('opening')
    expect(plan.items[0].student.student_name).toBe('다현')
    const last = plan.items[plan.items.length - 1]
    expect(last.stage).toBe('finale')
    expect(last.student.student_name).toBe('마음')
  })

  it('구간 순서는 오프닝 → 초급 → 중급 → 앙상블 → 피날레 를 지킨다', () => {
    const stages = buildProgram(roster).items.map((i) => i.stage)
    expect(stages).toEqual(['opening', 'beginner', 'beginner', 'intermediate', 'ensemble', 'finale'])
  })

  it('모든 학생이 정확히 한 번씩 배치된다', () => {
    const plan = buildProgram(roster)
    expect(plan.items).toHaveLength(roster.length)
    expect(new Set(plan.items.map((i) => i.student.id)).size).toBe(roster.length)
  })

  it('러닝타임은 연주 시간 + 전환 시간의 합이다', () => {
    const plan = buildProgram(roster)
    expect(plan.play_sec).toBe(80 + 100 + 180 + 200 + 300 + 150)
    expect(plan.total_sec).toBe(plan.play_sec + DEFAULT_PROGRAM_OPTIONS.turnover_sec * (roster.length - 1))
  })

  it('시작 오프셋은 앞 곡들의 누적값이다', () => {
    const plan = buildProgram(roster)
    expect(plan.items[0].start_offset_sec).toBe(0)
    for (let i = 1; i < plan.items.length; i++) {
      const prev = plan.items[i - 1]
      expect(plan.items[i].start_offset_sec).toBe(
        prev.start_offset_sec + prev.duration_sec + DEFAULT_PROGRAM_OPTIONS.turnover_sec,
      )
    }
  })

  it('명단이 비면 경고만 남기고 빈 계획을 돌려준다', () => {
    const plan = buildProgram([])
    expect(plan.items).toHaveLength(0)
    expect(plan.warnings[0]).toContain('비어')
  })

  it('학생이 두 명뿐이면 오프닝·피날레를 따로 뽑지 않는다', () => {
    const plan = buildProgram([student('한', 'beginner', 60), student('둘', 'advanced', 300)])
    expect(plan.items).toHaveLength(2)
    expect(plan.items.every((i) => i.stage !== 'opening' && i.stage !== 'finale')).toBe(true)
  })

  it('긴 행사에는 중간 휴식이 들어가고 마지막 곡 앞에는 넣지 않는다', () => {
    const many = Array.from({ length: 20 }, (_, i) => student(`학생${i}`, 'intermediate', 240))
    const plan = buildProgram(many)
    expect(plan.breaks).toHaveLength(1)
    expect(plan.breaks[0].after_order_no).toBeLessThan(plan.items.length - 1)
    expect(plan.total_sec).toBeGreaterThan(plan.play_sec)
  })

  it('휴식 시간이 0 이면 휴식을 넣지 않는다', () => {
    const many = Array.from({ length: 20 }, (_, i) => student(`학생${i}`, 'intermediate', 240))
    const plan = buildProgram(many, { ...DEFAULT_PROGRAM_OPTIONS, intermission_sec: 0 })
    expect(plan.breaks).toHaveLength(0)
  })

  it('권장 러닝타임을 넘으면 경고한다', () => {
    const many = Array.from({ length: 30 }, (_, i) => student(`학생${i}`, 'advanced', 300))
    const plan = buildProgram(many)
    expect(plan.warnings.some((w) => w.includes('러닝타임'))).toBe(true)
  })

  it('같은 학생이 3회 이상 오르면 경고한다', () => {
    const plan = buildProgram([
      student('서연', 'beginner', 90),
      student('서연', 'intermediate', 150),
      student('서연', 'advanced', 300),
      student('민준', 'beginner', 90),
    ])
    expect(plan.warnings.some((w) => w.includes('서연') && w.includes('3회'))).toBe(true)
  })
})

describe('relaxAdjacency', () => {
  it('같은 작곡가가 연달아 오면 같은 구간 안에서 자리를 바꾼다', () => {
    const seq = [
      { student: student('가', 'beginner', 90, { composer: '바흐' }), stage: 'beginner' as const },
      { student: student('나', 'beginner', 90, { composer: '바흐' }), stage: 'beginner' as const },
      { student: student('다', 'beginner', 90, { composer: '모차르트' }), stage: 'beginner' as const },
    ]
    const out = relaxAdjacency(seq)
    expect(out[1].student.composer).toBe('모차르트')
  })

  it('구간 경계를 넘어가며 바꾸지는 않는다', () => {
    const seq = [
      { student: student('가', 'beginner', 90, { composer: '바흐' }), stage: 'beginner' as const },
      { student: student('나', 'beginner', 90, { composer: '바흐' }), stage: 'beginner' as const },
      { student: student('다', 'intermediate', 180, { composer: '쇼팽' }), stage: 'intermediate' as const },
    ]
    const out = relaxAdjacency(seq)
    expect(out.map((e) => e.stage)).toEqual(['beginner', 'beginner', 'intermediate'])
  })
})

describe('applyOrder', () => {
  const roster = [
    student('가', 'beginner', 90, { id: 'a' }),
    student('나', 'intermediate', 180, { id: 'b' }),
    student('다', 'advanced', 300, { id: 'c' }),
  ]

  it('주어진 순서를 그대로 따른다', () => {
    const plan = applyOrder(roster, ['c', 'a', 'b'])
    expect(plan.items.map((i) => i.student.id)).toEqual(['c', 'a', 'b'])
    expect(plan.items.map((i) => i.order_no)).toEqual([1, 2, 3])
  })

  it('AI 가 빠뜨린 학생은 뒤에 붙여 아무도 무대를 잃지 않는다', () => {
    const plan = applyOrder(roster, ['b'])
    expect(plan.items.map((i) => i.student.id)).toEqual(['b', 'a', 'c'])
  })

  it('모르는 id 나 중복 id 는 무시한다', () => {
    const plan = applyOrder(roster, ['b', 'b', 'zzz', 'a', 'c'])
    expect(plan.items.map((i) => i.student.id)).toEqual(['b', 'a', 'c'])
  })

  it('첫 곡과 마지막 곡에 오프닝·피날레 구간을 부여한다', () => {
    const plan = applyOrder(roster, ['a', 'b', 'c'])
    expect(plan.items[0].stage).toBe('opening')
    expect(plan.items[2].stage).toBe('finale')
  })
})
