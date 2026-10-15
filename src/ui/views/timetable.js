// 시간표 탭 — 주간 그리드 + 강의실/강사 중복 경고 + 공석(추가 모집) 표시

import { h, clear, toast, modal, field, confirmDialog } from '../dom.js'
import { WEEKDAYS, hhmmToMin } from '../../core/date.js'
import { findConflicts, weekGrid, slotsOf, vacancyOf } from '../../core/schedule.js'
import { visibleClasses } from '../../core/perm.js'

const START_HOUR = 9
const END_HOUR = 22
const PX_PER_MIN = 0.9

export async function render(root, ctx) {
  const { repo, user } = ctx
  const canEdit = ctx.can('classes:write') || user?.role === 'owner'

  const warnBox = h('div')
  const gridBox = h('div', { class: 'scroll-x' })
  const vacancyBox = h('div', { class: 'row wrap', style: { gap: '6px' } })

  root.append(
    h('div', { class: 'card' },
      h('div', { class: 'row wrap' },
        h('div', { class: 'card-title', style: { margin: 0 } }, '주간 시간표'),
        canEdit ? h('button', { class: 'btn primary right', onClick: () => openClassEditor() }, '+ 반 만들기') : null
      ),
      h('div', { style: { marginTop: '8px' } }, warnBox)
    ),
    h('div', { class: 'card', style: { marginTop: '12px' } }, gridBox),
    h('div', { class: 'card', style: { marginTop: '12px' } },
      h('div', { class: 'card-title' }, '공석 현황 (추가 모집 가능)'), vacancyBox)
  )

  function paint() {
    const classes = visibleClasses(user, repo.cache.classes).filter((c) => c.status !== '종료')

    // 중복 배정 경고
    const conflicts = findConflicts(classes)
    clear(warnBox)
    if (conflicts.length) {
      warnBox.append(h('div', { class: 'badge danger', style: { marginBottom: '6px' } }, `중복 배정 ${conflicts.length}건`))
      for (const c of conflicts.slice(0, 8)) warnBox.append(h('div', { class: 'small', style: { color: 'var(--danger)' } }, `⚠ ${c.label}`))
    } else {
      warnBox.append(h('span', { class: 'badge ok' }, '강의실·강사 중복 없음'))
    }

    // 그리드
    clear(gridBox)
    const grid = h('div', { class: 'timetable' })
    grid.append(h('div', { class: 'tt-head' }, ''))
    for (const d of WEEKDAYS) grid.append(h('div', { class: 'tt-head' }, d))

    const hours = END_HOUR - START_HOUR
    const colHeight = hours * 60 * PX_PER_MIN
    const timeCol = h('div', {})
    for (let hgt = START_HOUR; hgt < END_HOUR; hgt++) {
      timeCol.append(h('div', { class: 'tt-time', style: { height: `${60 * PX_PER_MIN}px` } }, `${hgt}시`))
    }
    grid.append(timeCol)

    const byDow = weekGrid(classes)
    for (let d = 0; d < 7; d++) {
      const col = h('div', { class: 'tt-cell', style: { height: `${colHeight}px`, position: 'relative' } })
      for (let hgt = START_HOUR; hgt < END_HOUR; hgt++) {
        col.append(h('div', { style: { position: 'absolute', left: 0, right: 0, top: `${(hgt - START_HOUR) * 60 * PX_PER_MIN}px`, borderTop: '1px solid var(--line)', height: '0' } }))
      }
      for (const { cls, slot } of byDow.get(d) || []) {
        const subject = repo.cache.subjectById.get(cls.subject_id)
        const top = (slot.startMin - START_HOUR * 60) * PX_PER_MIN
        const hgt = Math.max(24, (slot.endMin - slot.startMin) * PX_PER_MIN)
        const teacher = repo.cache.userById.get(cls.teacher_id)
        const v = vacancyOf(cls, repo.enrolledCount(cls.id))
        const conflicted = findConflicts([cls, ...classes.filter((c) => c.id !== cls.id)]).some((c) => c.a === cls.id || c.b === cls.id)
        col.append(h('div', {
          class: 'tt-block',
          style: { top: `${Math.max(0, top)}px`, height: `${hgt}px`, background: subject?.color || 'var(--brand)', outline: conflicted ? '2px solid #dc2626' : 'none' },
          onClick: () => canEdit ? openClassEditor(cls) : toast(`${cls.name} · ${teacher?.name || '담당 미지정'}`)
        },
          h('b', {}, cls.name),
          h('div', {}, `${slot.start}~${slot.end}`),
          h('div', {}, `${cls.room || ''} ${v.capacity ? `${v.enrolled}/${v.capacity}` : `${v.enrolled}명`}`)
        ))
      }
      grid.append(col)
    }
    gridBox.append(grid)

    // 공석
    clear(vacancyBox)
    const open = classes.map((c) => ({ c, v: vacancyOf(c, repo.enrolledCount(c.id)) })).filter((x) => x.v.open > 0)
    if (!open.length) vacancyBox.append(h('span', { class: 'muted small' }, '정원이 설정된 반 중 공석이 없습니다'))
    for (const { c, v } of open) {
      vacancyBox.append(h('span', { class: 'badge brand' }, `${c.name} ${v.open}자리`))
    }
  }

  function openClassEditor(cls = null) {
    const name = h('input', { type: 'text', value: cls?.name || '' })
    const subject = h('select', {}, h('option', { value: '' }, '과목 선택'), ...repo.cache.subjects.map((s) => h('option', { value: s.id, selected: cls?.subject_id === s.id }, s.name)))
    const teacher = h('select', {}, h('option', { value: '' }, '담당 미지정'), ...repo.cache.users.map((u) => h('option', { value: u.id, selected: cls?.teacher_id === u.id }, u.name)))
    const room = h('input', { type: 'text', value: cls?.room || '' })
    const capacity = h('input', { type: 'number', value: cls?.capacity || '', min: '0' })
    const fee = h('input', { type: 'number', value: cls?.fee || '', min: '0', step: '1000' })
    let slots = slotsOf(cls || {}).map((s) => ({ dow: s.dow, start: s.start, end: s.end }))
    const slotBox = h('div')

    const paintSlots = () => {
      clear(slotBox)
      slots.forEach((s, i) => {
        slotBox.append(h('div', { class: 'row', style: { marginBottom: '6px' } },
          h('select', { onChange: (e) => { s.dow = Number(e.target.value) } }, ...WEEKDAYS.map((d, di) => h('option', { value: di, selected: s.dow === di }, d))),
          h('input', { type: 'time', value: s.start, onChange: (e) => { s.start = e.target.value } }),
          h('input', { type: 'time', value: s.end, onChange: (e) => { s.end = e.target.value } }),
          h('button', { class: 'btn sm danger', onClick: () => { slots.splice(i, 1); paintSlots() } }, '삭제')
        ))
      })
      slotBox.append(h('button', {
        class: 'btn sm', onClick: () => { slots.push({ dow: 1, start: '15:00', end: '16:00' }); paintSlots() }
      }, '+ 수업 시간 추가'))
    }
    paintSlots()

    modal({
      title: cls ? '반 수정' : '반 만들기',
      wide: true,
      body: h('div', {},
        h('div', { class: 'inline-fields' },
          field('반 이름', name), field('과목', subject), field('담당 강사', teacher),
          field('강의실', room), field('정원', capacity), field('수강료', fee)),
        field('수업 시간', slotBox, '요일·시간이 겹치면 강의실/강사 중복 경고가 표시됩니다')
      ),
      actions: [
        cls ? {
          label: '삭제', kind: 'danger', keepOpen: true, onClick: async (close) => {
            if (!await confirmDialog(`${cls.name} 반을 삭제할까요?`, { danger: true, okLabel: '삭제' })) return false
            await repo.remove('classes', cls.id)
            paint()
            close()
          }
        } : null,
        {
          label: '저장', kind: 'primary', keepOpen: true, onClick: async (close) => {
            if (!name.value.trim()) { toast('반 이름을 입력해 주세요', 'error'); return false }
            const bad = slots.find((s) => hhmmToMin(s.end) <= hhmmToMin(s.start))
            if (bad) { toast('종료 시간이 시작 시간보다 빠릅니다', 'error'); return false }
            const saved = await repo.put('classes', {
              ...(cls || {}),
              name: name.value.trim(),
              subject_id: subject.value || null,
              teacher_id: teacher.value || null,
              room: room.value.trim(),
              capacity: Number(capacity.value) || 0,
              fee: Number(fee.value) || 0,
              schedule: slots,
              status: cls?.status || '운영'
            })
            const conf = findConflicts(repo.cache.classes).filter((c) => c.a === saved.id || c.b === saved.id)
            paint()
            toast(conf.length ? `저장했지만 중복 배정 ${conf.length}건이 있습니다` : '저장했습니다', conf.length ? 'error' : 'ok')
            close()
          }
        }
      ].filter(Boolean)
    })
  }

  paint()
  const offs = [repo.on('classes', paint), repo.on('enrollments', paint)]
  return () => offs.forEach((o) => o())
}
