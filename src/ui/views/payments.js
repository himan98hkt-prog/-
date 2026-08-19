// 수납 탭 — 월별 현황 / 미납 필터 / 분할납부 계산기 / 월말 마감 도우미

import { h, clear, toast, modal, field, debounce, confirmDialog } from '../dom.js'
import { formatWon, splitInstallments, decorate, settleMonth, PAY_STATUS } from '../../core/fees.js'
import { toMonth, toYmd, addMonths } from '../../core/date.js'
import { openNoticeModal } from './notice-modal.js'

export async function render(root, ctx) {
  const { repo } = ctx
  const canWrite = ctx.can('payments:write')
  let month = toMonth(toYmd())
  let filter = '전체'
  let query = ''
  let rows = []

  const statBox = h('div', { class: 'grid cols4' })
  const tbody = h('tbody')
  const filterBar = h('div', { class: 'row wrap' })

  const monthInput = h('input', { type: 'month', value: month, style: { maxWidth: '160px' }, onChange: (e) => { month = e.target.value; load() } })

  const head = h('div', { class: 'card' },
    h('div', { class: 'row wrap' },
      h('button', { class: 'btn sm', onClick: () => { month = addMonths(month, -1); monthInput.value = month; load() } }, '‹'),
      monthInput,
      h('button', { class: 'btn sm', onClick: () => { month = addMonths(month, 1); monthInput.value = month; load() } }, '›'),
      h('input', { type: 'search', placeholder: '원생 검색', style: { maxWidth: '200px' }, onInput: debounce((e) => { query = e.target.value; paint() }, 200) }),
      canWrite ? h('button', { class: 'btn right', onClick: generateBills }, '이번 달 청구 생성') : null,
      canWrite ? h('button', { class: 'btn primary', onClick: closeMonth }, '월말 마감') : null
    ),
    h('div', { style: { marginTop: '10px' } }, filterBar)
  )

  root.append(head,
    h('div', { style: { marginTop: '12px' } }, statBox),
    h('div', { class: 'card', style: { marginTop: '12px' } },
      h('div', { class: 'scroll-x' },
        h('table', {},
          h('thead', {}, h('tr', {},
            h('th', {}, '원생'), h('th', {}, '청구'), h('th', {}, '납부'), h('th', {}, '잔액'), h('th', {}, '상태'), h('th', {}, '')
          )),
          tbody
        )
      )
    )
  )

  async function load() {
    rows = await repo.paymentsOfMonth(month)
    const expenses = await repo.expensesOfMonth(month)
    const s = settleMonth(rows, expenses)
    clear(statBox)
    statBox.append(
      stat('청구 합계', formatWon(s.billed)),
      stat('수납 합계', formatWon(s.collected)),
      stat('미수금', formatWon(s.outstanding), s.outstanding ? 'danger' : ''),
      stat('수납률', `${s.collectRate}%`)
    )
    paintFilters(s)
    paint()
  }

  function paintFilters(s) {
    clear(filterBar)
    const options = [['전체', rows.length], [PAY_STATUS.UNPAID, s.unpaidCount], [PAY_STATUS.PARTIAL, s.partialCount], [PAY_STATUS.FULL, rows.length - s.unpaidCount - s.partialCount]]
    for (const [name, n] of options) {
      filterBar.append(h('button', {
        class: `chip ${filter === name ? 'active' : ''}`,
        onClick: () => { filter = name; paintFilters(s); paint() }
      }, `${name} ${n}`))
    }
  }

  function paint() {
    const q = query.trim().toLowerCase()
    clear(tbody)
    const filtered = rows.filter((p) => {
      if (filter !== '전체' && p.status !== filter) return false
      if (!q) return true
      const st = repo.cache.studentById.get(p.student_id)
      return `${st?.name || ''} ${st?.school || ''}`.toLowerCase().includes(q)
    }).sort((a, b) => {
      const na = repo.cache.studentById.get(a.student_id)?.name || ''
      const nb = repo.cache.studentById.get(b.student_id)?.name || ''
      return na.localeCompare(nb, 'ko')
    })

    if (!filtered.length) {
      tbody.append(h('tr', {}, h('td', { colSpan: 6, class: 'muted' }, '해당 조건의 수납 내역이 없습니다. "이번 달 청구 생성"을 눌러 보세요.')))
      return
    }
    for (const p of filtered) {
      const st = repo.cache.studentById.get(p.student_id)
      tbody.append(h('tr', {},
        h('td', {}, h('b', {}, st?.name || '(삭제된 원생)'), h('div', { class: 'small muted' }, st?.grade || '')),
        h('td', {}, formatWon(p.amount)),
        h('td', {}, formatWon(p.paid)),
        h('td', {}, p.remaining ? h('span', { style: { color: 'var(--danger)' } }, formatWon(p.remaining)) : '-'),
        h('td', {}, h('span', { class: `badge ${p.status === '완납' ? 'ok' : p.status === '부분' ? 'warn' : 'danger'}` }, p.status)),
        h('td', { class: 'right' },
          h('div', { class: 'row', style: { gap: '4px', justifyContent: 'flex-end' } },
            p.status !== '완납' && st ? h('button', { class: 'btn sm', onClick: () => openNoticeModal({ student: st, templateId: 'payment', extra: { month, amount: p.remaining } }) }, '안내') : null,
            canWrite ? h('button', { class: 'btn sm', onClick: () => openEditor(p, st) }, '수정') : null
          ))
      ))
    }
  }

  function stat(label, value, kind = '') {
    return h('div', { class: 'stat' },
      h('div', { class: 'v', style: kind === 'danger' ? { color: 'var(--danger)' } : {} }, value),
      h('div', { class: 'l' }, label))
  }

  async function generateBills() {
    const created = await repo.generateMonthlyBills(month)
    await load()
    toast(created.length ? `${created.length}건의 청구를 생성했습니다` : '새로 만들 청구가 없습니다', created.length ? 'ok' : 'info')
  }

  async function closeMonth() {
    const expenses = await repo.expensesOfMonth(month)
    const s = settleMonth(rows, expenses)
    const unpaid = rows.filter((p) => p.status !== PAY_STATUS.FULL)
    modal({
      title: `${month} 월말 마감`,
      body: h('div', {},
        h('div', { class: 'grid cols2' },
          stat('수납', formatWon(s.collected)), stat('지출', formatWon(s.expense)),
          stat('순이익', formatWon(s.net)), stat('미수금', formatWon(s.outstanding))
        ),
        h('div', { class: 'card', style: { marginTop: '12px' } },
          h('div', { class: 'card-title' }, `미납 ${unpaid.length}명`),
          unpaid.length
            ? h('div', { class: 'row wrap', style: { gap: '6px' } },
              ...unpaid.slice(0, 40).map((p) => h('span', { class: 'badge danger' }, repo.cache.studentById.get(p.student_id)?.name || '?')))
            : h('p', { class: 'muted small' }, '미납자가 없습니다 👍')
        ),
        h('p', { class: 'small muted' }, '마감하면 이 달의 현황 통계가 다시 계산되어 저장됩니다.')
      ),
      actions: [
        {
          label: '마감하고 통계 갱신', kind: 'primary', onClick: async () => {
            await repo.recomputeMonth(month)
            await repo.setSetting('lastClosedMonth', month)
            toast(`${month} 마감 완료`, 'ok')
          }
        }
      ]
    })
  }

  function openEditor(payment, student) {
    const amount = h('input', { type: 'number', value: payment.amount, min: '0', step: '1000' })
    const method = h('select', {}, ...['계좌이체', '카드', '현금', '기타'].map((m) => h('option', { value: m, selected: payment.method === m }, m)))
    const paidAt = h('input', { type: 'date', value: payment.paid_at || '' })
    const instBox = h('div')
    let installments = (payment.installments || []).slice()

    const paintInst = () => {
      clear(instBox)
      if (!installments.length) {
        instBox.append(h('p', { class: 'small muted' }, '일시납입니다. 아래 계산기로 분할납부를 만들 수 있습니다.'))
        return
      }
      for (const it of installments) {
        instBox.append(h('div', { class: 'row', style: { marginBottom: '6px' } },
          h('span', { class: 'badge' }, `${it.seq}회`),
          h('span', { class: 'grow' }, formatWon(it.amount)),
          h('input', { type: 'date', value: it.due_date || '', style: { maxWidth: '150px' }, onChange: (e) => { it.due_date = e.target.value } }),
          h('label', { class: 'row small', style: { gap: '4px' } },
            h('input', {
              type: 'checkbox', checked: !!it.paid_at, style: { width: 'auto' },
              onChange: (e) => { it.paid_at = e.target.checked ? (it.due_date || toYmd()) : null }
            }), '납부')
        ))
      }
    }
    paintInst()

    const count = h('input', { type: 'number', value: '3', min: '1', max: '12', style: { maxWidth: '90px' } })

    modal({
      title: `${student?.name || ''} · ${payment.month} 수납`,
      body: h('div', {},
        h('div', { class: 'inline-fields' }, field('청구 금액', amount), field('납부 방법', method), field('완납일(일시납)', paidAt)),
        h('div', { class: 'card' },
          h('div', { class: 'card-title' }, '분할납부 계산기'),
          h('div', { class: 'row' }, count, h('span', { class: 'small muted' }, '회로 나누기'),
            h('button', {
              class: 'btn sm', onClick: () => {
                const n = Math.max(1, Math.min(12, Number(count.value) || 1))
                const start = toYmd()
                installments = splitInstallments(Number(amount.value) || 0, n, {
                  dueDates: Array.from({ length: n }, (_, i) => `${addMonths(payment.month, i)}-${start.slice(8)}`)
                })
                paintInst()
              }
            }, '계산'),
            installments.length ? h('button', { class: 'btn sm', onClick: () => { installments = []; paintInst() } }, '초기화') : null
          ),
          h('div', { style: { marginTop: '10px' } }, instBox)
        )
      ),
      actions: [
        {
          label: '삭제', kind: 'danger', keepOpen: true, onClick: async (close) => {
            if (!await confirmDialog('이 수납 기록을 삭제할까요?', { danger: true, okLabel: '삭제' })) return false
            await repo.remove('payments', payment.id)
            await load()
            close()
          }
        },
        {
          label: '저장', kind: 'primary', onClick: async () => {
            const next = decorate({
              ...payment,
              amount: Number(amount.value) || 0,
              method: method.value,
              paid_at: paidAt.value || null,
              installments
            })
            await repo.savePayment(next)
            await load()
            toast('저장했습니다', 'ok')
          }
        }
      ]
    })
  }

  await load()
  const off = repo.on('payments', () => {})
  return () => off()
}
