import { describe, it, expect } from 'vitest'
import { buildBackup, parseBackup, toProPayload, BACKUP_TABLES, BACKUP_VERSION } from '../src/core/backup.js'

const sample = {
  students: [{ id: 's1', name: '김서준', custom: { belt: '흰띠' } }],
  attendance: [{ id: 'a1', student_id: 's1', date: '2026-03-02', status: '출석' }],
  payments: [{ id: 'p1', student_id: 's1', month: '2026-03', amount: 150000 }]
}

describe('백업 파일', () => {
  it('내보내고 다시 읽으면 동일한 데이터', () => {
    const backup = buildBackup(sample, { plan: 'lite', academy: '아라 잉글리시' })
    const parsed = parseBackup(JSON.stringify(backup))
    expect(parsed.data.students).toEqual(sample.students)
    expect(parsed.counts.attendance).toBe(1)
    expect(parsed.academy).toBe('아라 잉글리시')
  })

  it('모든 테이블 키가 존재한다 (빈 배열이라도)', () => {
    const parsed = parseBackup(JSON.stringify(buildBackup({})))
    for (const t of BACKUP_TABLES) expect(Array.isArray(parsed.data[t])).toBe(true)
  })

  it('다른 앱 파일이나 깨진 JSON 은 거부한다', () => {
    expect(() => parseBackup('{"format":"other"}')).toThrow(/이 앱의 백업/)
    expect(() => parseBackup('not json')).toThrow(/읽을 수 없습니다/)
  })

  it('더 최신 버전 백업은 거부한다', () => {
    const future = { ...buildBackup(sample), version: BACKUP_VERSION + 1 }
    expect(() => parseBackup(JSON.stringify(future))).toThrow(/업데이트/)
  })

  it('구버전(v0) 영문 출결 상태를 한글로 올린다', () => {
    const old = {
      format: 'academy-note-backup', version: 0,
      data: { attendance: [{ id: 'a', status: 'absent' }], students: [{ id: 's' }] }
    }
    const parsed = parseBackup(JSON.stringify(old))
    expect(parsed.version).toBe(BACKUP_VERSION)
    expect(parsed.data.attendance[0].status).toBe('결석')
    expect(parsed.data.students[0].custom).toEqual({})
  })
})

describe('Pro 마이그레이션 페이로드', () => {
  it('모든 레코드에 academy_id 를 붙인다', () => {
    const payload = toProPayload(parseBackup(JSON.stringify(buildBackup(sample))), 'acad-1')
    expect(payload.students[0].academy_id).toBe('acad-1')
    expect(payload.attendance[0].academy_id).toBe('acad-1')
  })

  it('로컬 전용 테이블(settings·집계캐시)은 올리지 않는다', () => {
    const payload = toProPayload(parseBackup(JSON.stringify(buildBackup(sample))), 'acad-1')
    expect(payload.settings).toBeUndefined()
    expect(payload.monthlyStats).toBeUndefined()
  })

  it('academy_id 없이 호출하면 실패한다', () => {
    expect(() => toProPayload(buildBackup(sample), null)).toThrow(/academy_id/)
  })
})
