import { describe, it, expect } from 'vitest'
import { buildTodos, classesOn, upcomingClasses, renewalTargets, TODO_LEVEL } from '../src/core/todo.js'

// 2026-03-16 은 월요일
const MON = '2026-03-16'

const cls = (id, name, dow, start = '15:00', end = '16:00', extra = {}) => ({
  id, name, status: '운영', schedule: [{ dow, start, end }], ...extra
})

function base(over = {}) {
  return {
    today: MON,
    classes: [cls('c1', '초등A', 1), cls('c2', '중등B', 2)],
    rosterCounts: [{ class_id: 'c1', count: 3 }, { class_id: 'c2', count: 4 }],
    attendanceToday: [],
    payments: [],
    counselLogs: [],
    notices: [],
    studentById: new Map([
      ['s1', { id: 's1', name: '김하늘' }],
      ['s2', { id: 's2', name: '이바다' }]
    ]),
    lastBackupAt: `${MON}T09:00:00.000Z`,
    ...over
  }
}

const find = (items, id) => items.find((i) => i.id === id)

describe('오늘 할 일', () => {
  it('오늘 요일에 수업이 있는 반만 고른다', () => {
    const list = classesOn([cls('c1', 'A', 1), cls('c2', 'B', 2), cls('c3', 'C', 1, '10:00', '11:00', { status: '종료' })], MON)
    expect(list.map((c) => c.id)).toEqual(['c1'])
  })

  it('출결을 아직 안 찍은 반을 알려 준다', () => {
    const items = buildTodos(base())
    const t = find(items, 'attendance-pending')
    expect(t.count).toBe(1)
    expect(t.desc).toContain('초등A')
  })

  it('정원만큼 체크하면 미체크 항목이 사라진다', () => {
    const attendanceToday = ['s1', 's2', 's3'].map((id) => ({ class_id: 'c1', student_id: id, status: '출석', checked_at: 'x' }))
    expect(find(buildTodos(base({ attendanceToday })), 'attendance-pending')).toBeUndefined()
  })

  it('예약만 해 둔 보강은 체크로 치지 않는다', () => {
    const attendanceToday = ['s1', 's2', 's3'].map((id) => ({ class_id: 'c1', student_id: id, status: '보강', booked: true, checked_at: null }))
    expect(find(buildTodos(base({ attendanceToday })), 'attendance-pending')).toBeDefined()
  })

  it('오늘 결석자는 안내 대상으로 올리고, 이미 보낸 학부모는 뺀다', () => {
    const attendanceToday = [
      { class_id: 'c1', student_id: 's1', status: '결석', checked_at: 'x' },
      { class_id: 'c1', student_id: 's2', status: '결석', checked_at: 'x' }
    ]
    const one = find(buildTodos(base({ attendanceToday })), 'absent-notice')
    expect(one.count).toBe(2)
    expect(one.level).toBe(TODO_LEVEL.DANGER)

    const notices = [{ student_id: 's1', sent_at: `${MON}T10:00:00.000Z` }]
    const two = find(buildTodos(base({ attendanceToday, notices })), 'absent-notice')
    expect(two.count).toBe(1)
    expect(two.payload.studentIds).toEqual(['s2'])
  })

  it('납부 기준일 전에는 미납을 재촉하지 않는다', () => {
    const payments = [{ student_id: 's1', status: '미납', remaining: 150000 }]
    expect(find(buildTodos(base({ payments, today: '2026-03-05' })), 'unpaid')).toBeUndefined()
    const t = find(buildTodos(base({ payments })), 'unpaid')
    expect(t.title).toContain('150,000원')
    expect(t.payload.studentIds).toEqual(['s1'])
  })

  it('완납 건은 미납 목록에 넣지 않는다', () => {
    const payments = [
      { student_id: 's1', status: '완납', remaining: 0 },
      { student_id: 's2', status: '부분', remaining: 50000 }
    ]
    expect(find(buildTodos(base({ payments })), 'unpaid').count).toBe(1)
  })

  it('일주일 넘게 방치된 후속 상담을 올린다', () => {
    const counselLogs = [
      { student_id: 's1', next_action: '체험 안내', created_at: '2026-03-01T09:00:00.000Z', stage: '상담중' },
      { student_id: 's2', next_action: '재상담', created_at: '2026-03-15T09:00:00.000Z', stage: '상담중' },
      { student_id: 's2', next_action: '완료건', created_at: '2026-03-01T09:00:00.000Z', stage: '등록' }
    ]
    const t = find(buildTodos(base({ counselLogs })), 'counsel-followup')
    expect(t.count).toBe(1)
    expect(t.desc).toContain('체험 안내')
  })

  it('백업이 오래되면 경고하고, 한 번도 안 했으면 더 세게 경고한다', () => {
    expect(find(buildTodos(base()), 'backup')).toBeUndefined()
    expect(find(buildTodos(base({ lastBackupAt: '2026-03-06T09:00:00.000Z' })), 'backup').level).toBe(TODO_LEVEL.WARN)
    expect(find(buildTodos(base({ lastBackupAt: null })), 'backup').level).toBe(TODO_LEVEL.DANGER)
  })

  it('할 일이 없으면 빈 배열', () => {
    expect(buildTodos(base({ rosterCounts: [] }))).toEqual([])
  })
})

describe('오늘 남은 수업 / 재등록 대상', () => {
  it('지난 수업은 빼고 시작 시각 순으로 준다', () => {
    const classes = [cls('c1', 'A', 1, '09:00', '10:00'), cls('c2', 'B', 1, '17:00', '18:00'), cls('c3', 'C', 1, '15:00', '16:00')]
    const rows = upcomingClasses(classes, MON, 14 * 60)
    expect(rows.map((r) => r.cls.id)).toEqual(['c3', 'c2'])
  })

  it('2주 안에 수강이 끝나는 원생을 재등록 대상으로 본다', () => {
    const rows = renewalTargets([
      { id: 'e1', ended_at: '2026-03-20' },
      { id: 'e2', ended_at: '2026-05-01' },
      { id: 'e3', ended_at: null },
      { id: 'e4', ended_at: '2026-03-01' }
    ], MON)
    expect(rows.map((e) => e.id)).toEqual(['e1'])
  })
})
