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
import { setupSteps, setupProgress } from '../../core/onboarding.js'

export async function render(root, ctx) {
  const { repo } = ctx
  const today = toYmd()
  const month = toMonth(today)
  let cancelled = false

  const hero = h('div', { class: 'hero' })
  const setupBox = h('div', {})
  const statBox = h('div', { class: 'grid cols4 stats' })
  const todoBox = h('div', { class: 'card todo-card' })
  const nextBox = h('div', { class: 'card' })

  root.append(
    hero,
    setupBox,
    quickActions(),
    statBox,
    h('div', { class: 'section-head' },
      h('h2', {}, '오늘 할 일'),
      h('span', { class: 'desc' }, '오른쪽 버튼을 누르면 바로 처리됩니다'),
      h('span', { class: 'right' }),
      h('button', { class: 'btn sm ghost', type: 'button', onClick: () => load() }, icon('refresh', { size: 16 }), '새로고침')),
    todoBox,
    h('div', { class: 'section-head' }, h('h2', {}, '남은 수업'), h('span', { class: 'desc' }, '오늘 남은 시간표')),
    nextBox
  )

  paintHero()
  await load()
  maybeShowCoach()

  /** 맨 위 인사 — 시간대에 맞는 말과 오늘 날짜, 그리고 오늘의 한 줄 요약 */
  function paintHero(summary = '') {
    const hour = new Date().getHours()
    const hello = hour < 11 ? '좋은 아침입니다' : hour < 17 ? '오늘도 수고 많으십니다' : '오늘 하루도 고생하셨습니다'
    const user = ctx.user
    clear(hero)
    hero.append(
      h('div', { class: 'hero-date' }, `${Number(today.slice(5, 7))}월 ${Number(today.slice(8, 10))}일 ${WEEKDAYS[dowOf(today)]}요일`),
      h('h1', {}, hello, user?.name && user.name !== '원장' ? `, ${user.name}님` : ', 원장님'),
      h('p', { class: 'hero-sum' }, summary || '오늘 할 일을 확인하고 있습니다…'))
  }

  /** 가장 자주 하는 네 가지 — 메뉴 이름을 몰라도 그림과 말로 찾아 누를 수 있게 */
  function quickActions() {
    const tile = (ico, label, sub, onClick) => h('button', { class: 'quick', type: 'button', onClick },
      h('span', { class: 'ico' }, icon(ico, { size: 24 })),
      h('b', {}, label),
      h('span', {}, sub))
    const go = (view) => () => { location.hash = view }
    return h('div', { class: 'quick-grid' },
      tile('checkCircle', '출석 체크', '이름만 누르면 끝', go('attendance')),
      ctx.can('students:write') ? tile('users', '원생 등록', '새 학생 추가', go('students')) : null,
      ctx.can('payments:read') ? tile('won', '수강료', '청구 · 받은 돈 기록', go('payments')) : null,
      tile('send', '문자 보내기', '학부모 안내 문구', () => openBulkNotice({
        studentIds: repo.searchStudents('', { status: '재원' }).map((s) => s.id),
        templateId: 'lesson', month, title: '학부모 안내 문자'
      })))
  }

  /** 시작 가이드 — 네 가지를 끝낼 때까지 "다음에 할 일" 을 하나씩 짚어 준다 */
  async function paintSetup() {
    clear(setupBox)
    if (repo.getSetting('demoMode') || repo.getSetting('setupDone') || !ctx.can('settings:read')) return
    const [att, pay] = await Promise.all([repo.db.attendance.limit(1).count(), repo.db.payments.limit(1).count()])
    if (cancelled) return
    const steps = setupSteps({
      classes: repo.cache.classes.length,
      students: repo.cache.students.length,
      hasAttendance: att > 0,
      hasPayments: pay > 0
    })
    const prog = setupProgress(steps)
    if (prog.complete) {
      await repo.setSetting('setupDone', true)
      return
    }

    setupBox.append(h('div', { class: 'card setup' },
      h('div', { class: 'setup-head' },
        h('div', { class: 'grow' },
          h('b', {}, prog.done ? `잘하고 계십니다 — ${prog.total}가지 중 ${prog.done}가지 완료` : '처음이시죠? 이 네 가지만 하면 준비가 끝납니다'),
          h('div', { class: 'progressbar', style: { marginTop: '10px' } }, h('div', { style: { width: `${(prog.done / prog.total) * 100}%` } }))),
        h('button', {
          class: 'linkbtn', type: 'button',
          onClick: async () => { await repo.setSetting('setupDone', true); clear(setupBox) }
        }, '안내 그만 보기')),
      h('ol', { class: 'setup-steps' }, ...steps.map((st, i) => {
        const isNext = prog.next?.id === st.id
        return h('li', { class: `${st.done ? 'done' : ''} ${isNext ? 'next' : ''}`, dataset: { step: st.id } },
          h('span', { class: 'num' }, st.done ? icon('check', { size: 16, stroke: 2.4 }) : String(i + 1)),
          h('span', { class: 'grow' }, h('b', {}, st.title), h('span', { class: 'small muted' }, st.done ? '완료했습니다' : st.desc)),
          isNext ? h('button', { class: 'btn primary', type: 'button', onClick: () => { location.hash = st.view } }, st.cta) : null)
      }))))
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
    paintHero(summaryLine({ attendanceToday, payments, classes, items }))
    paintSetup()

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
    return h('div', { class: `stat ico ${tone}` },
      h('span', { class: 'stat-ico' }, icon(iconName, { size: 19 })),
      h('div', { class: 'grow' },
        h('div', { class: 'l' }, label),
        h('div', { class: 'v' }, value)))
  }

  /** 인사말 아래 한 줄 — 숫자를 읽지 않아도 오늘 상황이 문장으로 보이게 */
  function summaryLine({ attendanceToday, payments, classes, items }) {
    const todayClasses = classes.filter((c) => c.status !== '종료' &&
      (c.schedule || []).some((s) => Number(s.dow) === dowOf(today)))
    if (!repo.cache.students.length) return '아직 등록된 원생이 없습니다. 아래 안내를 따라 시작해 보세요.'
    const parts = [todayClasses.length ? `오늘 수업은 ${todayClasses.length}개 반입니다` : '오늘은 수업이 없는 날입니다']
    parts.push(items.length ? `처리할 일이 ${items.length}건 있습니다` : '처리할 일은 모두 끝났습니다')
    return `${parts.join('. ')}.`
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
