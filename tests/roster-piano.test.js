import { describe, it, expect } from 'vitest'
import {
  buildRoster, parseRoster, toRosterEntry, rosterFilename,
  ROSTER_FORMAT, ROSTER_FIELDS, NEVER_EXPORT
} from '../src/core/roster-piano.js'

// 관리노트의 진짜 학생 레코드 모양 그대로 (src/data/seed.js 참고)
const student = (over = {}) => ({
  id: 's1',
  name: '김지우',
  school: '행복초',
  grade: '3학년',
  phone: '010-1234-5678',
  parent_phone: '010-9876-5432',
  siblings_group: 'g1',
  status: '재원',
  joined_at: '2026-03-02',
  memo: '왼손이 약함',
  custom: { 레벨: 'B' },
  discount: { memo: '장기 등록', amount: 20000 },
  updated_at: '2026-09-01T00:00:00.000Z',
  ...over
})

describe('피아노 반주 연동 명단', () => {
  it('연락처·메모·수납 정보는 넘기지 않는다', () => {
    // 반주를 만드는 데 하나도 안 쓰인다. 넘기면 개인정보가 두 시스템에 흩어진다.
    const entry = toRosterEntry(student(), '월수금 4시')
    expect(Object.keys(entry).sort()).toEqual([...ROSTER_FIELDS].sort())
    const blob = JSON.stringify(entry)
    for (const field of NEVER_EXPORT) {
      expect(blob).not.toContain(field)
    }
    expect(blob).not.toContain('010-')
    expect(blob).not.toContain('왼손이 약함')
    expect(blob).not.toContain('장기 등록')
  })

  it('명단 전체를 내보내도 연락처가 한 줄도 안 섞인다', () => {
    const roster = buildRoster(
      [student(), student({ id: 's2', name: '박서준', phone: '010-0000-1111' })],
      [{ student_id: 's1', class_id: 'c1', ended_at: null }],
      [{ id: 'c1', name: '월수금 4시' }],
      { academy: '행복피아노' }
    )
    const blob = JSON.stringify(roster)
    expect(blob).not.toMatch(/010-\d/)
    expect(roster.students).toHaveLength(2)
    expect(roster.academy).toBe('행복피아노')
  })

  it('지금 다니는 반만 붙인다 (끝난 등록은 무시)', () => {
    const roster = buildRoster(
      [student()],
      [
        { student_id: 's1', class_id: 'c0', ended_at: '2026-06-30' },
        { student_id: 's1', class_id: 'c1', ended_at: null }
      ],
      [{ id: 'c0', name: '예전 반' }, { id: 'c1', name: '월수금 4시' }]
    )
    expect(roster.students[0].class).toBe('월수금 4시')
  })

  it('반이 없어도 학생은 나간다', () => {
    const roster = buildRoster([student()], [], [])
    expect(roster.students[0].class).toBe('')
  })

  it('휴원·퇴원은 표시만 하고 빼지는 않는다', () => {
    // 발표회 명단을 짤 때 원장님이 보고 고르시면 된다. 여기서 임의로 빼면
    // "왜 그 아이가 안 보이지" 가 된다.
    const roster = buildRoster(
      [student(), student({ id: 's2', name: '박서준', status: '휴원' })], [], []
    )
    expect(roster.students).toHaveLength(2)
    expect(roster.students.find((s) => s.name === '박서준').active).toBe(false)
    expect(roster.students.find((s) => s.name === '김지우').active).toBe(true)
  })

  it('이름 없는 줄은 버린다', () => {
    const roster = buildRoster([student(), student({ id: 's2', name: '  ' })], [], [])
    expect(roster.students).toHaveLength(1)
  })

  it('가나다순으로 정렬한다', () => {
    const roster = buildRoster([
      student({ id: 'a', name: '한지호' }),
      student({ id: 'b', name: '강민준' }),
      student({ id: 'c', name: '박서준' })
    ], [], [])
    expect(roster.students.map((s) => s.name)).toEqual(['강민준', '박서준', '한지호'])
  })

  it('id 는 문자열로 고정한다 (반주 쪽이 이걸로 연결한다)', () => {
    const roster = buildRoster([student({ id: 12 })], [], [])
    expect(roster.students[0].id).toBe('12')
  })
})

describe('명단 읽기', () => {
  const good = () => buildRoster([student()], [], [], { academy: '행복피아노' })

  it('내보낸 것을 그대로 읽는다', () => {
    const parsed = parseRoster(JSON.stringify(good()))
    expect(parsed.format).toBe(ROSTER_FORMAT)
    expect(parsed.students[0].name).toBe('김지우')
  })

  it('JSON 이 아니면 거절한다', () => {
    expect(() => parseRoster('이건 파일이 아니다')).toThrow('JSON')
  })

  it('다른 앱의 백업 파일은 거절한다', () => {
    expect(() => parseRoster('{"format":"academy-note-backup","students":[]}'))
      .toThrow('명단 파일이 아닙니다')
  })

  it('더 최신 버전은 거절하고 이유를 말한다', () => {
    const future = { ...good(), version: 99 }
    expect(() => parseRoster(JSON.stringify(future))).toThrow('업데이트')
  })

  it('students 가 배열이 아니면 거절한다', () => {
    expect(() => parseRoster('{"format":"academy-note-piano-roster","students":null}'))
      .toThrow('비어 있습니다')
  })
})

describe('파일 이름', () => {
  it('학원명과 날짜가 들어간다', () => {
    const name = rosterFilename('행복피아노')
    expect(name).toMatch(/^행복피아노-반주명단-\d{4}-\d{2}-\d{2}\.json$/)
  })

  it('파일명에 못 쓰는 글자를 뺀다', () => {
    expect(rosterFilename('행복/피아노:학원')).toMatch(/^행복피아노학원-/)
  })

  it('학원명이 없으면 그냥 학원으로', () => {
    expect(rosterFilename('')).toMatch(/^학원-반주명단-/)
  })
})
