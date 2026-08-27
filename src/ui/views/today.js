// 오늘 탭 — 원장이 아침에 열어 보는 첫 화면.
//
// 화면을 열자마자 "지금 뭘 해야 하는지" 가 보여야 한다. 통계는 현황 탭에 있다.
// 여기서는 오늘 움직여야 할 것과, 오늘 남은 수업만 남긴다.

import { h, clear } from '../dom.js'
import { icon } from '../icons.js'
import { toYmd, toMonth, WEEKDAYS, dowOf, minToHhmm } from '../../core/date.js'
import { buildTodos, upcomingClasses, renewalTargets } from '../../core/todo.js'
import { overdueDays, formatWon } from '../../core/fees.js'
import { openBulkNotice } from './bulk-notice.js'
import { maybeShowCoach } from '../coach.js'

export async function render(root, ctx) {
  const { repo } = ctx
  const today = toYmd()
  const month = toMonth(today)
  let cancelled = false

  const head = h('div', {})
  const statBox = h('div', { class: 'grid cols4', style: { marginBottom: '4px' } })
  const todoBox = h('div', { class: 'card' })
  const nextBox = h('div', { class: 'card' })

  root.append(
    head,
    statBox,
    h('div', { class: 'section-head' },
      h('h2', {}, '오늘 할 일'),
      h('span', { class: 'desc' }, '누르면 바로 처리됩니다'),
      h('span', { class: 'right' }),
      h('button', { class: 'btn sm ghost', onClick: () => load() }, icon('refresh', { size: 16 }), '새로고침')),
    todoBox,
    h('div', { class: 'section-head' }, h('h2', {}, '남은 수업'), h('span', { class: 'desc' }, '오늘 남은 시간표')),
    nextBox
  )

  paintHead()
  await load()
  maybeShowCoach()

  function paintHead() {
    const hour = new Date().getHours()
    const hello = hour < 11 ? '좋은 아침입니다' : hour < 17 ? '오늘도 수고 많으십니다' : '오늘 하루 마무리해요'
    clear(head)
    head.append(h('div', { class: 'greeting' },
      h('h1', {}, hello),
      h('span', { class: 'date' }, `${today.replaceAll('-', '. ')} ${WEEKDAYS[dowOf(today)]}요일`)))
  }

  async function load() {
    clear(todoBox)
    todoBox.append(h('p', { class: 'muted small' }, '확인 중…'))

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

    paintStats({ attendanceToday, payments, classes })

    clear(todoBox)
    if (!items.length) {
      todoBox.append(h('div', { class: 'todo-empty' },
        h('div', { class: 'empty' },
          h('div', { class: 'emoji' }, icon('checkCircle', { size: 26 })),
          h('b', {}, '오늘 처리할 일이 없습니다'),
          h('p', {}, '출결도 안내도 모두 끝났습니다. 편안한 하루 되세요.'))))
    }

    for (const item of items) {
      todoBox.append(h('div', { class: `todo-item ${item.level}` },
        h('div', { class: 'todo-ico' }, icon(item.icon, { size: 20 })),
        h('div', { class: 'grow' },
          h('b', {}, item.title),
          h('div', { class: 'small muted' }, item.desc || '')),
        actionButton(item, amounts)))
    }

    paintNext(payments)
  }

  /** 오늘의 숫자 — 판단에 바로 쓰이는 네 개만 */
  function paintStats({ attendanceToday, payments, classes }) {
    const todayClasses = classes.filter((c) => c.status !== '종료' &&
      (c.schedule || []).some((s) => Number(s.dow) === dowOf(today)))
    const checked = attendanceToday.filter((a) => a.checked_at).length
    const absent = attendanceToday.filter((a) => a.status === '결석').length
    const unpaid = payments.filter((p) => p.remaining > 0)
    const unpaidSum = unpaid.reduce((s, p) => s + p.remaining, 0)

    clear(statBox)
    statBox.append(
      stat('오늘 수업', `${todayClasses.length}개 반`, 'calendar'),
      stat('출결 체크', `${checked}명`, 'checkCircle'),
      stat('오늘 결석', `${absent}명`, 'warning', absent ? 'danger' : ''),
      stat('이달 미납', unpaid.length ? formatWon(unpaidSum) : '없음', 'won', unpaid.length ? 'warn' : '')
    )
  }

  function stat(label, value, iconName, tone = '') {
    const color = tone === 'danger' ? 'var(--danger)' : tone === 'warn' ? 'var(--warn)' : ''
    return h('div', { class: 'stat' },
      h('div', { class: 'row', style: { gap: '6px', color: 'var(--ink-3)' } },
        icon(iconName, { size: 15 }), h('span', { class: 'l', style: { marginTop: 0 } }, label)),
      h('div', { class: 'v', style: color ? { color } : {} }, value))
  }

  function actionButton(item, amounts) {
    if (item.action?.type === 'bulk-notice') {
      return h('button', {
        class: 'btn primary',
        onClick: () => openBulkNotice({
          studentIds: item.payload.studentIds,
          templateId: item.action.templateId,
          month,
          amounts: item.action.templateId === 'payment' ? amounts : {},
          title: item.title
        })
      }, icon('send', { size: 16 }), '일괄 안내')
    }
    if (item.action?.type === 'view') {
      return h('button', {
        class: 'btn', onClick: () => { location.hash = item.action.view }
      }, '바로가기', icon('chevronRight', { size: 16 }))
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
    nextBox.classList.add('flush')
    if (!rows.length) {
      nextBox.append(h('div', { class: 'empty' },
        h('div', { class: 'emoji' }, icon('clock', { size: 26 })),
        h('b', {}, '오늘 남은 수업이 없습니다'),
        h('p', {}, '시간표는 시간표 탭에서 바꿀 수 있습니다.')))
    }
    for (const { cls, slot } of rows) {
      const teacher = repo.cache.userById.get(cls.teacher_id)
      const subject = repo.cache.subjectById.get(cls.subject_id)
      nextBox.append(h('div', { class: 'list-row link', onClick: () => { location.hash = 'attendance' } },
        h('span', { class: 'badge brand num', style: { minWidth: '54px', justifyContent: 'center' } }, minToHhmm(slot.startMin)),
        h('span', { class: 'grow truncate' },
          h('b', {}, cls.name),
          h('div', { class: 'small muted truncate' },
            [`${repo.rosterOf(cls.id, today).length}명`, subject?.name, teacher?.name, cls.room].filter(Boolean).join(' · '))),
        h('span', { class: 'btn sm soft' }, '출결 체크')))
    }

    const notes = []
    if (late.length) notes.push(`연체 ${late.length}건 · ${formatWon(late.reduce((s, p) => s + p.remaining, 0))}`)
    if (renewals.length) notes.push(`2주 안에 수강이 끝나는 원생 ${renewals.length}명`)
    if (notes.length) {
      nextBox.append(h('div', { class: 'list-row', style: { color: 'var(--ink-3)', fontSize: '.86em' } },
        icon('warning', { size: 16 }), h('span', {}, notes.join(' · '))))
    }
  }

  return () => { cancelled = true }
}
