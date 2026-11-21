// 교재·진도 — 원생마다 "지금 어떤 책의 어디를 하고 있는지" 를 적어 둔다.
//
// 피아노학원에서 가장 자주 묻는 것이 "우리 아이 지금 어디 해요?" 다. 레슨이 끝날 때 한 줄만 적어 두면
// 원생 카드·학부모 리포트·레슨 안내 문자에 같은 내용이 그대로 실린다.
//
// 저장 위치는 원생의 custom 안 예약 키(_books)다. 표를 새로 만들지 않으므로 백업·Pro 동기화가
// 지금 구조 그대로 따라온다. '_' 로 시작하는 키는 원장이 만드는 학습 항목과 섞이지 않는다.

import { uid } from './id.js'

export const BOOKS_KEY = '_books'
const LOG_LIMIT = 20

/** 계열별로 자주 쓰는 교재 — 고르기만 하면 되게 미리 넣어 둔다 */
const MUSIC_BOOKS = [
  '바이엘 상', '바이엘 하', '어드벤처 1급', '어드벤처 2급', '체르니 100', '체르니 30', '체르니 40', '체르니 50',
  '하농', '소나티네', '소나타', '부르크뮐러 25', '인벤션', '피아노 명곡집', '반주법', '이론 · 계이름'
]
const ART_BOOKS = ['기초 드로잉', '수채화', '소묘', '포트폴리오']

export const BOOK_PRESETS = {
  음악: MUSIC_BOOKS,
  // '예체능' 은 예전 버전에서 음악·미술을 함께 묶던 이름이다. 그때 설정한 피아노학원도 교재가 나오게 둘 다 넣는다.
  예체능: [...ART_BOOKS, ...MUSIC_BOOKS],
  어학: ['파닉스 1', '파닉스 2', 'Reading 1', 'Reading 2', 'Grammar 1', 'Grammar 2', '단어장'],
  교과: ['개념서', '유형서', '심화서', '기출 문제집', '오답 노트'],
  체육: ['기본 동작', '품새', '겨루기', '승급 심사 준비'],
  공부방: ['국어', '수학', '영어', '독서']
}

export function booksOf(student) {
  const list = student?.custom?.[BOOKS_KEY]
  if (!Array.isArray(list)) return []
  // 지금 하는 책이 위, 끝낸 책은 최근에 끝낸 순서로 아래
  return [...list].sort((a, b) => {
    if (!!a.done_at !== !!b.done_at) return a.done_at ? 1 : -1
    return String(b.done_at || b.updated_at || '').localeCompare(String(a.done_at || a.updated_at || ''))
  })
}

export function activeBooks(student) {
  return booksOf(student).filter((b) => !b.done_at)
}

function withBooks(custom, list) {
  return { ...(custom || {}), [BOOKS_KEY]: list }
}

/** 새 교재를 붙인다. 같은 제목이 진행 중이면 진도만 고친다(두 번 등록되지 않게). */
export function addBook(custom, { title, progress = '' }, today) {
  const name = String(title || '').trim()
  if (!name) return custom || {}
  const list = Array.isArray(custom?.[BOOKS_KEY]) ? custom[BOOKS_KEY] : []
  const same = list.find((b) => !b.done_at && b.title === name)
  if (same) return setProgress(custom, same.id, progress || same.progress, today)
  const note = String(progress || '').trim()
  return withBooks(custom, [...list, {
    id: uid('bk'),
    title: name,
    progress: note,
    started_at: today,
    updated_at: today,
    done_at: null,
    log: note ? [{ date: today, progress: note }] : []
  }])
}

/** 진도를 고쳐 적는다. 바뀐 내용은 날짜와 함께 기록으로 남는다. */
export function setProgress(custom, bookId, progress, today) {
  const note = String(progress || '').trim()
  const list = (custom?.[BOOKS_KEY] || []).map((b) => {
    if (b.id !== bookId) return b
    if (note === (b.progress || '')) return b
    const log = [...(b.log || []).filter((l) => l.date !== today), { date: today, progress: note }]
    return { ...b, progress: note, updated_at: today, log: log.slice(-LOG_LIMIT) }
  })
  return withBooks(custom, list)
}

/** 교재를 끝냈다 / 다시 진행 중으로 되돌린다 */
export function setDone(custom, bookId, done, today) {
  const list = (custom?.[BOOKS_KEY] || []).map((b) =>
    b.id === bookId ? { ...b, done_at: done ? today : null, updated_at: today } : b)
  return withBooks(custom, list)
}

export function removeBook(custom, bookId) {
  return withBooks(custom, (custom?.[BOOKS_KEY] || []).filter((b) => b.id !== bookId))
}

/** 한 줄 요약 — 문자 문구의 {진도} 자리와 목록 화면에 쓴다 */
export function progressLine(student, sep = ' · ') {
  return activeBooks(student)
    .map((b) => (b.progress ? `${b.title} ${b.progress}` : b.title))
    .join(sep)
}

/** 리포트카드에 실을 항목 — 진행 중인 교재마다 한 줄 */
export function bookPairs(student) {
  return activeBooks(student).map((b) => ({ key: `book:${b.id}`, label: b.title, value: b.progress || '진행 중' }))
}

/**
 * 원생 정보를 고쳐 저장할 때, 화면에 없는 예약 항목(_books 등)이 지워지지 않게 이어 붙인다.
 * 학습 항목 값은 설정에 정의된 것만 남기므로(normalizeValues) 이 과정을 거치지 않으면 진도가 사라진다.
 */
export function keepReserved(prevCustom, nextCustom) {
  const out = { ...(nextCustom || {}) }
  for (const [k, v] of Object.entries(prevCustom || {})) {
    if (k.startsWith('_') && !(k in out)) out[k] = v
  }
  return out
}

/** 고를 수 있는 교재 목록 — 학원이 직접 넣은 것이 먼저, 그다음 계열 기본값. 이미 하는 책은 뺀다. */
export function bookSuggestions({ category = '', own = [], student = null, all = [] } = {}) {
  const using = new Set(activeBooks(student).map((b) => b.title))
  const seen = new Set()
  const out = []
  // 다른 원생이 쓰는 교재도 후보에 넣는다 — 우리 학원에서 실제로 쓰는 책이 가장 먼저 필요하다
  const inUse = all.flatMap((s) => booksOf(s).map((b) => b.title))
  for (const t of [...own, ...inUse, ...(BOOK_PRESETS[category] || [])]) {
    const name = String(t || '').trim()
    if (!name || seen.has(name) || using.has(name)) continue
    seen.add(name)
    out.push(name)
  }
  return out
}
