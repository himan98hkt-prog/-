import { describe, expect, it } from 'vitest'
import {
  EXTRA_STEPS,
  FLOW_STEPS,
  REQUIRED_STEPS,
  getStep,
  isDone,
  nextAfter,
  progress,
  progressLabel,
  stepHref,
  stepTone,
  type FlowState,
} from '@/lib/flow/steps'

const state = (partial: Partial<FlowState> = {}): FlowState => ({
  hasStudents: false,
  hasProgram: false,
  hasPrint: false,
  ...partial,
})

describe('꼭 하셔야 하는 것과 하시면 좋은 것', () => {
  it('꼭 하셔야 하는 것은 딱 세 가지다 — 더 늘면 그때부터 안 하신다', () => {
    expect(REQUIRED_STEPS).toHaveLength(3)
    expect(REQUIRED_STEPS.map((s) => s.no)).toEqual([1, 2, 3])
  })

  it('나머지는 전부 곁들이다', () => {
    expect(EXTRA_STEPS.every((s) => s.no === null)).toBe(true)
    expect(EXTRA_STEPS.length).toBeGreaterThan(3)
  })

  it('화면마다 무엇을 하는 곳인지 한 줄이 있다', () => {
    for (const step of FLOW_STEPS) {
      expect(step.why.length).toBeGreaterThan(10)
      expect(step.name.length).toBeGreaterThan(1)
      expect(step.short.length).toBeGreaterThan(0)
    }
  })

  it('화면마다 색이 다르다 — 배경이 같으면 어디인지 알 수 없다', () => {
    expect(new Set(FLOW_STEPS.map((s) => s.hue)).size).toBe(FLOW_STEPS.length)
  })
})

describe('어디까지 했는지', () => {
  it('아무것도 안 하셨으면 0 / 3 이고 다음은 명단이다', () => {
    const p = progress(state())
    expect(p.done).toBe(0)
    expect(p.next?.key).toBe('roster')
  })

  it('명단을 넣으시면 1 / 3', () => {
    expect(progressLabel(state({ hasStudents: true }))).toBe('1 / 3')
  })

  it('앞 단계를 건너뛰셨어도 앞엣것을 먼저 권한다 — 권하는 것은 늘 하나여야 한다', () => {
    const p = progress(state({ hasPrint: true }))
    expect(p.done).toBe(1)
    expect(p.next?.key).toBe('roster')
  })

  it('셋 다 끝나면 더 권하지 않는다', () => {
    const p = progress(state({ hasStudents: true, hasProgram: true, hasPrint: true }))
    expect(p.allDone).toBe(true)
    expect(p.next).toBeNull()
  })

  it('곁들이 화면은 끝났다고 표시하지 않는다 — 안 하셔도 되는 것이다', () => {
    expect(isDone('video', state({ hasStudents: true, hasProgram: true, hasPrint: true }))).toBe(false)
  })
})

describe('다음에 갈 곳', () => {
  it('명단 다음은 순서표다', () => {
    expect(nextAfter('roster', state({ hasStudents: true }))?.key).toBe('program')
  })

  it('이미 끝낸 단계는 건너뛴다', () => {
    expect(nextAfter('roster', state({ hasStudents: true, hasProgram: true }))?.key).toBe('print')
  })

  it('뒤가 다 끝났는데 앞이 비었으면 앞으로 돌려보낸다', () => {
    expect(nextAfter('print', state({ hasProgram: true, hasPrint: true }))?.key).toBe('roster')
  })

  it('셋 다 끝났으면 다음이 없다 — 없는 길을 만들지 않는다', () => {
    expect(nextAfter('print', state({ hasStudents: true, hasProgram: true, hasPrint: true }))).toBeNull()
  })

  it('곁들이 화면에서는 안 끝난 필수 단계로 돌려보낸다', () => {
    expect(nextAfter('video', state({ hasStudents: true }))?.key).toBe('program')
  })
})

describe('화면 주소', () => {
  it('명단·순서표·리허설은 행사 화면의 탭이다', () => {
    expect(stepHref('roster', 'e1')).toBe('/events/e1?tab=roster')
    expect(stepHref('program', 'e1')).toBe('/events/e1?tab=program')
  })

  it('인쇄물은 디자인 화면이다', () => {
    expect(stepHref('print', 'e1')).toBe('/events/e1/design')
  })

  it('나머지는 이름 그대로', () => {
    expect(stepHref('video', 'e1')).toBe('/events/e1/video')
    expect(stepHref('live', 'e1')).toBe('/events/e1/live')
  })
})

describe('화면 색', () => {
  it('화면마다 배경·띠·글자 색이 함께 나온다', () => {
    const tone = stepTone('roster')
    expect(tone.bg).toMatch(/^hsl\(/)
    expect(tone.band).toMatch(/^hsl\(/)
  })

  it('배경은 아주 옅다 — 알록달록해지면 그것대로 못 읽으신다', () => {
    for (const step of FLOW_STEPS) {
      const light = Number(stepTone(step.key).bg.match(/(\d+)%\)$/)?.[1])
      expect(light).toBeGreaterThanOrEqual(95)
    }
  })

  it('모르는 화면을 물으면 첫 단계로 답한다 — 멈추는 것보다 낫다', () => {
    expect(getStep('없는것' as never).key).toBe('roster')
  })
})
