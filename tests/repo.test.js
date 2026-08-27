// IndexedDB 통합 테스트 (fake-indexeddb) — 월 청구 생성 / 집계 캐시 / 출결 쓰기 경로
import 'fake-indexeddb/auto'
import { describe, it, expect, beforeAll } from 'vitest'
import { db } from '../src/data/db.js'
import * as repo from '../src/data/repo.js'
import { toMonth, toYmd, addMonths } from '../src/core/date.js'
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

describe('집계 캐시 무효화', () => {
  it('출결을 쓰면 그 달 캐시가 지워진다 (오래된 통계가 남지 않도록)', async () => {
    await repo.recomputeMonth(month)
    expect(await db.monthlyStats.get(month)).toBeTruthy()
    await repo.markAttendance({ classId: 'c1', date: today, studentId: 's2', status: ATT.PRESENT })
    expect(await db.monthlyStats.get(month)).toBeUndefined()
  })

  it('cachedStats 는 캐시에 없는 달을 계산하지 않고 null 로 돌려준다', async () => {
    await repo.recomputeMonth(month)
    const rows = await repo.cachedStats(['1999-01', month])
    expect(rows[0]).toBe(null)
    expect(rows[1].month).toBe(month)
  })

  it('수납을 지우면 그 달 캐시도 지워진다', async () => {
    const pay = (await repo.paymentsOfMonth(month))[0]
    await repo.recomputeMonth(month)
    await repo.remove('payments', pay.id)
    expect(await db.monthlyStats.get(month)).toBeUndefined()
  })
})

describe('할인 정책 반영 청구', () => {
  const nextMonth = addMonths(month, 1)

  it('미리보기는 만들기 전에 누가 얼마인지 보여 준다', async () => {
    const { rows, total, skipped } = await repo.previewMonthlyBills(nextMonth)
    const byName = Object.fromEntries(rows.map((r) => [r.student.name, r.bill.total]))
    expect(byName['김서준']).toBe(240000)
    expect(byName['김서연']).toBe(150000)
    expect(total).toBe(390000)
    expect(skipped).toBe(0)
    expect(await db.payments.where('month').equals(nextMonth).count()).toBe(0) // 미리보기는 저장하지 않는다
  })

  it('형제 할인을 켜면 형제 두 명 모두에게 적용된다', async () => {
    await repo.setSetting('billing', { sibling: { enabled: true, type: 'percent', value: 10 }, roundUnit: 100 })
    const created = await repo.generateMonthlyBills(nextMonth)
    const byStudent = Object.fromEntries(created.map((c) => [c.student_id, c]))
    expect(byStudent.s1.amount).toBe(216000)      // 240,000 - 10%
    expect(byStudent.s1.base_amount).toBe(240000)
    expect(byStudent.s1.discount).toBe(24000)
    expect(byStudent.s2.amount).toBe(135000)
    expect(byStudent.s1.lines.at(-1).label).toContain('형제 할인')
    await repo.setSetting('billing', null)
  })

  it('청구서에 납부 기한을 적어 둔다', async () => {
    const rows = await db.payments.where('month').equals(nextMonth).toArray()
    expect(rows[0].due_date).toBe(`${nextMonth}-10`)
  })

  it('월 중간에 등록해도 그 달 청구에 포함된다', async () => {
    const later = addMonths(month, 2)
    await db.enrollments.put({ id: 'e5', student_id: 's2', class_id: 'c2', started_at: `${later}-25`, ended_at: null })
    await repo.init()
    const { rows } = await repo.previewMonthlyBills(later)
    const mine = rows.find((r) => r.student.id === 's2')
    expect(mine.bill.total).toBe(270000)  // 150,000 + 120,000
  })
})
