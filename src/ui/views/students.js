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
import { icon } from '../icons.js'
import { openImportStudents } from './import-students.js'
import { openBulkNotice } from './bulk-notice.js'
import { downloadCsv } from '../../core/csv.js'
import { progressLine, keepReserved } from '../../core/books.js'
import { booksPanel } from '../books-panel.js'

/** 이름으로 정하는 얼굴 색 — 같은 학생은 언제나 같은 색이라 목록에서 눈으로 찾기 쉽다 */
function toneOf(name) {
  let n = 0
  for (const ch of String(name || '')) n = (n * 31 + ch.codePointAt(0)) % 997
  return n % 6
}

export async function render(root, ctx) {
  const { repo } = ctx
  const canWrite = ctx.can('students:write')
  let query = ''
  let status = '재원'
  let classId = ''

  const count = h('span', { class: 'muted small' })
  const search = h('input', {
    type: 'search', placeholder: '이름이나 전화번호로 찾기', autocomplete: 'off', 'aria-label': '원생 찾기',
    onInput: debounce((e) => { query = e.target.value; apply() }, 200)
  })

  const statusChips = h('div', { class: 'row wrap' })
  const classSelect = h('select', { onChange: (e) => { classId = e.target.value; apply() } },
    h('option', { value: '' }, '모든 반'),
    ...repo.cache.classes.map((c) => h('option', { value: c.id }, c.name))
  )

  // 자주 쓰는 것(찾기 · 등록)은 크게, 가끔 쓰는 것(가져오기 · 내보내기)은 한 줄 아래에 작게 둔다
  const head = h('div', { class: 'card toolbar' },
    h('div', { class: 'toolbar-main' },
      h('label', { class: 'searchbox grow' }, icon('search', { size: 18 }), search),
      classSelect,
      canWrite ? h('button', { class: 'btn primary', type: 'button', dataset: { act: 'add-student' }, onClick: () => openEditor() }, icon('plus', { size: 17 }), '원생 등록') : null
    ),
    h('div', { class: 'toolbar-sub' },
      statusChips,
      h('span', { class: 'count' }, count),
      h('span', { class: 'right' }),
      canWrite ? h('button', { class: 'btn sm ghost', type: 'button', onClick: () => openImportStudents({ onDone: apply }) }, icon('upload', { size: 15 }), '엑셀에서 가져오기') : null,
      h('button', { class: 'btn sm ghost', type: 'button', onClick: exportCsv }, icon('download', { size: 15 }), '명단 내려받기'),
      h('button', { class: 'btn sm ghost', type: 'button', onClick: bulkNotice }, icon('send', { size: 15 }), '보이는 원생에게 문자')
    )
  )

  const viewport = h('div', { class: 'vl-viewport' })
  root.append(
    h('div', { class: 'page-head' },
      h('h1', {}, '원생'),
      h('p', {}, '이름을 누르면 출석률·수강료·교재 진도까지 한 장으로 보입니다.')),
    head,
    h('div', { style: { marginTop: '12px' } }, viewport))

  const list = new VirtualList(viewport, {
    rowHeight: 64,
    renderRow: (s) => {
      const cls = repo.studentClasses(s.id).map((c) => c.name).join(', ')
      const sibs = repo.siblingsOf(s)
      return h('div', { class: 'student-row', onClick: () => openCard(s) },
        h('div', { class: `avatar tone${toneOf(s.name)}` }, String(s.name || '').slice(0, 1)),
        h('div', { class: 'grow truncate' },
          h('div', { class: 'row', style: { gap: '6px' } },
            h('b', {}, s.name),
            s.status !== '재원' ? h('span', { class: 'badge warn' }, s.status) : null,
            sibs.length ? h('span', { class: 'badge' }, `형제 ${sibs.length + 1}`) : null
          ),
          h('div', { class: 'small muted truncate' }, [cls, s.school, s.grade, progressLine(s)].filter(Boolean).join(' · ') || '아직 반이 없습니다')
        ),
        h('span', { class: 'muted small phone' }, s.parent_phone || s.phone || ''),
        icon('chevronRight', { size: 17, class: 'chev' })
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

  function visibleStudents() {
    return repo.searchStudents(query, { status: status || undefined, classId: classId || undefined })
  }

  function exportCsv() {
    const rows = visibleStudents().map((s) => [
      s.name, s.status, s.school || '', s.grade || '',
      repo.studentClasses(s.id).map((c) => c.name).join(' '),
      s.phone || '', s.parent_phone || '', s.joined_at || '', s.memo || ''
    ])
    if (!rows.length) return toast('내보낼 원생이 없습니다', 'error')
    downloadCsv(`원생명단_${toYmd()}.csv`,
      ['이름', '상태', '학교', '학년', '반', '학생연락처', '학부모연락처', '등록일', '메모'], rows)
    toast(`${rows.length}명 명단을 엑셀 파일로 저장했습니다`, 'ok')
  }

  function bulkNotice() {
    const list = visibleStudents()
    if (!list.length) return toast('대상 원생이 없습니다', 'error')
    openBulkNotice({ studentIds: list.map((s) => s.id), templateId: 'lesson', title: `학부모 안내 문자 (${list.length}명)` })
  }

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

    const unpaid = pays.filter((p) => p.status !== '완납').length
    const phoneLine = (label, num) => h('div', { class: 'kv' },
      h('span', { class: 'k' }, label),
      num ? h('a', { class: 'v', href: `tel:${num}` }, num) : h('span', { class: 'v muted' }, '없음'))

    modal({
      title: student.name,
      wide: true,
      body: h('div', { class: 'student-card' },
        h('div', { class: 'row wrap', style: { gap: '6px', marginBottom: '12px' } },
          h('span', { class: `badge ${student.status === '재원' || !student.status ? 'ok' : 'warn'}` }, student.status || '재원'),
          ...cls.map((c) => h('span', { class: 'badge brand' }, c.name)),
          student.school ? h('span', { class: 'badge' }, student.school) : null,
          student.grade ? h('span', { class: 'badge' }, student.grade) : null
        ),
        h('div', { class: 'grid cols3' },
          stat('최근 3개월 출석률', `${sum.rate}%`),
          stat('결석', `${sum.absent}회`, sum.absent >= 3 ? 'danger' : ''),
          stat('안 낸 수강료', unpaid ? `${unpaid}건` : '없음', unpaid ? 'warn' : '')
        ),
        h('div', { class: 'card' },
          h('div', { class: 'card-title' }, icon('book', { size: 18 }), '교재 · 진도',
            h('span', { class: 'hint' }, '칸에 적고 다른 곳을 누르면 저장됩니다')),
          booksPanel(student.id, { canWrite, onChange: apply })
        ),
        h('div', { class: 'card' },
          h('div', { class: 'card-title' }, icon('phone', { size: 18 }), '연락처'),
          phoneLine('학부모', student.parent_phone),
          phoneLine('학생', student.phone),
          sibs.length ? h('div', { class: 'kv' }, h('span', { class: 'k' }, '형제·자매'), h('span', { class: 'v' }, sibs.map((s) => s.name).join(', '))) : null
        ),
        pairs.length ? h('div', { class: 'card' },
          h('div', { class: 'card-title' }, icon('list', { size: 18 }), '학습 기록'),
          ...pairs.map((p) => h('div', { class: 'kv' }, h('span', { class: 'k' }, p.label), h('span', { class: 'v' }, String(p.value))))
        ) : null,
        h('div', { class: 'card' },
          h('div', { class: 'card-title' }, icon('won', { size: 18 }), '최근 수강료'),
          pays.length
            ? h('div', {}, ...pays.map((p) => h('div', { class: 'kv' },
              h('span', { class: 'k' }, `${Number(p.month.slice(5, 7))}월`),
              h('span', { class: 'v num' }, formatWon(p.amount)),
              h('span', { class: `badge ${p.status === '완납' ? 'ok' : p.status === '부분' ? 'warn' : 'danger'}` }, p.status))))
            : h('p', { class: 'muted small', style: { margin: 0 } }, '아직 청구한 수강료가 없습니다'),
          student.memo ? h('p', { class: 'small muted', style: { margin: '10px 0 0' } }, `메모: ${student.memo}`) : null
        )
      ),
      actions: [
        { label: '학부모 리포트', onClick: () => openReportModal(repo.cache.studentById.get(student.id) || student), keepOpen: false },
        { label: '문자 보내기', onClick: () => openNoticeModal({ student: repo.cache.studentById.get(student.id) || student, templateId: 'lesson' }) },
        canWrite ? { label: '정보 고치기', kind: 'primary', onClick: () => openEditor(repo.cache.studentById.get(student.id) || student) } : null
      ].filter(Boolean)
    })
  }

  function stat(label, value, tone = '') {
    return h('div', { class: `stat plain ${tone}` }, h('div', { class: 'l' }, label), h('div', { class: 'v' }, value))
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
      memo: h('textarea', { value: student?.memo || '' }),
      discountType: h('select', {},
        h('option', { value: 'percent', selected: (student?.discount?.type || 'percent') === 'percent' }, '%'),
        h('option', { value: 'amount', selected: student?.discount?.type === 'amount' }, '원')),
      discountValue: h('input', { type: 'number', min: '0', value: student?.discount?.value ?? '' }),
      discountMemo: h('input', { type: 'text', value: student?.discount?.memo || '', placeholder: '예) 장기 등록' })
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
    // 새 원생은 아무 반도 고르지 않은 상태에서 시작한다.
    // (원생 번호 없이 조회하면 "모든 수강 기록" 이 돌아와 모든 반이 골라진 채로 열렸다)
    const selected = new Set(student ? repo.activeEnrollments({ studentId: student.id }).map((e) => e.class_id) : [])
    const paintClasses = () => {
      clear(classPicker)
      for (const c of repo.cache.classes) {
        classPicker.append(h('button', {
          class: `chip ${selected.has(c.id) ? 'active' : ''}`,
          onClick: () => { selected.has(c.id) ? selected.delete(c.id) : selected.add(c.id); paintClasses() }
        }, c.name))
      }
      if (!repo.cache.classes.length) classPicker.append(h('span', { class: 'muted small' }, '아직 반이 없습니다. 먼저 저장하고, "시간표" 메뉴에서 반을 만든 뒤 다시 골라도 됩니다.'))
    }
    paintClasses()

    // 이름과 학부모 번호, 반 — 이 셋이면 출석·수강료·문자가 모두 돌아간다. 나머지는 필요할 때 펼친다.
    const hasMore = !!(student && (student.school || student.grade || student.phone || student.memo || student.discount ||
      (student.status && student.status !== '재원') || Object.keys(student.custom || {}).some((k) => !k.startsWith('_'))))
    modal({
      title: student ? `${student.name} 정보 고치기` : '원생 등록',
      wide: true,
      body: h('div', {},
        h('div', { class: 'inline-fields' },
          field('이름 *', f.name),
          field('학부모 연락처', f.parent_phone, '번호가 같은 원생은 형제로 자동으로 묶입니다')
        ),
        field('반', classPicker, '반을 고르면 그 반 출석부와 수강료 청구에 들어갑니다'),
        h('details', { class: 'more-fields', open: hasMore },
          h('summary', {}, '더 적기 (학교 · 할인 · 메모)'),
          h('div', { class: 'inline-fields' },
            field('학교', f.school), field('학년', f.grade),
            field('학생 연락처', f.phone), field('등록일', f.joined_at),
            field('상태', f.status, '쉬는 원생은 "휴원", 그만둔 원생은 "퇴원"')
          ),
          h('div', { class: 'inline-fields' },
            field('할인', h('div', { class: 'row' }, h('div', { class: 'grow' }, f.discountValue), f.discountType), '수강료를 청구할 때 자동으로 빠집니다'),
            field('할인 이유', f.discountMemo)),
          fields.length ? h('div', {}, h('div', { class: 'card-title' }, '학습 기록'),
            h('div', { class: 'inline-fields' }, ...fields.map((cf) => field(cf.label, customInputs.get(cf.key))))) : null,
          field('메모', f.memo)
        )
      ),
      actions: [
        student ? {
          label: '원생 삭제', kind: 'danger', keepOpen: true, onClick: async (close) => {
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
            // 화면에 없는 기록(교재·진도 등)이 저장하면서 지워지지 않게 이어 붙인다
            const latest = student ? (repo.cache.studentById.get(student.id) || student) : null
            const custom = keepReserved(latest?.custom,
              normalizeValues(fields, Object.fromEntries([...customInputs].map(([k, el]) => [k, el.value]))))
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
              discount: Number(f.discountValue.value) > 0
                ? { type: f.discountType.value, value: Number(f.discountValue.value), memo: f.discountMemo.value.trim() }
                : null,
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
