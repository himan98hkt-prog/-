import { describe, it, expect } from 'vitest'
import { findConflicts, weekGrid, vacancyOf, slotsOf, classesOnDow } from '../src/core/schedule.js'

const cls = (id, over = {}) => ({
  id, name: id, room: 'A', teacher_id: 't1', status: '운영',
  schedule: [{ dow: 1, start: '15:00', end: '16:00' }], ...over
})

describe('시간표 충돌', () => {
  it('같은 강의실·같은 시간이면 경고', () => {
    const out = findConflicts([cls('a'), cls('b', { teacher_id: 't2' })])
    expect(out).toHaveLength(1)
    expect(out[0].type).toBe('room')
  })

  it('같은 강사·같은 시간이면 경고', () => {
    const out = findConflicts([cls('a'), cls('b', { room: 'B' })])
    expect(out.map((c) => c.type)).toEqual(['teacher'])
  })

  it('강의실과 강사가 동시에 겹치면 2건으로 보고한다', () => {
    expect(findConflicts([cls('a'), cls('b')])).toHaveLength(2)
  })

  it('시간이 붙어 있기만 하면(끝=시작) 충돌이 아니다', () => {
    const out = findConflicts([cls('a'), cls('b', { schedule: [{ dow: 1, start: '16:00', end: '17:00' }] })])
    expect(out).toHaveLength(0)
  })

  it('요일이 다르면 충돌이 아니다', () => {
    expect(findConflicts([cls('a'), cls('b', { schedule: [{ dow: 2, start: '15:00', end: '16:00' }] })])).toHaveLength(0)
  })

  it('종료된 반은 검사하지 않는다', () => {
    expect(findConflicts([cls('a'), cls('b', { status: '종료' })])).toHaveLength(0)
  })

  it('끝 시간이 시작보다 빠른 잘못된 슬롯은 무시한다', () => {
    expect(slotsOf({ schedule: [{ dow: 1, start: '16:00', end: '15:00' }] })).toHaveLength(0)
  })
})

describe('주간 그리드', () => {
  it('요일별로 시작 시간 순으로 배치한다', () => {
    const grid = weekGrid([
      cls('late', { schedule: [{ dow: 1, start: '18:00', end: '19:00' }] }),
      cls('early', { schedule: [{ dow: 1, start: '14:00', end: '15:00' }] })
    ])
    expect(grid.get(1).map((x) => x.cls.id)).toEqual(['early', 'late'])
    expect(grid.get(3)).toEqual([])
  })
})

describe('공석', () => {
  it('정원이 있으면 남은 자리를 계산한다', () => {
    expect(vacancyOf({ capacity: 10 }, 7)).toMatchObject({ open: 3, full: false })
    expect(vacancyOf({ capacity: 10 }, 10)).toMatchObject({ open: 0, full: true })
  })

  it('정원 미설정이면 공석 계산을 하지 않는다', () => {
    expect(vacancyOf({}, 5).open).toBe(null)
  })
})

describe('요일 필터', () => {
  it('해당 요일에 수업이 있는 반만 남긴다', () => {
    const list = [cls('mon'), cls('tue', { schedule: [{ dow: 2, start: '15:00', end: '16:00' }] })]
    expect(classesOnDow(list, 1).map((c) => c.id)).toEqual(['mon'])
  })
})
