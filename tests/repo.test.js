// IndexedDB 통합 테스트 (fake-indexeddb) — 월 청구 생성 / 집계 캐시 / 출결 쓰기 경로
import 'fake-indexeddb/auto'
import { describe, it, expect, beforeAll } from 'vitest'
import { db } from '../src/data/db.js'
import * as repo from '../src/data/repo.js'
import { toMonth, toYmd } from '../src/core/date.js'
import { ATT } from '../src/core/attendance.js'

const month = toMonth(toYmd())
const today = toYmd()

beforeAll(async () => {
  await db.open()
  await db.classes.bulkPut([
    { id: 'c1', name: '수학 1반', subject_id: 'sub1', fee: 150000, status: '운영', schedule: [] },
    { id: 'c2', name: '영어 1반', subject_id: 'sub2', fee: 120000, status: '운영', schedule: [] }
  ])
  await db.students.bulkPut([
    { id: 's1', name: '김서준', status: '재원', parent_phone: '010-1111-2222', joined_at: today },
    { id: 's2', name: '김서연', status: '재원', parent_phone: '01011112222', joined_at: today },
    { id: 's3', name: '휴원생', status: '휴원', parent_phone: '010-3333-4444', joined_at: today }
  ])
  await db.enrollments.bulkPut([
    { id: 'e1', student_id: 's1', class_id: 'c1', started_at: today, ended_at: null },
    { id: 'e2', student_id: 's1', class_id: 'c2', started_at: today, ended_at: null, fee_override: 90000 },
    { id: 'e3', student_id: 's2', class_id: 'c1', started_at: today, ended_at: null },
    { id: 'e4', student_id: 's3', class_id: 'c1', started_at: today, ended_at: null }
  ])
  await repo.init()
})

describe('월 청구 생성', () => {
  it('재원생만, 반 수강료 합계로 청구를 만든다 (fee_override 우선)', async () => {
    const created = await repo.generateMonthlyBills(month)
    const byStudent = Object.fromEntries(created.map((c) => [c.student_id, c.amount]))
    expect(byStudent.s1).toBe(240000)   // 150,000 + override 90,000
    expect(byStudent.s2).toBe(150000)
    expect(byStudent.s3).toBeUndefined() // 휴원생은 제외
  })

  it('두 번 실행해도 중복 청구가 생기지 않는다', async () => {
    const again = await repo.generateMonthlyBills(month)
    expect(again).toHaveLength(0)
    expect(await db.payments.where('month').equals(month).count()).toBe(2)
  })
})

describe('출결 쓰기', () => {
  it('같은 원생·같은 날·같은 반은 덮어쓴다', async () => {
    await repo.markAttendance({ classId: 'c1', date: today, studentId: 's1', status: ATT.PRESENT })
    await repo.markAttendance({ classId: 'c1', date: today, studentId: 's1', status: ATT.ABSENT, reason_tag: '질병' })
    const rows = await repo.attendanceOfClassDate('c1', today)
    const mine = rows.filter((r) => r.student_id === 's1')
    expect(mine).toHaveLength(1)
    expect(mine[0].status).toBe(ATT.ABSENT)
    expect(mine[0].reason_tag).toBe('질병')
  })

  it('반 명단은 휴원생을 포함하되 퇴원생은 뺀다', async () => {
    expect(repo.rosterOf('c1', today).map((s) => s.id).sort()).toEqual(['s1', 's2', 's3'])
    await repo.put('students', { ...repo.cache.studentById.get('s3'), status: '퇴원' })
    expect(repo.rosterOf('c1', today).map((s) => s.id).sort()).toEqual(['s1', 's2'])
  })
})

describe('형제 자동 묶기 (저장 경로)', () => {
  it('원생 저장 시 학부모 번호가 같은 형제를 묶는다', async () => {
    await repo.syncSiblingGroups()
    const s1 = repo.cache.studentById.get('s1')
    const s2 = repo.cache.studentById.get('s2')
    expect(s1.siblings_group).toBe('01011112222')
    expect(s2.siblings_group).toBe(s1.siblings_group)
    expect(repo.siblingsOf(s1).map((s) => s.id)).toEqual(['s2'])
  })
})

describe('월별 집계 캐시', () => {
  it('집계를 계산해 저장하고, 두 번째 호출은 캐시에서 읽는다', async () => {
    const first = await repo.recomputeMonth(month)
    expect(first.billed).toBe(390000)
    expect(first.attendanceTotal).toBeGreaterThan(0)
    const cached = await repo.monthlyStats(month)
    expect(cached.computed_at).toBe(first.computed_at)
  })

  it('수납 후 재계산하면 수납액이 반영된다', async () => {
    const pay = (await repo.paymentsOfMonth(month)).find((p) => p.student_id === 's2')
    await repo.savePayment({ ...pay, paid_at: `${month}-05` })
    const stats = await repo.recomputeMonth(month)
    expect(stats.collected).toBe(150000)
    expect(stats.outstanding).toBe(240000)
    expect(stats.unpaidCount).toBe(1)
  })
})

describe('검색', () => {
  it('이름·학교·전화번호를 부분일치로 찾는다', () => {
    expect(repo.searchStudents('김서', { status: '재원' }).map((s) => s.id).sort()).toEqual(['s1', 's2'])
    expect(repo.searchStudents('1111', {}).map((s) => s.id).sort()).toEqual(['s1', 's2'])
  })

  it('반으로 거를 수 있다', () => {
    expect(repo.searchStudents('', { classId: 'c2' }).map((s) => s.id)).toEqual(['s1'])
  })
})
