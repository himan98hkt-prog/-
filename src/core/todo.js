// 오늘 할 일 — 원장이 매일 반복하는 확인 작업을 한 곳으로 모은다.
//
// 순수 함수다. 화면이 필요한 데이터를 모아서 넘기면 "무엇을, 몇 건, 어디로" 만 돌려준다.
// 판단 기준을 여기 모아 두면 테스트로 고정할 수 있고, 화면은 그리기만 하면 된다.

import { slotsOf } from './schedule.js'
import { dowOf, daysBetween, addDays } from './date.js'
import { PAY_STATUS } from './fees.js'
import { ATT } from './attendance.js'

export const TODO_LEVEL = { INFO: 'info', WARN: 'warn', DANGER: 'danger' }

/** 오늘 수업이 있는 반 (종료된 반 제외) */
export function classesOn(classes = [], ymd) {
  const dow = dowOf(ymd)
  return classes.filter((c) => c.status !== '종료' && slotsOf(c).some((s) => s.dow === dow))
}

/**
 * @param {object} input
 * @param {string} input.today               'YYYY-MM-DD'
 * @param {Array}  input.classes
 * @param {Array}  input.rosterCounts        [{class_id, count}] 오늘 기준 재원 인원
 * @param {Array}  input.attendanceToday     오늘자 출결 레코드
 * @param {Array}  input.payments            이번 달 청구(decorate 된 것)
 * @param {Array}  input.counselLogs         최근 상담일지
 * @param {Array}  input.notices             최근 발송 이력
 * @param {Map}    input.studentById
 * @param {string} [input.lastBackupAt]      마지막 백업 ISO 문자열
 * @param {number} [input.dueDay]            수강료 납부 기준일(기본 10일)
 * @param {number} [input.backupWarnDays]    백업 경고 기준(기본 7일)
 */
