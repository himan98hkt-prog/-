// 연습 기록 형식 — 이 숫자는 학부모에게 나간다.
//
// 그래서 여기서 지키는 것은 하나다: **같은 연습이 두 번 세어지지 않고, 친 연습이
// 사라지지 않는다.** 원장님이 같은 파일을 두 번 넣으실 수도 있고, 학부모가 지난달
// 파일을 다시 보내실 수도 있다. 둘 다 흔한 일이고, 둘 다 숫자를 틀리게 만들면 안 된다.

import { describe, expect, it } from 'vitest'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  NEVER_IMPORT, PRACTICE_FORMAT, buildPractice, humanDuration, linkToStudents,
  localDate, mergePractice, parsePractice, practiceFilename, practiceKey,
  summarize, toPracticeEntry
} from '../src/core/practice-piano.js'

const row = (over = {}) => ({
  student_id: 's1', student: '김지우', song_id: 'p05', title: '왈츠',
  date: '2026-09-21', device: 'dhome', count: 2, seconds: 600, ...over
})

describe('기록 한 줄 받아들이기', () => {
  it('멀쩡한 줄은 그대로', () => {
    expect(toPracticeEntry(row())).toMatchObject({
      student_id: 's1', song_id: 'p05', date: '2026-09-21', count: 2, seconds: 600
    })
  })

  it('날짜가 날짜가 아니면 버린다', () => {
    expect(toPracticeEntry(row({ date: '2026/09/21' }))).toBeNull()
    expect(toPracticeEntry(row({ date: '' }))).toBeNull()
  })

  it('곡이나 사람을 모르면 버린다', () => {
    expect(toPracticeEntry(row({ song_id: '' }))).toBeNull()
    expect(toPracticeEntry(row({ student_id: '', student: '' }))).toBeNull()
  })

  it('아무것도 안 한 줄은 넣지 않는다', () => {
    expect(toPracticeEntry(row({ count: 0, seconds: 0 }))).toBeNull()
  })

  // 하루에 30시간 연습했다는 기록이 리포트에 찍히면 그 리포트는 끝이다
  it('말이 안 되는 값은 잘라 낸다', () => {
    expect(toPracticeEntry(row({ seconds: 999999 })).seconds).toBe(86400)
    expect(toPracticeEntry(row({ count: 100000 })).count).toBe(999)
    expect(toPracticeEntry(row({ seconds: -5, count: 1 })).seconds).toBe(0)
  })

  it('개인정보는 애초에 자리가 없다', () => {
    const dirty = row({ phone: '010-0000-0000', parent_phone: '010-1111-2222', memo: '비밀' })
    const clean = toPracticeEntry(dirty)
    for (const key of NEVER_IMPORT) expect(clean).not.toHaveProperty(key)
    expect(JSON.stringify(clean)).not.toContain('010-')
  })
})

describe('파일 만들고 읽기', () => {
  it('만든 것을 그대로 다시 읽는다', () => {
    const file = buildPractice([row(), row({ date: '2026-09-22' })], { academy: '아첼', device: 'dhome' })
    expect(file.format).toBe(PRACTICE_FORMAT)
    const back = parsePractice(JSON.stringify(file))
    expect(back.practice).toHaveLength(2)
    expect(back.academy).toBe('아첼')
  })

  it('다른 파일은 거절한다', () => {
    expect(() => parsePractice('{}')).toThrow(/연습 기록 파일이 아닙니다/)
    expect(() => parsePractice('그냥 글')).toThrow(/읽을 수 없습니다/)
    expect(() => parsePractice(JSON.stringify({ format: PRACTICE_FORMAT, version: 99, practice: [] })))
      .toThrow(/업데이트/)
  })

  it('줄에 기기가 없으면 파일의 기기를 쓴다', () => {
    const file = buildPractice([row({ device: '' })], { device: 'dphone' })
    expect(parsePractice(file).practice[0].device).toBe('dphone')
  })

  it('이상한 줄이 섞여 있어도 나머지는 읽는다', () => {
    const file = { format: PRACTICE_FORMAT, version: 1, practice: [row(), { date: '없음' }] }
    expect(parsePractice(file).practice).toHaveLength(1)
  })
})

