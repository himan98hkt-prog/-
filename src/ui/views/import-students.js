// 원생 명단 가져오기 — 엑셀/한글 표를 그대로 붙여넣거나 CSV 파일을 올린다.
//
// 새로 도입하는 원장의 첫 관문이 "명단 100명 손입력" 이다. 여기서 5분 안에 끝내는 것이 목표.
// 미리보기에서 중복(이미 등록된 이름+연락처)을 표시하고, 체크를 풀면 그 줄만 건너뛴다.

import { h, modal, toast, clear } from '../dom.js'
import * as repo from '../../data/repo.js'
import { parseStudentTable } from '../../core/csv.js'
import { toYmd } from '../../core/date.js'

export function openImportStudents({ onDone } = {}) {
  const paste = h('textarea', {
    class: 'msg',
    placeholder: '엑셀에서 표를 복사해 그대로 붙여넣으세요.\n예)\n이름\t학년\t학부모 연락처\t반\n김하늘\t초3\t010-1111-2222\t초등A'
  })
  const fileInput = h('input', { type: 'file', accept: '.csv,text/csv,text/plain' })
  const previewBox = h('div', { style: { maxHeight: '260px', overflow: 'auto' } })
  const summary = h('div', { class: 'small muted' })
  const skipDup = h('input', { type: 'checkbox', checked: true })
  const makeClasses = h('input', { type: 'checkbox', checked: true })

  let rows = []

  fileInput.addEventListener('change', async () => {
    const f = fileInput.files?.[0]
    if (!f) return
    paste.value = await f.text()
    analyze()
  })
  paste.addEventListener('input', () => analyze())
  skipDup.addEventListener('change', () => paintPreview())

  function analyze() {
    const res = parseStudentTable(paste.value, { existing: repo.cache.students })
    rows = res.rows.map((r) => ({ ...r, on: true }))
    summary.textContent = res.rows.length
      ? `${res.rows.length}명 인식${res.skipped.length ? ` · 건너뛴 줄 ${res.skipped.length}개` : ''}${res.hasHeader ? '' : ' · 헤더 없이 이름만 인식했습니다'}`
      : '아직 인식된 줄이 없습니다'
    paintPreview()
  }

  function usable() {
    return rows.filter((r) => r.on && !(skipDup.checked && r.duplicate))
  }

  function paintPreview() {
    clear(previewBox)
    if (!rows.length) {
      previewBox.append(h('p', { class: 'muted small' }, '붙여넣거나 CSV 파일을 선택하면 여기에 미리보기가 나옵니다'))
      return
    }
    for (const r of rows) {
      const cb = h('input', { type: 'checkbox', checked: r.on })
      cb.addEventListener('change', () => { r.on = cb.checked; paintPreview() })
      const dup = r.duplicate && skipDup.checked
      previewBox.append(h('label', { class: 'pick-row', style: dup ? { opacity: '.45' } : {} },
        cb,
        h('span', { class: 'grow' }, r.name,
          h('span', { class: 'small muted' }, ` ${[r.grade, r.school, r.className].filter(Boolean).join(' · ')}`)),
        h('span', { class: 'small muted' }, r.parent_phone || r.phone || ''),
        r.duplicate ? h('span', { class: 'badge warn' }, '이미 등록') : null))
    }
    const n = usable().length
    summary.textContent = `${n}명 등록 예정 (전체 ${rows.length}명)`
  }

  analyze()

  modal({
    wide: true,
    title: '원생 명단 가져오기',
    body: h('div', {},
      h('div', { class: 'small muted' },
        '엑셀에서 복사한 표(탭 구분) 또는 CSV 를 그대로 받습니다. 인식하는 열 이름: ',
        h('b', {}, '이름 · 학년 · 학교 · 학부모 연락처 · 학생 연락처 · 반 · 메모 · 등록일')),
      h('div', { style: { marginTop: '8px' } }, paste),
      h('div', { class: 'row', style: { marginTop: '8px' } },
        h('span', { class: 'small muted' }, 'CSV 파일:'), fileInput),
      h('div', { class: 'row wrap', style: { marginTop: '8px' } },
        h('label', { class: 'row', style: { gap: '6px' } }, skipDup, h('span', { class: 'small' }, '이미 등록된 원생 건너뛰기')),
        h('label', { class: 'row', style: { gap: '6px' } }, makeClasses, h('span', { class: 'small' }, '없는 반은 새로 만들어 배정'))),
      h('div', { class: 'card-title', style: { marginTop: '12px' } }, '미리보기'),
      previewBox,
      summary),
    actions: [
      {
        label: '가져오기', kind: 'primary', keepOpen: true, onClick: async (close) => {
          const list = usable()
          if (!list.length) return toast('등록할 원생이 없습니다', 'error')

          const classByName = new Map(repo.cache.classes.map((c) => [c.name.trim(), c]))
          for (const r of list) {
            const student = await repo.saveStudent({
              name: r.name,
              school: r.school,
              grade: r.grade,
              phone: r.phone,
              parent_phone: r.parent_phone,
              memo: r.memo,
              status: ['재원', '휴원', '퇴원'].includes(r.status) ? r.status : '재원',
              joined_at: r.joined_at || toYmd()
            })
            if (!r.className) continue
            let cls = classByName.get(r.className.trim())
            if (!cls && makeClasses.checked) {
              cls = await repo.put('classes', {
                name: r.className.trim(),
                subject_id: repo.cache.subjects[0]?.id || null,
                fee: 0,
                status: '운영',
                schedule: [],
                color: null
              })
              classByName.set(cls.name, cls)
            }
            if (cls) await repo.enroll(student.id, cls.id)
          }
          toast(`${list.length}명을 등록했습니다`, 'ok')
          onDone?.()
          close()
        }
      }
    ]
  })
}