export function buildTodos(input) {
  const {
    today,
    classes = [],
    rosterCounts = [],
    attendanceToday = [],
    payments = [],
    counselLogs = [],
    notices = [],
    studentById = new Map(),
    lastBackupAt = null,
    dueDay = 10,
    backupWarnDays = 7
  } = input

  const items = []
  const rosterOf = new Map(rosterCounts.map((r) => [r.class_id, r.count]))
  const checkedByClass = new Map()
  for (const a of attendanceToday) {
    if (a.booked && !a.checked_at) continue // 미래 보강 예약은 체크로 치지 않는다
    checkedByClass.set(a.class_id, (checkedByClass.get(a.class_id) || 0) + 1)
  }

  // 1) 오늘 출결을 아직 안 찍은 반
  const pending = classesOn(classes, today).filter((c) => {
    const roster = rosterOf.get(c.id) ?? 0
    if (!roster) return false
    return (checkedByClass.get(c.id) || 0) < roster
  })
  if (pending.length) {
    items.push({
      id: 'attendance-pending',
      level: TODO_LEVEL.WARN,
      icon: '✅',
      title: `출결 미체크 ${pending.length}개 반`,
      desc: pending.map((c) => c.name).slice(0, 4).join(', ') + (pending.length > 4 ? ` 외 ${pending.length - 4}개` : ''),
      count: pending.length,
      action: { type: 'view', view: 'attendance' },
      payload: { classIds: pending.map((c) => c.id) }
    })
  }

  // 2) 오늘 결석했는데 아직 안내하지 않은 학부모
  const noticedToday = new Set(
    notices.filter((n) => String(n.sent_at || '').slice(0, 10) === today).map((n) => n.student_id)
  )
  const absentees = attendanceToday
    .filter((a) => a.status === ATT.ABSENT && !noticedToday.has(a.student_id))
    .map((a) => studentById.get(a.student_id))
    .filter(Boolean)
  if (absentees.length) {
    items.push({
      id: 'absent-notice',
      level: TODO_LEVEL.DANGER,
      icon: '📮',
      title: `결석 안내 ${absentees.length}명`,
      desc: absentees.map((s) => s.name).slice(0, 5).join(', '),
      count: absentees.length,
      action: { type: 'bulk-notice', templateId: 'absent' },
      payload: { studentIds: absentees.map((s) => s.id) }
    })
  }

  // 3) 납부 기한이 지난 미납 (기준일 이후에만 재촉한다)
  const day = Number(String(today).slice(8, 10))
  const overdue = payments.filter((p) => p.status !== PAY_STATUS.FULL && p.remaining > 0)
  if (overdue.length && day >= dueDay) {
    const sum = overdue.reduce((s, p) => s + p.remaining, 0)
    items.push({
      id: 'unpaid',
      level: TODO_LEVEL.DANGER,
      icon: '💳',
      title: `미납 ${overdue.length}건 · ${sum.toLocaleString('ko-KR')}원`,
      desc: `납부 기준일(${dueDay}일)이 지났습니다. 일괄 안내로 한 번에 보낼 수 있습니다`,
      count: overdue.length,
      action: { type: 'bulk-notice', templateId: 'payment' },
      payload: { studentIds: overdue.map((p) => p.student_id) }
    })
  }

  // 4) 오늘 잡아 둔 보강
  const makeups = attendanceToday.filter((a) => a.status === ATT.MAKEUP)
  if (makeups.length) {
    items.push({
      id: 'makeup',
      level: TODO_LEVEL.INFO,
      icon: '🔁',
      title: `오늘 보강 ${makeups.length}건`,
      desc: makeups.map((m) => studentById.get(m.student_id)?.name).filter(Boolean).join(', '),
      count: makeups.length,
      action: { type: 'view', view: 'attendance' }
    })
  }

  // 5) 후속 조치가 적혀 있는데 일주일 넘게 방치된 상담
  const staleCounsel = counselLogs.filter((c) => {
    if (!c.next_action) return false
    if (c.stage === '등록' || c.stage === '보류') return false
    const d = String(c.created_at || '').slice(0, 10)
    return d && daysBetween(d, today) >= 7
  })
  if (staleCounsel.length) {
    items.push({
      id: 'counsel-followup',
      level: TODO_LEVEL.WARN,
      icon: '📞',
      title: `후속 상담 대기 ${staleCounsel.length}건`,
      desc: staleCounsel.slice(0, 3).map((c) => `${studentById.get(c.student_id)?.name || '신규'} — ${c.next_action}`).join(' / '),
      count: staleCounsel.length,
      action: { type: 'view', view: 'counsel' }
    })
  }

  // 6) 백업 (Lite 는 이 기기에만 자료가 있다)
  const backupDays = lastBackupAt ? daysBetween(String(lastBackupAt).slice(0, 10), today) : null
  if (backupDays === null || backupDays >= backupWarnDays) {
    items.push({
      id: 'backup',
      level: backupDays === null || backupDays >= backupWarnDays * 2 ? TODO_LEVEL.DANGER : TODO_LEVEL.WARN,
      icon: '💾',
      title: backupDays === null ? '백업을 아직 한 번도 하지 않았습니다' : `백업한 지 ${backupDays}일 지났습니다`,
      desc: '자료는 이 기기에만 있습니다. 파일 하나로 내려받아 두세요',
      count: 1,
      action: { type: 'view', view: 'settings' }
    })
  }

  return items
}

/** 다가오는 수업(오늘 남은 시간표) — 헤더 옆 요약용 */
export function upcomingClasses(classes = [], ymd, nowMin = 0, limit = 3) {
  const dow = dowOf(ymd)
  const rows = []
  for (const c of classes) {
    if (c.status === '종료') continue
    for (const s of slotsOf(c)) {
      if (s.dow !== dow || s.endMin < nowMin) continue
      rows.push({ cls: c, slot: s })
    }
  }
  return rows.sort((a, b) => a.slot.startMin - b.slot.startMin).slice(0, limit)
}

/** 이번 주 안에 수강 종료 예정 — 재등록 상담 대상 */
export function renewalTargets(enrollments = [], today, withinDays = 14) {
  const limit = addDays(today, withinDays)
  return enrollments.filter((e) => e.ended_at && e.ended_at >= today && e.ended_at <= limit)
}
