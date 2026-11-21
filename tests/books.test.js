import { describe, it, expect } from 'vitest'
import {
  BOOKS_KEY, booksOf, activeBooks, addBook, setProgress, setDone, removeBook,
  progressLine, bookPairs, keepReserved, bookSuggestions
} from '../src/core/books.js'
import { normalizeValues, displayPairs } from '../src/core/customfields.js'
import { withDefaults, DEFAULT_TEMPLATES, renderTemplate, unknownVars } from '../src/core/templates.js'
import { setupSteps, setupProgress } from '../src/core/onboarding.js'

const D1 = '2026-11-16'
const D2 = '2026-11-18'

describe('교재·진도', () => {
  it('교재를 붙이면 진행 중 목록에 나타난다', () => {
    const custom = addBook({}, { title: '체르니 30', progress: '12번' }, D1)
    const s = { custom }
    expect(activeBooks(s)).toHaveLength(1)
    expect(activeBooks(s)[0]).toMatchObject({ title: '체르니 30', progress: '12번', started_at: D1, done_at: null })
  })

  it('같은 교재를 또 붙이면 새로 만들지 않고 진도만 고친다', () => {
    let custom = addBook({}, { title: '하농', progress: '5번' }, D1)
    custom = addBook(custom, { title: '하농', progress: '8번' }, D2)
    expect(custom[BOOKS_KEY]).toHaveLength(1)
    expect(custom[BOOKS_KEY][0].progress).toBe('8번')
  })

  it('진도를 고치면 날짜와 함께 기록이 쌓인다 (지난주 어디까지 했는지 볼 수 있게)', () => {
    let custom = addBook({}, { title: '소나티네', progress: '4번 1악장' }, D1)
    const id = custom[BOOKS_KEY][0].id
    custom = setProgress(custom, id, '4번 2악장', D2)
    const book = custom[BOOKS_KEY][0]
    expect(book.progress).toBe('4번 2악장')
    expect(book.updated_at).toBe(D2)
    expect(book.log).toEqual([{ date: D1, progress: '4번 1악장' }, { date: D2, progress: '4번 2악장' }])
  })

  it('같은 날 여러 번 고치면 그날 기록은 마지막 것 하나만 남는다', () => {
    let custom = addBook({}, { title: '하농', progress: '1번' }, D1)
    const id = custom[BOOKS_KEY][0].id
    custom = setProgress(custom, id, '2번', D1)
    custom = setProgress(custom, id, '3번', D1)
    expect(custom[BOOKS_KEY][0].log).toEqual([{ date: D1, progress: '3번' }])
  })

  it('내용이 그대로면 기록을 늘리지 않는다', () => {
    let custom = addBook({}, { title: '하농', progress: '1번' }, D1)
    const before = custom[BOOKS_KEY][0]
    custom = setProgress(custom, before.id, '1번', D2)
    expect(custom[BOOKS_KEY][0]).toEqual(before)
  })

  it('끝낸 교재는 진행 중에서 빠지고, 되돌릴 수 있다', () => {
    let custom = addBook({}, { title: '바이엘 하', progress: '끝' }, D1)
    const id = custom[BOOKS_KEY][0].id
    custom = setDone(custom, id, true, D2)
    expect(activeBooks({ custom })).toHaveLength(0)
    expect(booksOf({ custom })[0].done_at).toBe(D2)
    custom = setDone(custom, id, false, D2)
    expect(activeBooks({ custom })).toHaveLength(1)
  })

  it('진행 중인 책이 위, 끝낸 책이 아래에 온다', () => {
    let custom = addBook({}, { title: '바이엘 하' }, D1)
    custom = setDone(custom, custom[BOOKS_KEY][0].id, true, D1)
    custom = addBook(custom, { title: '체르니 100', progress: '3번' }, D2)
    expect(booksOf({ custom }).map((b) => b.title)).toEqual(['체르니 100', '바이엘 하'])
  })

  it('지울 수 있다', () => {
    let custom = addBook({}, { title: '하농' }, D1)
    custom = removeBook(custom, custom[BOOKS_KEY][0].id)
    expect(booksOf({ custom })).toEqual([])
  })

  it('이름이 비어 있으면 붙이지 않는다', () => {
    expect(addBook({ level: 'A' }, { title: '   ' }, D1)).toEqual({ level: 'A' })
  })

  it('문자·목록에 쓰는 한 줄 요약', () => {
    let custom = addBook({}, { title: '체르니 30', progress: '12번' }, D1)
    custom = addBook(custom, { title: '하농' }, D1)
    const line = progressLine({ custom })
    expect(line).toContain('체르니 30 12번')
    expect(line).toContain('하농')
    expect(progressLine({ custom: {} })).toBe('')
  })

  it('리포트카드에는 진행 중인 교재가 한 줄씩 실린다', () => {
    let custom = addBook({}, { title: '체르니 30', progress: '12번' }, D1)
    custom = addBook(custom, { title: '하농' }, D1)
    expect(bookPairs({ custom }).map((p) => [p.label, p.value])).toEqual(
      expect.arrayContaining([['체르니 30', '12번'], ['하농', '진행 중']]))
  })

  it('원생 정보를 고쳐 저장해도 진도가 지워지지 않는다', () => {
    const fields = [{ key: 'level', label: '레벨', type: 'text' }]
    const prev = addBook({ level: 'A' }, { title: '체르니 30', progress: '12번' }, D1)
    // 원생 수정 화면은 설정에 정의된 학습 항목만 다시 모은다 — 여기서 _books 가 떨어져 나간다
    const fromForm = normalizeValues(fields, { level: 'B' })
    expect(fromForm[BOOKS_KEY]).toBeUndefined()
    const saved = keepReserved(prev, fromForm)
    expect(saved.level).toBe('B')
    expect(saved[BOOKS_KEY]).toHaveLength(1)
  })

  it('진도는 학습 항목 표에 섞여 나오지 않는다', () => {
    const fields = [{ key: 'level', label: '레벨', type: 'text', onCard: true }]
    const custom = addBook({ level: 'A' }, { title: '하농' }, D1)
    expect(displayPairs(fields, custom, 'card')).toEqual([{ key: 'level', label: '레벨', value: 'A' }])
  })

  it('교재 후보는 우리 학원에서 쓰는 책이 먼저, 이미 하는 책은 뺀다', () => {
    const me = { custom: addBook({}, { title: '하농' }, D1) }
    const other = { custom: addBook({}, { title: '우리학원 자체교재' }, D1) }
    const list = bookSuggestions({ category: '음악', student: me, all: [me, other] })
    expect(list[0]).toBe('우리학원 자체교재')
    expect(list).toContain('체르니 30')
    expect(list).not.toContain('하농')
    expect(new Set(list).size).toBe(list.length)
  })
})

