// 키오스크 자가 체크인 — 학원 입구 태블릿용. 원생이 자기 이름을 눌러 출석 처리.

import { h, clear, toast, modal, confirmDialog } from '../dom.js'
import * as repo from '../../data/repo.js'
import { branding, logoDataUrl } from '../branding.js'
import { toYmd, dowOf } from '../../core/date.js'
import { ATT } from '../../core/attendance.js'
import { classesOnDow } from '../../core/schedule.js'
import { findByPin, DEFAULT_PIN } from '../session.js'

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
        h('div', { class: 'grow' }, h('h2', { style: { margin: 0 } }, `${b.name} 등원 체크`), h('div', { class: 'small muted' }, `${Number(date.slice(5, 7))}월 ${Number(date.slice(8, 10))}일 · 내 이름을 누르면 출석됩니다`)),
        h('button', { class: 'btn', onClick: exit }, '닫기')),
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

  // 닫을 때는 잠금 번호 확인 — 원생이 임의로 닫지 못하게.
  // 잠금 번호를 정한 적이 없는 1인 학원은 물어볼 번호가 없으니 한 번 더 묻기만 한다.
  // (브라우저 기본 창(confirm/prompt)은 뜨지 않는 환경이 있어 앱 안의 창으로 묻는다)
  async function exit() {
    const locked = repo.cache.users.length > 1 || repo.cache.users.some((u) => String(u.pin || DEFAULT_PIN) !== DEFAULT_PIN)
    if (!locked) {
      if (await confirmDialog('등원 체크 화면을 닫을까요?', { title: '닫기', okLabel: '닫기' })) cover.remove()
      return
    }
    const pin = h('input', {
      type: 'password', inputMode: 'numeric', maxLength: 4, autocomplete: 'off', placeholder: '●●●●',
      'aria-label': '잠금 번호', style: { fontSize: '1.4em', textAlign: 'center', letterSpacing: '.4em' }
    })
    const tryClose = (close) => {
      if (!findByPin(pin.value)) { toast('번호가 맞지 않습니다', 'error'); pin.value = ''; pin.focus(); return false }
      close()
      cover.remove()
    }
    const dialog = modal({
      title: '선생님 확인',
      body: h('div', {}, h('p', { class: 'muted small', style: { marginTop: 0 } }, '선생님 잠금 번호 4자리를 넣으면 닫힙니다.'), pin),
      actions: [{ label: '취소' }, { label: '닫기', kind: 'primary', keepOpen: true, onClick: (close) => tryClose(close) }]
    })
    pin.addEventListener('keydown', (e) => { if (e.key === 'Enter') tryClose(dialog.close) })
    setTimeout(() => pin.focus(), 50)
  }
}
