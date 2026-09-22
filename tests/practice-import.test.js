// 반주에서 받은 파일을 실제로 넣어 본다 (fake-indexeddb).
//
// 형식 쪽 규칙은 practice-piano.test.js 가 본다. 여기서 보는 것은 **저장까지 갔을 때도
// 같은가**다 — 원장님이 같은 파일을 두 번 넣으시는 일은 실제로 생기고, 그때 리포트
// 숫자가 두 배가 되면 그 리포트는 못 쓴다.

import 'fake-indexeddb/auto'
import { beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { db } from '../src/data/db.js'
import * as repo from '../src/data/repo.js'
import { buildPractice, summarize } from '../src/core/practice-piano.js'

const file = (rows, device = 'dhome') =>
  JSON.stringify(buildPractice(rows, { academy: '아첼 음악학원', device }))

const row = (over = {}) => ({
  student_id: 'p1', student: '김지우', song_id: 'p05', title: '왈츠',
  date: '2026-09-21', count: 2, seconds: 600, ...over
})

beforeAll(async () => {
  await db.open()
  await db.students.bulkPut([
    { id: 'p1', name: '김지우', status: '재원' },
    { id: 'p2', name: '박서준', status: '재원' },
    { id: 'p3', name: '같은이름', status: '재원' },
    { id: 'p4', name: '같은이름', status: '재원' }
  ])
  await repo.init()
})

beforeEach(async () => { await db.practice.clear() })

describe('반주 파일 불러오기', () => {
  it('넣으면 그 학생 기록으로 읽힌다', async () => {
    const r = await repo.importPractice(file([row()]))
    expect(r.added).toBe(1)
    const rows = await repo.practiceOf('p1', '2026-09')
    expect(summarize(rows)).toMatchObject({ days: 1, count: 2, seconds: 600 })
  })

  // 원장님이 같은 파일을 두 번 넣으시는 일은 실제로 생긴다
  it('같은 파일을 두 번 넣어도 숫자가 그대로다', async () => {
    const f = file([row()])
    await repo.importPractice(f)
    const second = await repo.importPractice(f)
    expect(second.added).toBe(0)
    expect(second.same).toBe(1)
    const rows = await repo.practiceOf('p1', '2026-09')
    expect(rows).toHaveLength(1)
    expect(summarize(rows).seconds).toBe(600)
  })

  it('더 친 뒤 다시 보내면 그만큼만 올라간다', async () => {
    await repo.importPractice(file([row({ seconds: 600, count: 2 })]))
    await repo.importPractice(file([row({ seconds: 900, count: 3 })]))
    const rows = await repo.practiceOf('p1', '2026-09')
    expect(rows).toHaveLength(1)
    expect(summarize(rows)).toMatchObject({ seconds: 900, count: 3 })
  })

  // 학원에서도 치고 집에서도 친 날
  it('기기가 다르면 둘 다 센다', async () => {
    await repo.importPractice(file([row({ seconds: 600, count: 2 })], 'dhome'))
    await repo.importPractice(file([row({ seconds: 300, count: 1 })], 'dacademy'))
    const rows = await repo.practiceOf('p1', '2026-09')
    expect(rows).toHaveLength(2)
    expect(summarize(rows)).toMatchObject({ seconds: 900, count: 3 })
  })

  it('id 없이 이름만 와도 붙는다', async () => {
    const r = await repo.importPractice(file([row({ student_id: '', student: '박서준' })]))
    expect(r.unmatched).toHaveLength(0)
    expect(summarize(await repo.practiceOf('p2', '2026-09')).count).toBe(2)
  })

  // 남의 아이 연습이 우리 아이 리포트에 찍히는 것이 제일 나쁜 고장이다
  it('동명이인이면 아무 데도 안 넣고 여쭤 볼 것으로 돌려준다', async () => {
    const r = await repo.importPractice(file([row({ student_id: '', student: '같은이름' })]))
    expect(r.added).toBe(0)
    expect(r.unmatched).toHaveLength(1)
    expect(await db.practice.count()).toBe(0)
  })

  it('원장님이 골라 주시면 그 아이에게 들어간다', async () => {
    const r = await repo.importPractice(file([row({ student_id: '', student: '같은이름' })]))
    await repo.linkPractice(r.unmatched, 'p4')
    expect(summarize(await repo.practiceOf('p4', '2026-09')).count).toBe(2)
    expect(await repo.practiceOf('p3', '2026-09')).toHaveLength(0)
  })

  it('누구인지 안 고르면 아무 일도 안 일어난다', async () => {
    const r = await repo.importPractice(file([row({ student_id: '', student: '같은이름' })]))
    await expect(repo.linkPractice(r.unmatched, '')).rejects.toThrow(/골라/)
    expect(await db.practice.count()).toBe(0)
  })

  it('반주 파일이 아니면 거절한다', async () => {
    await expect(repo.importPractice('{"format":"뭔가다른것"}'))
      .rejects.toThrow(/연습 기록 파일이 아닙니다/)
  })

  it('달을 넘어가면 그 달 것만 읽는다', async () => {
    await repo.importPractice(file([
      row({ date: '2026-09-21' }), row({ date: '2026-08-21' })
    ]))
    expect(await repo.practiceOf('p1', '2026-09')).toHaveLength(1)
    expect(await repo.practiceOf('p1', '2026-08')).toHaveLength(1)
    expect(await repo.practiceOf('p1')).toHaveLength(2)
  })

  it('개인정보가 섞여 와도 저장되지 않는다', async () => {
    await repo.importPractice(JSON.stringify({
      format: 'academy-note-piano-practice', version: 1, device: 'dhome',
      practice: [{ ...row(), parent_phone: '010-9999-8888', memo: '비밀' }]
    }))
    const saved = await db.practice.toArray()
    expect(JSON.stringify(saved)).not.toContain('010-9999-8888')
    expect(JSON.stringify(saved)).not.toContain('비밀')
  })
})