describe('합치기 — 두 번 넣어도 안 늘어난다', () => {
  it('같은 파일을 두 번 넣어도 합계가 그대로', () => {
    const rows = [toPracticeEntry(row())]
    const once = mergePractice([], rows)
    const twice = mergePractice(once.rows, rows)
    expect(summarize(once.rows).seconds).toBe(600)
    expect(summarize(twice.rows).seconds).toBe(600)
    expect(twice.added).toBe(0)
    expect(twice.same).toBe(1)
  })

  // 학원에서도 치고 집에서도 쳤으면 둘 다 센다. 기기를 안 나누면 하나가 사라진다.
  it('같은 날 같은 곡이라도 기기가 다르면 따로 센다', () => {
    const home = toPracticeEntry(row({ device: 'dhome', seconds: 600, count: 2 }))
    const academy = toPracticeEntry(row({ device: 'dacademy', seconds: 300, count: 1 }))
    const { rows } = mergePractice([home], [academy])
    expect(rows).toHaveLength(2)
    expect(summarize(rows).seconds).toBe(900)
    expect(summarize(rows).count).toBe(3)
  })

  it('같은 기기가 더 친 뒤 다시 보내면 늘어난 만큼만 반영된다', () => {
    const before = toPracticeEntry(row({ seconds: 600, count: 2 }))
    const after = toPracticeEntry(row({ seconds: 900, count: 3 }))
    const { rows, updated } = mergePractice([before], [after])
    expect(rows).toHaveLength(1)
    expect(updated).toBe(1)
    expect(summarize(rows)).toMatchObject({ seconds: 900, count: 3 })
  })

  // 지난주 파일을 다시 보내시는 일은 실제로 생긴다
  it('옛날 파일이 최신 기록을 깎지 못한다', () => {
    const latest = toPracticeEntry(row({ seconds: 900, count: 3 }))
    const stale = toPracticeEntry(row({ seconds: 600, count: 2 }))
    const { rows } = mergePractice([latest], [stale])
    expect(summarize(rows)).toMatchObject({ seconds: 900, count: 3 })
  })

  it('id 를 아는 기록과 이름만 아는 기록은 서로 다른 줄이다', () => {
    const byId = toPracticeEntry(row({ student_id: 's1' }))
    const byName = toPracticeEntry(row({ student_id: '' }))
    expect(practiceKey(byId)).not.toBe(practiceKey(byName))
  })
})

describe('학생에게 붙이기', () => {
  const students = [{ id: 's1', name: '김지우' }, { id: 's2', name: '박서준' }]

  it('id 가 맞으면 그대로', () => {
    const { linked, unmatched } = linkToStudents([toPracticeEntry(row())], students)
    expect(linked).toHaveLength(1)
    expect(unmatched).toHaveLength(0)
  })

  it('id 가 없으면 이름으로 찾는다', () => {
    const { linked } = linkToStudents([toPracticeEntry(row({ student_id: '' }))], students)
    expect(linked[0].student_id).toBe('s1')
  })

  // 남의 아이 연습이 우리 아이 리포트에 찍히는 것이 제일 나쁜 고장이다
  it('동명이인이면 아무 데도 안 붙이고 돌려준다', () => {
    const two = [{ id: 's1', name: '김지우' }, { id: 's9', name: '김지우' }]
    const { linked, unmatched } = linkToStudents([toPracticeEntry(row({ student_id: '' }))], two)
    expect(linked).toHaveLength(0)
    expect(unmatched).toHaveLength(1)
  })

  it('명단에 없는 id 는 이름으로 다시 찾아본다', () => {
    const { linked } = linkToStudents([toPracticeEntry(row({ student_id: '없는id' }))], students)
    expect(linked[0].student_id).toBe('s1')
  })

  it('찾지 못한 기록은 버리지 않는다', () => {
    const { unmatched } = linkToStudents(
      [toPracticeEntry(row({ student_id: '', student: '누구세요' }))], students)
    expect(unmatched).toHaveLength(1)
  })
})

