// 표를 새로 만들면 **일곱 군데**를 같이 고쳐야 한다.
//
//   db.js(스키마) · backup.js(백업) · repo.js(동기화 대상) · sync.js(표 목록·이름 대응)
//   schema.sql(표·트리거 배열·RLS 배열)
//
// 하나라도 빠지면 조용히 고장 난다. 백업에서 빠지면 기기를 바꿀 때 그 표만 사라지고,
// RLS 배열에서 빠지면 **다른 학원 자료가 보인다.** 둘 다 우리 화면에서는 안 보이고
// 현장에서만 보이는 고장이다. 그래서 사람이 기억하지 않게 여기서 못 박는다.

import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { BACKUP_TABLES } from '../src/core/backup.js'

const ROOT = resolve(import.meta.dirname, '..')
const read = (p) => readFileSync(resolve(ROOT, p), 'utf8')

/** 동기화하지 않는 표와 그 이유. 새로 예외를 두려면 여기에 이유를 적어야 한다. */
const NOT_SYNCED = {
  outbox: '동기화 큐 자체다. 큐를 동기화할 수는 없다',
  settings: '기기의 설정이다. 인증키처럼 그 기기 것만 있어야 하는 값이 들어 있다',
  monthlyStats: '다시 계산할 수 있는 집계 캐시다. 옮길 이유가 없다'
}

/** 백업에 담지 않는 표. */
const NOT_BACKED_UP = {
  outbox: '보내다 만 변경이다. 복원해서 다시 보낼 것이 아니다'
}

function dexieTables() {
  const src = read('src/data/db.js')
  const names = new Set()
  // `db.version(n).stores({ 이름: '...' })` 안의 키들
  for (const block of src.matchAll(/\.stores\(\{([\s\S]*?)\}\)/g)) {
    for (const m of block[1].matchAll(/^\s*(\w+)\s*:/gm)) names.add(m[1])
  }
  return [...names]
}

const ALL = dexieTables()

describe('표를 새로 만들면 빠뜨리지 않는다', () => {
  it('스키마에서 표를 읽어 온다 (읽기 자체가 안 되면 아래가 전부 헛검사다)', () => {
    expect(ALL).toContain('students')
    expect(ALL).toContain('payments')
    expect(ALL.length).toBeGreaterThan(10)
  })

  it('백업에 다 들어간다', () => {
    const want = ALL.filter((t) => !(t in NOT_BACKED_UP))
    expect([...BACKUP_TABLES].sort()).toEqual(want.sort())
  })

  it('Pro 동기화 대상에 다 들어간다 (repo.js)', () => {
    const src = read('src/data/repo.js')
    const list = src.match(/const SYNCED_TABLES = new Set\(\[([\s\S]*?)\]\)/)[1]
    const got = [...list.matchAll(/'([^']+)'/g)].map((m) => m[1])
    expect(got.sort()).toEqual(ALL.filter((t) => !(t in NOT_SYNCED)).sort())
  })

  it('동기화가 실제로 도는 표 목록과 이름 대응에 다 들어간다 (sync.js)', () => {
    const src = read('src/data/sync.js')
    const tables = [...src.match(/const TABLES = \[([\s\S]*?)\]/)[1]
      .matchAll(/'([^']+)'/g)].map((m) => m[1])
    const pg = [...src.match(/const PG = \{([\s\S]*?)\n\}/)[1]
      .matchAll(/(\w+)\s*:/g)].map((m) => m[1])
    const want = ALL.filter((t) => !(t in NOT_SYNCED)).sort()
    expect(tables.sort()).toEqual(want)
    // 이름 대응이 빠지면 그 표만 조용히 안 올라간다
    expect(pg.sort()).toEqual(want)
  })
})

describe('Supabase 스키마도 같이 따라온다', () => {
  const sql = read('supabase/schema.sql')
  const pgName = (t) => t === 'counselLogs' ? 'counsel_logs' : t
  const synced = ALL.filter((t) => !(t in NOT_SYNCED)).map(pgName)

  it('표가 만들어진다', () => {
    for (const t of synced) {
      expect(sql, `create table ${t} 가 없습니다`).toMatch(new RegExp(`create table if not exists ${t}\\b`))
    }
  })

  // 여기서 빠지면 **다른 학원 자료가 보인다.** 이 저장소에서 제일 위험한 누락이다.
  it('RLS 가 켜진다', () => {
    const arrays = [...sql.matchAll(/foreach t in array array\[([^\]]+)\]/g)]
      .map((m) => [...m[1].matchAll(/'([^']+)'/g)].map((x) => x[1]))
    const rls = arrays.find((a) => a.includes('attendance') && !a.includes('academies'))
    expect(rls, 'RLS 배열을 못 찾았습니다').toBeTruthy()
    for (const t of synced) expect(rls, `${t} 에 RLS 가 안 걸립니다`).toContain(t)
  })

  it('updated_at 트리거가 붙는다 (안 붙으면 동기화 커서가 안 움직인다)', () => {
    const arrays = [...sql.matchAll(/foreach t in array array\[([^\]]+)\]/g)]
      .map((m) => [...m[1].matchAll(/'([^']+)'/g)].map((x) => x[1]))
    const touch = arrays.find((a) => a.includes('academies'))
    expect(touch, '트리거 배열을 못 찾았습니다').toBeTruthy()
    for (const t of synced) expect(touch, `${t} 에 트리거가 안 붙습니다`).toContain(t)
  })
})
