// 지출 탭 — 월별 지출 입력/목록/카테고리 합계

import { h, clear, toast, modal, field, confirmDialog } from '../dom.js'
import { formatWon } from '../../core/fees.js'
import { toMonth, toYmd, addMonths } from '../../core/date.js'
import { EXPENSE_CATEGORIES } from '../../data/repo.js'

export async function render(root, ctx) {
  const { repo } = ctx
  const canWrite = ctx.can('expenses:write') || ctx.can('*')
  let month = toMonth(toYmd())

  const totalBox = h('div', { class: 'grid cols3' })
  const tbody = h('tbody')
  const monthInput = h('input', { type: 'month', value: month, style: { maxWidth: '160px' }, onChange: (e) => { month = e.target.value; load() } })

  root.append(
    h('div', { class: 'card' },
      h('div', { class: 'row wrap' },
        h('button', { class: 'btn sm', onClick: () => { month = addMonths(month, -1); monthInput.value = month; load() } }, '‹'),
        monthInput,
        h('button', { class: 'btn sm', onClick: () => { month = addMonths(month, 1); monthInput.value = month; load() } }, '›'),
        canWrite ? h('button', { class: 'btn primary right', onClick: () => openEditor() }, '+ 지출 등록') : null
      )
    ),
    h('div', { style: { marginTop: '12px' } }, totalBox),
    h('div', { class: 'card', style: { marginTop: '12px' } },
      h('table', {}, h('thead', {}, h('tr', {}, h('th', {}, '날짜'), h('th', {}, '항목'), h('th', {}, '금액'), h('th', {}, '메모'), h('th', {}, ''))), tbody))
  )

  async function load() {
    const rows = (await repo.expensesOfMonth(month)).sort((a, b) => String(b.date).localeCompare(String(a.date)))
    const total = rows.reduce((s, e) => s + (Number(e.amount) || 0), 0)
    const byCat = new Map()
    for (const e of rows) byCat.set(e.category, (byCat.get(e.category) || 0) + (Number(e.amount) || 0))
    const top = [...byCat.entries()].sort((a, b) => b[1] - a[1])

    clear(totalBox)
    totalBox.append(
      h('div', { class: 'stat' }, h('div', { class: 'v' }, formatWon(total)), h('div', { class: 'l' }, '이번 달 지출')),
      h('div', { class: 'stat' }, h('div', { class: 'v' }, `${rows.length}건`), h('div', { class: 'l' }, '건수')),
      h('div', { class: 'stat' }, h('div', { class: 'v' }, top[0] ? `${top[0][0]}` : '-'), h('div', { class: 'l' }, top[0] ? `최대 항목 ${formatWon(top[0][1])}` : '최대 항목'))
    )

    clear(tbody)
    if (!rows.length) tbody.append(h('tr', {}, h('td', { colSpan: 5, class: 'muted' }, '등록된 지출이 없습니다')))
    for (const e of rows) {
      tbody.append(h('tr', {},
        h('td', {}, e.date),
        h('td', {}, h('span', { class: 'badge' }, e.category || '기타')),
        h('td', {}, formatWon(e.amount)),
        h('td', { class: 'muted small' }, e.memo || ''),
        h('td', {}, canWrite ? h('button', { class: 'btn sm', onClick: () => openEditor(e) }, '수정') : null)
      ))
    }
  }

  function openEditor(expense = null) {
    const date = h('input', { type: 'date', value: expense?.date || toYmd() })
    const category = h('select', {}, ...EXPENSE_CATEGORIES.map((c) => h('option', { value: c, selected: expense?.category === c }, c)))
    const amount = h('input', { type: 'number', value: expense?.amount || '', min: '0', step: '1000' })
    const memo = h('input', { type: 'text', value: expense?.memo || '' })

    modal({
      title: expense ? '지출 수정' : '지출 등록',
      body: h('div', { class: 'inline-fields' }, field('날짜', date), field('항목', category), field('금액', amount), field('메모', memo)),
      actions: [
        expense ? {
          label: '삭제', kind: 'danger', keepOpen: true, onClick: async (close) => {
            if (!await confirmDialog('이 지출을 삭제할까요?', { danger: true, okLabel: '삭제' })) return false
            await repo.remove('expenses', expense.id)
            await load()
            close()
          }
        } : null,
        {
          label: '저장', kind: 'primary', onClick: async () => {
            if (!Number(amount.value)) return toast('금액을 입력해 주세요', 'error')
            await repo.put('expenses', { ...(expense || {}), date: date.value, category: category.value, amount: Number(amount.value), memo: memo.value.trim() })
            await load()
            toast('저장했습니다', 'ok')
          }
        }
      ].filter(Boolean)
    })
  }

  await load()
  return () => {}
}