describe('리포트에 쓸 요약', () => {
  const rows = [
    toPracticeEntry(row({ date: '2026-09-01', seconds: 600, count: 2, title: '왈츠' })),
    toPracticeEntry(row({ date: '2026-09-02', seconds: 900, count: 3, title: '왈츠' })),
    toPracticeEntry(row({ date: '2026-09-02', song_id: 'p06', seconds: 300, count: 1, title: '미뉴에트' })),
    toPracticeEntry(row({ date: '2026-08-30', seconds: 1200, count: 4 })),
  ]

  it('그 달만 센다', () => {
    const s = summarize(rows, '2026-09')
    expect(s.days).toBe(2)
    expect(s.count).toBe(6)
    expect(s.minutes).toBe(30)
  })

  it('많이 친 곡이 앞에 온다', () => {
    expect(summarize(rows, '2026-09').songs[0]).toEqual({ title: '왈츠', count: 5 })
  })

  it('달을 안 주면 전부 센다', () => {
    expect(summarize(rows).days).toBe(3)
  })

  it('기록이 없으면 0', () => {
    expect(summarize([], '2026-09')).toMatchObject({ days: 0, count: 0, seconds: 0 })
  })

  it('사람이 읽는 시간', () => {
    expect(humanDuration(0)).toBe('0분')
    expect(humanDuration(90)).toBe('2분')
    expect(humanDuration(3600)).toBe('1시간')
    expect(humanDuration(13200)).toBe('3시간 40분')
  })
})

describe('날짜와 파일 이름', () => {
  it('지역 시간의 날짜를 쓴다', () => {
    const d = new Date(2026, 8, 21, 23, 30)
    expect(localDate(d)).toBe('2026-09-21')
  })

  // 한국에서 밤 12시 반에 친 연습이 전날로 기록되면 학부모가 바로 물어보신다.
  // 이건 이 기계의 시간대(UTC)에서는 드러나지 않는 고장이라, 시간대를 바꿔 실제로 돌려 본다.
  it('시간대가 한국이면 한국 날짜가 나온다 (UTC 날짜가 아니라)', () => {
    const code = `
      import { localDate } from '${resolve(import.meta.dirname, '../src/core/practice-piano.js')}'
      const t = new Date('2026-09-21T15:30:00Z')   // 서울에서는 9월 22일 00:30
      console.log(JSON.stringify({ local: localDate(t), utc: t.toISOString().slice(0, 10) }))
    `
    const out = execFileSync('node', ['--input-type=module', '-e', code], {
      encoding: 'utf8', env: { ...process.env, TZ: 'Asia/Seoul' }
    })
    const { local, utc } = JSON.parse(out)
    expect(utc).toBe('2026-09-21')      // UTC 로 적었다면 하루 전으로 갔을 자리
    expect(local).toBe('2026-09-22')
  })

  it('파일 이름에 학원과 아이가 들어간다', () => {
    expect(practiceFilename('아첼 음악학원', '김지우')).toMatch(/^아첼 음악학원-김지우-연습기록-\d{4}-\d{2}-\d{2}\.json$/)
    expect(practiceFilename('', '')).toMatch(/^학원-연습기록-/)
  })

  it('파일 이름에 경로 문자가 섞이지 않는다', () => {
    expect(practiceFilename('a/b:c*학원', '')).not.toMatch(/[\\/:*?"<>|]/)
  })
})

describe('플레이어에 들어가는 사본', () => {
  // 형식을 한쪽에서만 고치면 원장님 쪽에서 파일이 안 읽힌다. 그 고장은 우리 화면에서
  // 안 보이고 현장에서만 보이므로, 여기서 글자 단위로 막는다.
  it('관리노트와 플레이어가 같은 파일을 쓴다', () => {
    const root = resolve(import.meta.dirname, '..')
    const mine = readFileSync(resolve(root, 'src/core/practice-piano.js'), 'utf8')
    const theirs = readFileSync(
      resolve(root, 'mr/server/static/player/js/practice-format.js'), 'utf8')
    expect(theirs, 'npm run sync:shared 로 맞추세요').toBe(mine)
  })
})
