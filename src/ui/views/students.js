// 원생 탭 — 가상 스크롤 목록 + 즉시 검색(debounce 200ms) + 원생 카드.

import { h, clear, toast, modal, field, debounce, confirmDialog } from '../dom.js'
import { VirtualList } from '../virtual-list.js'
import { STUDENT_STATUS } from '../../data/repo.js'
import { displayPairs, normalizeValues } from '../../core/customfields.js'
import { formatWon } from '../../core/fees.js'
import { toYmd, addMonths, toMonth } from '../../core/date.js'
import { summarize } from '../../core/attendance.js'
import { openReportModal } from './report-modal.js'
import { openNoticeModal } from './notice-modal.js'

export async function render(root, ctx) {
  const { repo } = ctx
  const canWrite = ctx.can('students:write')
  let query = ''
  let status = '재원'
  let classId = ''

  const count = h('span', { class: 'muted small' })
  const search = h('input', {
    type: 'search', placeholder: '이름 · 학교 · 학년 · 전화번호 검색', autocomplete: 'off',
    onInput: debounce((e) => { query = e.target.value; apply() }, 200)
  })

  const statusChips = h('div', { class: 'row wrap' })
  const classSelect = h('select', { onChange: (e) => { classId = e.target.value; apply() } },
    h('option', { value: '' }, '전체 반'),
    ...repo.cache.classes.map((c) => h('option', { value: c.id }, c.name))
  )

  const head = h('div', { class: 'card' },
    h('div', { class: 'row wrap' },
      h('div', { class: 'grow' }, search),
      classSelect,
      canWrite ? h('button', { class: 'btn primary', onClick: () => openEditor() }, '+ 원생 등록') : null
    ),
    h('div', { class: 'row wrap', style: { marginTop: '10px' } }, statusChips, h('span', { class: 'right' }, count))
  )

  const viewport = h('div', { class: 'vl-viewport' })
  root.append(head, h('div', { style: { marginTop: '12px' } }, viewport))

  const list = new VirtualList(viewport, {
    rowHeight: 64,
    renderRow: (s) => {
      const cls = repo.studentClasses(s.id).map((c) => c.name).join(', ')
      const sibs = repo.siblingsOf(s)
      return h('div', { class: 'student-row', onClick: () => openCard(s) },
        h('div', { class: 'avatar' }, String(s.name || '').slice(0, 2)),
        h('div', { class: 'grow truncate' },
          h('div', { class: 'row', style: { gap: '6px' } },
            h('b', {}, s.name),
            s.status !== '재원' ? h('span', { class: 'badge warn' }, s.status) : null,
            sibs.length ? h('span', { class: 'badge' }, `형제 ${sibs.length + 1}`) : null
          ),
          h('div', { class: 'small muted truncate' }, [s.school, s.grade, cls].filter(Boolean).join(' · ') || '반 미배정')
        ),
        h('span', { class: 'muted small' }, s.parent_phone || s.phone || '')
      )
    }
  })

  function paintChips() {
    clear(statusChips)
    for (const st of ['전체', ...STUDENT_STATUS]) {
      statusChips.append(h('button', {
        class: `chip ${(st === '전체' ? '' : st) === status ? 'active' : ''}`,
        onClick: () => { status = st === '전체' ? '' : st; paintChips(); apply() }
      }, st))
    }
  }

  function apply() {
    const rows = repo.searchStudents(query, { status: status || undefined, classId: classId || undefined })
    list.setItems(rows)
    count.textContent = `${rows.length.toLocaleString('ko-KR')}명`
  }

  paintChips()
  apply()

  // ── 원생 카드 ──────────────────────────────────────────────
  async function openCard(student) {
    const cls = repo.studentClasses(student.id)
    const fields = repo.getSetting('customFields', [])
    const pairs = displayPairs(fields, student.custom || {}, 'card')
    const sibs = repo.siblingsOf(student)
    const month = toMonth(toYmd())
    const [pays, att] = await Promise.all([
      repo.paymentsOfStudent(student.id, 6),
      repo.attendanceOfStudentRange(student.id, `${addMonths(month, -2)}-01`, toYmd())
    ])
    const sum = summarize(att)

    modal({
      title: student.name,
      wide: true,
      body: h('div', {},
        h('div', { class: 'row wrap', style: { gap: '6px', marginBottom: '10px' } },
          h('span', { class: 'badge brand' }, student.status || '재원'),
          student.school ? h('span', { class: 'badge' }, student.school) : null,
          student.grade ? h('span', { class: 'badge' }, student.grade) : null,
          ...cls.map((c) => h('span', { class: 'badge' }, c.name))
        ),
        h('div', { class: 'grid cols3' },
          stat('최근 3개월 출석률', `${sum.rate}%`),
          stat('결석', `${sum.absent}회`),
          stat('미납', `${pays.filter((p) => p.status !== '완납').length}건`)
        ),
        h('div', { class: 'card', style: { marginTop: '12px' } },
          h('div', { class: 'card-title' }, '연락처'),
          h('div', { class: 'small' }, `학생 ${student.phone || '-'} / 학부모 ${student.parent_phone || '-'}`),
          sibs.length ? h('div', { class: 'small muted', style: { marginTop: '6px' } }, `형제·자매: ${sibs.map((s) => s.name).join(', ')} (학부모 번호 매칭)`) : null
        ),
        pairs.length ? h('div', { class: 'card' },
          h('div', { class: 'card-title' }, '학습 현황'),
          h('table', {}, h('tbody', {}, ...pairs.map((p) => h('tr', {}, h('th', {}, p.label), h('td', {}, String(p.value))))))
        ) : null,
        h('div', { class: 'card' },
          h('div', { class: 'card-title' }, '최근 수납'),
          pays.length ? h('table', {},
            h('tbody', {}, ...pays.map((p) => h('tr', {},
              h('td', {}, p.month),
              h('td', {}, formatWon(p.amount)),
              h('td', {}, h('span', { class: `badge ${p.status === '완납' ? 'ok' : p.status === '부분' ? 'warn' : 'danger'}` }, p.status))
            )))
          ) : h('p', { class: 'muted small' }, '수납 기록이 없습니다'),
          student.memo ? h('p', { class: 'small muted' }, `메모: ${student.memo}`) : null
        )
      ),
      actions: [
        { label: '리포트', onClick: () => openReportModal(student), keepOpen: false },
        { label: '문자 문구', onClick: () => openNoticeModal({ student }) },
        canWrite ? { label: '수정', kind: 'primary', onClick: () => openEditor(student) } : null
      ].filter(Boolean)
    })
  }

  function stat(label, value) {
    return h('div', { class: 'stat' }, h('div', { class: 'v' }, value), h('div', { class: 'l' }, label))
  }

  // ── 등록/수정 ──────────────────────────────────────────────
  function openEditor(student = null) {
    const fields = repo.getSetting('customFields', [])
    const f = {
      name: h('input', { type: 'text', value: student?.name || '', required: true }),
      school: h('input', { type: 'text', value: student?.school || '' }),
      grade: h('input', { type: 'text', value: student?.grade || '' }),
      phone: h('input', { type: 'tel', value: student?.phone || '' }),
      parent_phone: h('input', { type: 'tel', value: student?.parent_phone || '' }),
      status: h('select', {}, ...STUDENT_STATUS.map((s) => h('option', { value: s, selected: (student?.status || '재원') === s }, s))),
      joined_at: h('input', { type: 'date', value: student?.joined_at || toYmd() }),
      memo: h('textarea', { value: student?.memo || '' })
    }
    const customInputs = new Map()
    for (const cf of fields) {
      const val = student?.custom?.[cf.key] ?? ''
      let input
      if (cf.type === 'select') input = h('select', {}, h('option', { value: '' }, '-'), ...(cf.options || []).map((o) => h('option', { value: o, selected: String(val) === o }, o)))
      else if (cf.type === 'textarea') input = h('textarea', { value: val })
      else input = h('input', { type: cf.type === 'number' ? 'number' : cf.type === 'date' ? 'date' : 'text', value: val })
      customInputs.set(cf.key, input)
    }

    const classPicker = h('div', { class: 'row wrap' })
    const selected = new Set(repo.activeEnrollments({ studentId: student?.id }).map((e) => e.class_id))
    const paintClasses = () => {
      clear(classPicker)
      for (const c of repo.cache.classes) {
        classPicker.append(h('button', {
          class: `chip ${selected.has(c.id) ? 'active' : ''}`,
          onClick: () => { selected.has(c.id) ? selected.delete(c.id) : selected.add(c.id); paintClasses() }
        }, c.name))
      }
      if (!repo.cache.classes.length) classPicker.append(h('span', { class: 'muted small' }, '설정 > 반 관리에서 반을 먼저 만들어 주세요'))
    }
    paintClasses()

    modal({
      title: student ? '원생 수정' : '원생 등록',
      wide: true,
      body: h('div', {},
        h('div', { class: 'inline-fields' },
          field('이름 *', f.name), field('상태', f.status),
          field('학교', f.school), field('학년', f.grade),
          field('학생 연락처', f.phone), field('학부모 연락처', f.parent_phone, '같은 번호면 형제로 자동 묶입니다'),
          field('등록일', f.joined_at)
        ),
        field('반 배정', classPicker),
        fields.length ? h('div', {}, h('div', { class: 'card-title' }, '학습 항목'),
          h('div', { class: 'inline-fields' }, ...fields.map((cf) => field(cf.label, customInputs.get(cf.key))))) : null,
        field('메모', f.memo)
      ),
      actions: [
        student ? {
          label: '삭제', kind: 'danger', keepOpen: true, onClick: async (close) => {
            if (!await confirmDialog(`${student.name} 원생을 삭제할까요? 출결·수납 기록은 남습니다.`, { danger: true, okLabel: '삭제' })) return false
            await repo.remove('students', student.id)
            apply()
            close()
          }
        } : null,
        {
          label: '저장', kind: 'primary', keepOpen: true, onClick: async (close) => {
            const name = f.name.value.trim()
            if (!name) { toast('이름을 입력해 주세요', 'error'); return false }
            const custom = normalizeValues(fields, Object.fromEntries([...customInputs].map(([k, el]) => [k, el.value])))
            const saved = await repo.saveStudent({
              ...(student || {}),
              name,
              school: f.school.value.trim(),
              grade: f.grade.value.trim(),
              phone: f.phone.value.trim(),
              parent_phone: f.parent_phone.value.trim(),
              status: f.status.value,
              joined_at: f.joined_at.value,
              left_at: f.status.value === '퇴원' ? (student?.left_at || toYmd()) : null,
              memo: f.memo.value.trim(),
              custom
            })
            // 반 배정 반영
            const current = repo.activeEnrollments({ studentId: saved.id })
            for (const e of current) if (!selected.has(e.class_id)) await repo.unenroll(e.id)
            for (const cid of selected) if (!current.some((e) => e.class_id === cid)) await repo.enroll(saved.id, cid)
            apply()
            toast('저장했습니다', 'ok')
            close()
          }
        }
      ].filter(Boolean)
    })
  }

  const offs = [repo.on('students', apply), repo.on('enrollments', apply)]
  return () => { offs.forEach((o) => o()); list.destroy() }
}
