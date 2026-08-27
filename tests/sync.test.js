// Pro 동기화 로직 — 실제 Supabase 없이 가짜 클라이언트로 검증한다.
import 'fake-indexeddb/auto'
import { describe, it, expect, beforeEach } from 'vitest'
import { db } from '../src/data/db.js'
import * as repo from '../src/data/repo.js'
import { push, pull, __setTestHarness, __applyRemote, __toPg, __fromPg } from '../src/data/sync.js'

const ACADEMY = 'acad-1'

/** 최소한의 supabase-js 흉내 — 호출 기록만 남긴다 */
function fakeClient(pullRows = {}) {
  const calls = { upsert: [], delete: [] }
  const client = {
    calls,
    from(table) {
      return {
        upsert(rows) { calls.upsert.push({ table, rows }); return Promise.resolve({ error: null }) },
        delete() {
          return { in(_col, ids) { calls.delete.push({ table, ids }); return Promise.resolve({ error: null }) } }
        },
        select() {
          const q = {
            eq: () => q,
            gt: () => q,
            order: () => q,
            range: (from) => Promise.resolve({ data: from === 0 ? (pullRows[table] || []) : [], error: null })
          }
          return q
        }
      }
    }
  }
  return client
}

beforeEach(async () => {
  await db.open()
  await Promise.all(db.tables.map((t) => t.clear()))
  await repo.init()
  repo.setPlan('pro') // init 이 settings 의 라이선스로 플랜을 되돌리므로 그 뒤에 지정한다
})

describe('오프라인 큐(outbox) → 서버 push', () => {
  it('Pro 에서는 쓰기가 큐에 쌓인다', async () => {
    await repo.put('students', { id: 's1', name: '김서준' })
    await repo.markAttendance({ classId: 'c1', date: '2026-03-02', studentId: 's1', status: '출석' })
    expect(await db.outbox.count()).toBe(2)
  })

  it('push 는 테이블·연산별로 묶어 보내고 성공한 항목만 큐에서 지운다', async () => {
    await repo.put('students', { id: 's1', name: '김서준' })
    await repo.put('students', { id: 's2', name: '김서연' })
    await repo.put('expenses', { id: 'x1', date: '2026-03-02', amount: 1000 })
    await repo.remove('students', 's2')

    const client = fakeClient()
    __setTestHarness({ client, academyId: ACADEMY })
    await push()

    const studentUpserts = client.calls.upsert.find((c) => c.table === 'students')
    expect(studentUpserts.rows).toHaveLength(2)
    expect(studentUpserts.rows.every((r) => r.academy_id === ACADEMY)).toBe(true)
    expect(client.calls.delete).toEqual([{ table: 'students', ids: ['s2'] }])
    expect(await db.outbox.count()).toBe(0)
  })

  it('Dexie 테이블명을 Postgres 테이블명으로 바꿔 보낸다', async () => {
    await repo.put('counselLogs', { id: 'c1', student_id: 's1', type: '전화', content: '상담' })
    const client = fakeClient()
    __setTestHarness({ client, academyId: ACADEMY })
    await push()
    expect(client.calls.upsert[0].table).toBe('counsel_logs')
  })

  it('Lite 에서는 큐를 쓰지 않는다 (서버가 없으므로)', async () => {
    repo.setPlan('lite')
    await repo.put('students', { id: 's9', name: '단일기기' })
    expect(await db.outbox.count()).toBe(0)
    repo.setPlan('pro')
  })
})

describe('서버 → 로컬 pull', () => {
  it('받은 행을 로컬에 저장하고 academy_id 는 로컬에 남기지 않는다', async () => {
    const client = fakeClient({
      students: [{ id: 's5', name: '원격학생', academy_id: ACADEMY, updated_at: '2026-03-02T00:00:00.000Z' }]
    })
    __setTestHarness({ client, academyId: ACADEMY })
    await pull()
    const row = await db.students.get('s5')
    expect(row.name).toBe('원격학생')
    expect(row.academy_id).toBeUndefined()
    expect(repo.getSetting('syncCursor')).toBe('2026-03-02T00:00:00.000Z')
  })
})

describe('충돌 해결 (last-write-wins)', () => {
  beforeEach(() => __setTestHarness({ client: fakeClient(), academyId: ACADEMY }))

  it('서버가 더 최신이면 로컬을 덮어쓴다', async () => {
    await db.attendance.put({ id: 'a1', student_id: 's1', class_id: 'c1', date: '2026-03-02', status: '출석', updated_at: '2026-03-02T10:00:00.000Z' })
    await __applyRemote('attendance', {
      eventType: 'UPDATE',
      new: { id: 'a1', student_id: 's1', class_id: 'c1', date: '2026-03-02', status: '결석', academy_id: ACADEMY, updated_at: '2026-03-02T11:00:00.000Z' }
    })
    expect((await db.attendance.get('a1')).status).toBe('결석')
  })

  it('로컬이 더 최신이면 원격 이벤트를 무시한다', async () => {
    await db.attendance.put({ id: 'a2', student_id: 's1', class_id: 'c1', date: '2026-03-02', status: '지각', updated_at: '2026-03-02T12:00:00.000Z' })
    await __applyRemote('attendance', {
      eventType: 'UPDATE',
      new: { id: 'a2', student_id: 's1', class_id: 'c1', date: '2026-03-02', status: '출석', academy_id: ACADEMY, updated_at: '2026-03-02T09:00:00.000Z' }
    })
    expect((await db.attendance.get('a2')).status).toBe('지각')
  })

  it('원격 삭제는 로컬에서도 지운다', async () => {
    await db.students.put({ id: 's7', name: '삭제대상' })
    await __applyRemote('students', { eventType: 'DELETE', old: { id: 's7' } })
    expect(await db.students.get('s7')).toBeUndefined()
  })
})

describe('행 변환', () => {
  it('보낼 때 academy_id 를 붙이고 로컬 전용 플래그는 뗀다', () => {
    __setTestHarness({ client: fakeClient(), academyId: ACADEMY })
    const out = __toPg('attendance', { id: 'a', status: '보강', booked: true })
    expect(out).toEqual({ id: 'a', status: '보강', academy_id: ACADEMY })
  })

  it('받을 때 academy_id 를 떼어낸다', () => {
    expect(__fromPg({ id: 'a', academy_id: ACADEMY, name: 'x' })).toEqual({ id: 'a', name: 'x' })
  })
})