describe('알림 문구', () => {
  it('새로 생긴 기본 문구는 기존 사용자에게도 덧붙는다 (고쳐 둔 문구는 그대로)', () => {
    const saved = [{ id: 'absent', name: '결석 안내', body: '원장이 고친 문구' }]
    const merged = withDefaults(saved)
    expect(merged[0].body).toBe('원장이 고친 문구')
    expect(merged.map((t) => t.id)).toEqual(expect.arrayContaining(['absent', 'payment', 'report', 'lesson', 'recruit']))
    expect(merged.filter((t) => t.id === 'absent')).toHaveLength(1)
  })

  it('저장된 것이 없으면 기본 문구를 그대로 준다', () => {
    expect(withDefaults(null)).toEqual(DEFAULT_TEMPLATES)
    expect(withDefaults([])).toEqual(DEFAULT_TEMPLATES)
  })

  it('레슨 안내 문구에 {진도} 가 채워진다', () => {
    const lesson = DEFAULT_TEMPLATES.find((t) => t.id === 'lesson')
    expect(unknownVars(lesson.body)).toEqual([])
    const text = renderTemplate(lesson.body, { '{학원명}': '아첼 음악학원', '{원생명}': '김하늘', '{진도}': '체르니 30 12번 · 하농 8번' })
    expect(text).toContain('김하늘 학생')
    expect(text).toContain('체르니 30 12번 · 하농 8번')
    expect(text).not.toContain('{')
  })
})

describe('시작 가이드', () => {
  it('아무것도 없을 때는 "반 만들기" 부터 안내한다', () => {
    const p = setupProgress(setupSteps({}))
    expect(p).toMatchObject({ done: 0, total: 4, complete: false })
    expect(p.next.id).toBe('class')
    expect(p.next.view).toBe('timetable')
  })

  it('한 가지를 끝낼 때마다 다음 단계로 넘어간다', () => {
    expect(setupProgress(setupSteps({ classes: 1 })).next.id).toBe('student')
    expect(setupProgress(setupSteps({ classes: 1, students: 3 })).next.id).toBe('attendance')
    expect(setupProgress(setupSteps({ classes: 1, students: 3, hasAttendance: true })).next.id).toBe('payment')
  })

  it('순서를 건너뛰어도 안 한 것 중 가장 앞의 것을 안내한다', () => {
    const p = setupProgress(setupSteps({ students: 5, hasPayments: true }))
    expect(p.done).toBe(2)
    expect(p.next.id).toBe('class')
  })

  it('네 가지를 모두 하면 끝난다', () => {
    const p = setupProgress(setupSteps({ classes: 2, students: 10, hasAttendance: true, hasPayments: true }))
    expect(p).toMatchObject({ done: 4, complete: true, next: null })
  })
})
