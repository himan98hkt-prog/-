// 출결 탭 — 날짜 + 반 선택 → 원생 터치 체크. 과목 색상 기반 보드(구 '건반 시각화' 대체).

import { h, clear, toast, modal, field } from '../dom.js'
import { icon } from '../icons.js'
import { ATT, ATT_LIST, summarize } from '../../core/attendance.js'
import { toYmd, addDays, WEEKDAYS, dowOf } from '../../core/date.js'
import { visibleClasses } from '../../core/perm.js'
import { classesOnDow } from '../../core/schedule.js'
import { openBulkNotice } from './bulk-notice.js'
import { printTable } from '../print.js'
import { monthRange, toMonth } from '../../core/date.js'
import { ATT_LABELS, monthlyRegister } from '../../core/register.js'

export async function render(root, ctx) {
  const { repo, user } = ctx
  const canWrite = ctx.can('attendance:write')
  let date = toYmd()
  let classId = null
  let onlyToday = true

  const classBar = h('div', { class: 'row wrap', style: { gap: '6px' } })
  const board = h('div', { class: 'att-board' })
  const summaryBox = h('div', { class: 'row wrap', style: { gap: '8px', marginBottom: '10px' } })

  const dateInput = h('input', {
    type: 'date', value: date, class: 'hidden',
    onChange: (e) => { date = e.target.value || toYmd(); paintDate(); renderClasses(); load() }
  })
  const dateLabel = h('button', {
    class: 'btn', style: { minWidth: '190px' },
    onClick: () => { dateInput.showPicker ? dateInput.showPicker() : dateInput.click() }
  })
  const paintDate = () => {
    const [, m, d] = date.split('-')
    clear(dateLabel)
    dateLabel.append(
      icon('calendar', { size: 17 }),
      h('b', {}, `${Number(m)}월 ${Number(d)}일`),
      h('span', { class: 'muted' }, `${WEEKDAYS[dowOf(date)]}요일`),
      date === toYmd() ? h('span', { class: 'badge brand' }, '오늘') : null
    )
    dateInput.value = date
  }
  paintDate()

  const shift = (n) => { date = addDays(date, n); paintDate(); renderClasses(); load() }

  const head = h('div', { class: 'card' },
    h('div', { class: 'row datebar' },
      h('button', { class: 'btn nav-prev', onClick: () => shift(-1), title: '어제' },
        icon('chevronLeft', { size: 17 }), h('span', { class: 'lbl' }, '어제')),
      dateLabel, dateInput,
      h('button', { class: 'btn nav-next', onClick: () => shift(1), title: '내일' },
        h('span', { class: 'lbl' }, '내일'), icon('chevronRight', { size: 17 }))),
    h('div', { class: 'row wrap', style: { marginTop: '10px' } },
      h('label', { class: 'row small right', style: { gap: '6px', cursor: 'pointer' } },
        h('input', {
          type: 'checkbox', checked: onlyToday, style: { width: 'auto' },
          onChange: (e) => { onlyToday = e.target.checked; renderClasses() }
        }), h('span', { class: 'muted' }, '이 요일 수업만 보기')
      )
    ),
    h('div', { style: { marginTop: '12px' } }, classBar),
    h('div', { class: 'row wrap', style: { marginTop: '10px' } },
      canWrite ? h('button', { class: 'btn sm', onClick: notifyAbsentees }, icon('send', { size: 15 }), '오늘 결석자 일괄 안내') : null,
      h('button', { class: 'btn sm', onClick: printRegister }, icon('printer', { size: 15 }), '월간 출석부 인쇄')
    )
  )

  const undoBox = h('div', {})

  root.append(
    h('div', { class: 'page-head' },
      h('h1', {}, '출결'),
      h('p', {}, '반을 고르고 학생 이름을 누르면 출석 → 지각 → 결석 순서로 바뀝니다.')),
    head,
    h('div', { class: 'card' }, summaryBox, undoBox, board))

  function myClasses() {
    const all = visibleClasses(user, repo.cache.classes).filter((c) => c.status !== '종료')
    return onlyToday ? classesOnDow(all, dowOf(date)) : all
  }

  function renderClasses() {
    const list = myClasses()
    if (!list.some((c) => c.id === classId)) classId = list[0]?.id || null
    clear(classBar)
    if (!list.length) {
      classBar.append(h('span', { class: 'muted small' }, onlyToday ? '이 요일에 배정된 반이 없습니다. 체크를 해제하면 전체 반이 보입니다.' : '먼저 설정 > 반 관리에서 반을 만들어 주세요.'))
      return
    }
    for (const c of list) {
      const subject = repo.cache.subjectById.get(c.subject_id)
      classBar.append(h('button', {
        class: `chip ${c.id === classId ? 'active' : ''}`,
        onClick: () => { classId = c.id; renderClasses(); load() }
      },
        h('span', { style: { width: '8px', height: '8px', borderRadius: '50%', background: subject?.color || 'var(--brand)', display: 'inline-block' } }),
        `${c.name}`,
        h('span', { class: 'muted' }, ` ${repo.enrolledCount(c.id)}명`)
      ))
    }
  }

  /** 방금 한 일을 한 번에 되돌린다 — 잘못 눌렀을 때 당황하지 않도록 */
  function showUndo(message, undo) {
    clear(undoBox)
    const bar = h('div', { class: 'undobar' },
      icon('refresh', { size: 17 }),
      h('span', { class: 'grow' }, message),
      h('button', {
        class: 'btn sm', onClick: async () => { clear(undoBox); await undo() }
      }, '되돌리기'),
      h('button', { class: 'icon-btn', onClick: () => clear(undoBox), 'aria-label': '닫기' }, '×'))
    undoBox.append(bar)
    setTimeout(() => { if (undoBox.contains(bar)) clear(undoBox) }, 15000)
  }

  async function notifyAbsentees() {
    const records = await repo.attendanceOfRange(date, date)
    const ids = [...new Set(records.filter((r) => r.status === ATT.ABSENT).map((r) => r.student_id))]
    if (!ids.length) return toast('오늘 결석 처리된 원생이 없습니다 👍')
    openBulkNotice({ studentIds: ids, templateId: 'absent', title: `${date} 결석 안내 (${ids.length}명)` })
  }

  /** 월간 출석부 — 세무·학부모 문의 대응용으로 한 달치를 한 장에 뽑는다 */
  async function printRegister() {
    if (!classId) return toast('반을 먼저 선택해 주세요', 'error')
    const month = toMonth(date)
    const { from, to } = monthRange(month)
    const cls = repo.cache.classById.get(classId)
    const roster = repo.rosterOf(classId, to)
    const records = await repo.attendanceOfClassMonth(classId, month)
    const table = monthlyRegister({ month, roster, records })
    printTable({
      title: `${month} 출석부 — ${cls?.name || ''}`,
      subtitle: `대상 ${roster.length}명 · ${from} ~ ${to} · 표기 ${Object.entries(ATT_LABELS).map(([k, v]) => `${v}=${k}`).join(' ')}`,
      headers: table.headers,
      rows: table.rows
    })
  }

  async function load() {
    clear(board)
    clear(summaryBox)
    if (!classId) return
    const roster = repo.rosterOf(classId, date)
    const records = await repo.attendanceOfClassDate(classId, date)
    const byStudent = new Map(records.map((r) => [r.student_id, r]))
    const cls = repo.cache.classById.get(classId)
    const subject = repo.cache.subjectById.get(cls?.subject_id)

    if (!roster.length) {
      board.append(h('div', { class: 'empty' },
        h('div', { class: 'emoji' }, icon('users', { size: 26 })),
        h('b', {}, '이 반에 등록된 원생이 없습니다'),
        h('p', {}, '원생 탭에서 학생을 등록하고 반을 배정해 주세요.'),
        h('button', { class: 'btn primary', onClick: () => { location.hash = 'students' } }, '원생 탭으로 가기')))
      return
    }

    const cells = new Map()
    for (const s of roster) {
      const rec = byStudent.get(s.id)
      const cell = h('div', {
        class: 'att-cell',
        dataset: { status: rec?.status || '' },
        title: '누르면 출석 → 지각 → 결석 순으로 바뀝니다',
        onClick: () => canWrite ? quickToggle(s, cells.get(s.id)) : toast('출결 수정 권한이 없습니다'),
        oncontextmenu: (e) => { e.preventDefault(); if (canWrite) openDetail(s, cells.get(s.id)) }
      },
        h('div', { class: 'row', style: { gap: '6px' } },
          h('span', {
            style: {
              width: '8px', height: '8px', borderRadius: '50%', flex: 'none',
              background: subject?.color || 'var(--brand)'
            }
          }),
          h('div', { class: 'nm grow truncate' }, s.name),
          h('button', {
            class: 'icon-btn', style: { width: '30px', height: '30px' }, title: '자세히 (사유·보강)',
            onClick: (e) => { e.stopPropagation(); openDetail(s, cells.get(s.id)) }
          }, icon('more', { size: 16 }))),
        h('div', { class: 'st' }, rec ? `${rec.status}${rec.reason_tag ? ` · ${rec.reason_tag}` : ''}` : '미체크')
      )
      cell.__student = s
      cell.__record = rec || null
      cells.set(s.id, cell)
      board.append(cell)
    }
    renderSummary()

    function renderSummary() {
      const recs = [...cells.values()].map((c) => c.__record).filter(Boolean)
      const sum = summarize(recs)
      clear(summaryBox)
      summaryBox.append(
        h('span', { class: 'badge brand' }, `총 ${roster.length}명`),
        h('span', { class: 'badge ok' }, `출석 ${sum.counts[ATT.PRESENT]}`),
        h('span', { class: 'badge warn' }, `지각 ${sum.counts[ATT.LATE]}`),
        h('span', { class: 'badge danger' }, `결석 ${sum.counts[ATT.ABSENT]}`),
        h('span', { class: 'badge' }, `미체크 ${roster.length - recs.length}`),
        canWrite ? h('button', { class: 'btn primary right', onClick: markAllPresent }, icon('checkCircle', { size: 17 }), '전체 출석') : null
      )
    }

    async function markAllPresent() {
      const rows = []
      for (const [sid, cell] of cells) {
        if (cell.__record) continue
        rows.push({
          student_id: sid, class_id: classId, date, status: ATT.PRESENT,
          reason_tag: null, checked_by: user?.id || null
        })
      }
      if (!rows.length) return toast('이미 모두 체크되었습니다')
      const saved = await repo.markAttendanceBulk(rows)
      for (const r of saved) applyToCell(cells.get(r.student_id), r)
      renderSummary()
      toast(`${saved.length}명 출석 처리했습니다`, 'ok')
      showUndo(`방금 ${saved.length}명을 출석으로 표시했습니다`, async () => {
        for (const r of saved) await repo.remove('attendance', r.id)
        await load()
        toast('되돌렸습니다', 'ok')
      })
    }

    function applyToCell(cell, rec) {
      if (!cell) return
      cell.__record = rec
      cell.dataset.status = rec?.status || ''
      cell.querySelector('.st').textContent = rec ? `${rec.status}${rec.reason_tag ? ` · ${rec.reason_tag}` : ''}` : '미체크'
    }

    // 탭 한 번 = 출석 → 지각 → 결석 → 미체크 순환 (현장에서 가장 빠른 방식)
    async function quickToggle(student, cell) {
      const order = [null, ATT.PRESENT, ATT.LATE, ATT.ABSENT]
      const cur = cell.__record?.status || null
      const next = order[(order.indexOf(cur) + 1) % order.length]
      if (next === null) {
        if (cell.__record) await repo.remove('attendance', cell.__record.id)
        applyToCell(cell, null)
      } else {
        const rec = await repo.markAttendance({
          classId, date, studentId: student.id, status: next,
          reason_tag: next === ATT.ABSENT ? (cell.__record?.reason_tag || null) : null,
          checked_by: user?.id || null
        })
        applyToCell(cell, rec)
      }
      renderSummary()
    }

    function openDetail(student, cell) {
      const tags = repo.getSetting('reasonTags', ['질병', '가족행사', '학교일정', '무단', '기타'])
      let status = cell.__record?.status || ATT.PRESENT
      let reason = cell.__record?.reason_tag || null

      const statusRow = h('div', { class: 'row wrap' })
      const tagRow = h('div', { class: 'row wrap' })
      const paint = () => {
        clear(statusRow)
        for (const st of ATT_LIST) {
          statusRow.append(h('button', {
            class: `chip ${status === st ? 'active' : ''}`,
            onClick: () => { status = st; paint() }
          }, st))
        }
        clear(tagRow)
        for (const t of tags) {
          tagRow.append(h('button', {
            class: `chip ${reason === t ? 'active' : ''}`,
            onClick: () => { reason = reason === t ? null : t; paint() }
          }, t))
        }
      }
      paint()

      const makeupDate = h('input', { type: 'date', value: addDays(date, 7) })

      modal({
        title: `${student.name} · ${date}`,
        body: h('div', {},
          field('출결 상태', statusRow),
          field('사유 태그', tagRow, '결석/지각 사유를 남기면 이탈 위험 감지와 리포트에 함께 표시됩니다'),
          h('hr', { style: { border: 0, borderTop: '1px solid var(--line)', margin: '14px 0' } }),
          field('보강 예약', h('div', { class: 'row' }, makeupDate,
            h('button', {
              class: 'btn sm', onClick: async () => {
                await repo.bookMakeup({ studentId: student.id, classId, date: makeupDate.value })
                toast(`${makeupDate.value} 보강으로 예약했습니다`, 'ok')
              }
            }, '예약')))
        ),
        actions: [
          cell.__record ? {
            label: '체크 취소', kind: 'danger', onClick: async () => {
              await repo.remove('attendance', cell.__record.id)
              applyToCell(cell, null)
              renderSummary()
            }
          } : null,
          {
            label: '저장', kind: 'primary', onClick: async () => {
              const rec = await repo.markAttendance({
                classId, date, studentId: student.id, status,
                reason_tag: reason, checked_by: user?.id || null
              })
              applyToCell(cell, rec)
              renderSummary()
            }
          }
        ].filter(Boolean)
      })
    }
  }

  renderClasses()
  await load()

  const off = repo.on('attendance', () => {})
  return () => off()
}
