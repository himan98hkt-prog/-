// 키오스크 자가 체크인 — 학원 입구 태블릿용. 원생이 자기 이름을 눌러 출석 처리.

import { h, clear, toast } from '../dom.js'
import * as repo from '../../data/repo.js'
import { branding, logoDataUrl } from '../branding.js'
import { toYmd, dowOf } from '../../core/date.js'
import { ATT } from '../../core/attendance.js'
import { classesOnDow } from '../../core/schedule.js'
import { findByPin } from '../session.js'

export function openKiosk() {
  const date = toYmd()
  const b = branding()
  let classId = null

  const grid = h('div', { class: 'kiosk-grid' })
  const classBar = h('div', { class: 'row wrap', style: { gap: '6px', marginBottom: '12px' } })
  const cover = h('div', { class: 'cover kiosk' },
    h('div', { class: 'panel card', style: { width: 'min(880px, 100%)' } },
      h('div', { class: 'row', style: { marginBottom: '10px' } },
        h('img', { src: logoDataUrl(192), style: { width: '44px', height: '44px', borderRadius: '12px' }, alt: '' }),
        h('div', { class: 'grow' }, h('h2', { style: { margin: 0 } }, `${b.name} 출석 체크`), h('div', { class: 'small muted' }, `${date} · 이름을 눌러 출석하세요`)),
        h('button', { class: 'btn', onClick: exit }, '나가기')),
      classBar, grid))

  document.body.append(cover)
  paintClasses()
  load()

  function paintClasses() {
    const classes = classesOnDow(repo.cache.classes.filter((c) => c.status !== '종료'), dowOf(date))
    const list = classes.length ? classes : repo.cache.classes
    if (!list.some((c) => c.id === classId)) classId = list[0]?.id || null
    clear(classBar)
    for (const c of list) {
      classBar.append(h('button', {
        class: `chip ${c.id === classId ? 'active' : ''}`,
        onClick: () => { classId = c.id; paintClasses(); load() }
      }, c.name))
    }
  }

  async function load() {
    clear(grid)
    if (!classId) { grid.append(h('p', { class: 'muted' }, '오늘 수업이 없습니다')); return }
    const roster = repo.rosterOf(classId, date)
    const records = await repo.attendanceOfClassDate(classId, date)
    const done = new Set(records.map((r) => r.student_id))
    for (const s of roster) {
      const btn = h('button', {
        class: done.has(s.id) ? 'done' : '',
        onClick: async () => {
          if (done.has(s.id)) return
          await repo.markAttendance({ classId, date, studentId: s.id, status: ATT.PRESENT, checked_by: 'kiosk' })
          done.add(s.id)
          btn.className = 'done'
          btn.textContent = `${s.name} ✓`
          toast(`${s.name} 출석 완료`, 'ok')
        }
      }, done.has(s.id) ? `${s.name} ✓` : s.name)
      grid.append(btn)
    }
  }

  // 나가기는 PIN 확인 — 원생이 임의로 종료하지 못하게
  function exit() {
    const pin = prompt('관리자 PIN 4자리를 입력하세요')
    if (pin === null) return
    if (!findByPin(pin)) return toast('PIN 이 올바르지 않습니다', 'error')
    cover.remove()
  }
}
