// 교재·진도 칸 — 원생 카드와 출결 화면의 "자세히" 창이 함께 쓴다.
//
// 레슨이 끝난 자리에서 한 줄 적는 것이 전부다: 교재 옆 칸에 "12번" 이라고 쓰고 다른 곳을 누르면 저장된다.
// 저장 버튼을 따로 찾지 않아도 되도록 칸을 벗어나면(또는 Enter) 바로 반영한다.

import { h, clear, toast, confirmDialog } from './dom.js'
import { icon } from './icons.js'
import * as repo from '../data/repo.js'
import { toYmd } from '../core/date.js'
import { booksOf, addBook, setProgress, setDone, removeBook, bookSuggestions } from '../core/books.js'

const shortDate = (ymd) => (ymd ? `${Number(ymd.slice(5, 7))}/${Number(ymd.slice(8, 10))}` : '')

/**
 * @param {string} studentId
 * @param {{canWrite?:boolean, onChange?:Function}} opts
 * @returns {HTMLElement}
 */
export function booksPanel(studentId, { canWrite = true, onChange } = {}) {
  const box = h('div', { class: 'books' })
  const current = () => repo.cache.studentById.get(studentId)

  async function save(nextCustom, message) {
    const student = current()
    if (!student) return
    await repo.put('students', { ...student, custom: nextCustom })
    if (message) toast(message, 'ok')
    paint()
    onChange?.(current())
  }

  function paint() {
    const student = current()
    const all = booksOf(student)
    const active = all.filter((b) => !b.done_at)
    const finished = all.filter((b) => b.done_at)
    clear(box)

    if (!active.length) {
      box.append(h('p', { class: 'small muted', style: { margin: '0 0 10px' } },
        canWrite ? '아직 적어 둔 교재가 없습니다. 아래에서 교재를 골라 추가하세요.' : '적어 둔 교재가 없습니다.'))
    }

    for (const book of active) {
      const prev = (book.log || []).filter((l) => l.progress !== book.progress).at(-1)
      const input = h('input', {
        type: 'text', value: book.progress || '', placeholder: '오늘 진도  예) 12번', disabled: !canWrite,
        'aria-label': `${book.title} 진도`, dataset: { book: book.title }
      })
      const commit = () => {
        if (input.value.trim() === (book.progress || '')) return
        save(setProgress(current().custom, book.id, input.value, toYmd()), '진도를 적었습니다')
      }
      input.addEventListener('blur', commit)
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter') input.blur() })

      box.append(h('div', { class: 'book-row' },
        h('div', { class: 'book-title' },
          h('b', {}, book.title),
          h('span', { class: 'tiny muted' },
            book.updated_at ? `${shortDate(book.updated_at)} 기록` : '',
            prev ? ` · 그 전 ${shortDate(prev.date)} ${prev.progress}` : '')),
        input,
        canWrite
          ? h('button', {
            class: 'btn sm soft', type: 'button', title: '이 교재를 다 끝냈을 때 누릅니다',
            onClick: () => save(setDone(current().custom, book.id, true, toYmd()), `${book.title} — 끝낸 교재로 옮겼습니다`)
          }, icon('check', { size: 15, stroke: 2.2 }), '끝냄')
          : null))
    }

    if (canWrite) {
      const options = bookSuggestions({
        category: repo.getSetting('category', ''),
        own: repo.getSetting('bookList', []),
        student,
        all: repo.cache.students
      })
      const listId = `books-${studentId}`
      const title = h('input', { type: 'text', placeholder: '교재 이름  예) 체르니 30', list: listId, 'aria-label': '추가할 교재', dataset: { book: 'new-title' } })
      const prog = h('input', { type: 'text', placeholder: '진도 (나중에 적어도 됩니다)', 'aria-label': '진도', dataset: { book: 'new-progress' } })
      const add = () => {
        if (!title.value.trim()) { toast('교재 이름을 넣어 주세요', 'error'); title.focus(); return }
        save(addBook(current().custom, { title: title.value, progress: prog.value }, toYmd()), '교재를 추가했습니다')
      }
      for (const el of [title, prog]) el.addEventListener('keydown', (e) => { if (e.key === 'Enter') add() })

      box.append(h('div', { class: 'book-add' },
        h('datalist', { id: listId }, ...options.map((o) => h('option', { value: o }))),
        title, prog,
        h('button', { class: 'btn sm', type: 'button', dataset: { book: 'add' }, onClick: add }, icon('plus', { size: 15 }), '교재 추가')))
    }

    if (finished.length) {
      box.append(h('details', { class: 'book-done' },
        h('summary', {}, `끝낸 교재 ${finished.length}권`),
        ...finished.map((book) => h('div', { class: 'row small', style: { padding: '6px 0' } },
          h('span', { class: 'grow' }, book.title, h('span', { class: 'muted' }, ` · ${shortDate(book.done_at)} 끝냄`)),
          canWrite ? h('button', {
            class: 'linkbtn', type: 'button',
            onClick: () => save(setDone(current().custom, book.id, false, toYmd()), '다시 진행 중으로 옮겼습니다')
          }, '다시 진행') : null,
          canWrite ? h('button', {
            class: 'linkbtn', type: 'button', style: { color: 'var(--danger)' },
            onClick: async () => {
              if (!await confirmDialog(`${book.title} 기록을 지울까요?`, { danger: true, okLabel: '지우기' })) return
              save(removeBook(current().custom, book.id))
            }
          }, '지우기') : null))))
    }
  }

  paint()
  return box
}
