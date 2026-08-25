// 오늘 탭 — 원장이 아침에 열어 보는 첫 화면.
//
// "무엇을 해야 하는가" 만 남기고, 각 항목은 바로 처리할 수 있는 버튼을 단다.
// 통계는 현황 탭에 있다. 여기서는 오늘 움직여야 할 것만 보여 준다.

import { h, clear } from '../dom.js'
import { toYmd, toMonth, WEEKDAYS, dowOf, minToHhmm } from '../../core/date.js'
import { buildTodos, upcomingClasses, renewalTargets } from '../../core/todo.js'
import { overdueDays, formatWon } from '../../core/fees.js'
import { openBulkNotice } from './bulk-notice.js'

export async function render(root, ctx) {
  const { repo } = ctx
  const today = toYmd()
  const month = toMonth(today)
  let cancelled = false

  const head = h('div', { class: 'card' })
  const todoBox = h('div', { class: 'card', style: { marginTop: '12px' } })
  const nextBox = h('div', { class: 'card', style: { marginTop: '12px' } })
  root.append(head, todoBox, nextBox)

  paintHead()
  await load()

  function paintHead() {
    const d = new Date()
    clear(head)
    head.append(
      h('div', { class: 'row' },
        h('div', { class: 'grow' },
          h('div', { class: 'card-title', style: { margin: 0 } }, `${today} (${WEEKDAYS[dowOf(today)]})`),
          h('div', { class: 'small muted' }, '오늘 처리할 일만 모았습니다')),
        h('button', { class: 'btn sm', onClick: () => load() }, '새로고침')),
      h('div', { class: 'small muted', style: { marginTop: '4px' } },
        `${d.getHours()}시 기준`))
  }

  async function load() {
    clear(todoBox)
    todoBox.append(h('div', { class: 'card-title' }, '오늘 할 일'), h('p', { class: 'muted small' }, '확인 중…'))

    const [attendanceToday, payments, counselLogs, notices] = await Promise.all([
      repo.attendanceOfRange(today, today),
      repo.paymentsOfMonth(month),
      repo.counselRecent(200),
      repo.db.notices.orderBy('sent_at').reverse().limit(200).toArray()
    ])
    if (cancelled) return

    const classes = repo.cache.classes
    const rosterCounts = classes.map((c) => ({ class_id: c.id, count: repo.rosterOf(c.id, today).length }))
    const items = buildTodos({
      today,
      classes,
      rosterCounts,
      attendanceToday,
      payments,
      counselLogs,
      notices,
      studentById: repo.cache.studentById,
      lastBackupAt: repo.getSetting('lastBackupAt'),
      dueDay: repo.policy().dueDay
    })

    const amounts = Object.fromEntries(payments.map((p) => [p.student_id, p.remaining]))

    clear(todoBox)
    todoBox.append(h('div', { class: 'row' },
      h('div', { class: 'card-title', style: { margin: 0 } }, '오늘 할 일'),
      h('span', { class: 'right badge' }, `${items.length}건`)))

    if (!items.length) {
      todoBox.append(h('div', { class: 'todo-empty' }, '오늘 처리할 일이 없습니다 👍'))
    }

    for (const item of items) {
      todoBox.append(h('div', { class: `todo-item ${item.level}` },
        h('div', { class: 'todo-ico' }, item.icon),
        h('div', { class: 'grow' },
          h('b', {}, item.title),
          h('div', { class: 'small muted' }, item.desc || '')),
        actionButton(item, amounts)))
    }

    paintNext(payments)
  }

  function actionButton(item, amounts) {
    if (item.action?.type === 'bulk-notice') {
      return h('button', {
        class: 'btn sm primary',
        onClick: () => openBulkNotice({
          studentIds: item.payload.studentIds,
          templateId: item.action.templateId,
          month,
          amounts: item.action.templateId === 'payment' ? amounts : {},
          title: item.title
        })
      }, '일괄 안내')
    }
    if (item.action?.type === 'view') {
      return h('button', { class: 'btn sm', onClick: () => { location.hash = item.action.view } }, '바로가기')
    }
    return null
  }

  function paintNext(payments) {
    const now = new Date()
    const nowMin = now.getHours() * 60 + now.getMinutes()
    const rows = upcomingClasses(repo.cache.classes, today, nowMin, 5)
    const renewals = renewalTargets(repo.cache.enrollments, today)
    const late = payments.filter((p) => p.remaining > 0 && overdueDays(month, today, repo.policy().dueDay) > 0)

    clear(nextBox)
    nextBox.append(h('div', { class: 'card-title' }, '남은 수업'))
    if (!rows.length) nextBox.append(h('p', { class: 'muted small' }, '오늘 남은 수업이 없습니다'))
    for (const { cls, slot } of rows) {
      const teacher = repo.cache.userById.get(cls.teacher_id)
      nextBox.append(h('div', { class: 'row', style: { padding: '8px 0', borderBottom: '1px solid var(--line)' } },
        h('span', { class: 'badge brand' }, `${minToHhmm(slot.startMin)}`),
        h('span', { class: 'grow' }, cls.name,
          h('span', { class: 'small muted' }, ` · ${repo.rosterOf(cls.id, today).length}명${teacher ? ` · ${teacher.name}` : ''}${cls.room ? ` · ${cls.room}` : ''}`)),
        h('button', { class: 'btn sm', onClick: () => { location.hash = 'attendance' } }, '출결')))
    }

    const notes = []
    if (late.length) notes.push(`연체 ${late.length}건 · ${formatWon(late.reduce((s, p) => s + p.remaining, 0))}`)
    if (renewals.length) notes.push(`2주 내 수강 종료 ${renewals.length}건`)
    if (notes.length) {
      nextBox.append(h('div', { class: 'small muted', style: { marginTop: '10px' } }, notes.join(' · ')))
    }
  }

  return () => { cancelled = true }
}
