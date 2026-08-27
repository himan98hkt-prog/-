// 학부모 리포트 모달 — 월 선택 + 강사 코멘트 → Canvas 이미지 생성 → 공유/저장

import { h, modal, field, toast } from '../dom.js'
import { drawReportCard, shareReport } from '../report.js'
import * as repo from '../../data/repo.js'
import { monthRange, toMonth, toYmd } from '../../core/date.js'
import { summarize } from '../../core/attendance.js'
import { displayPairs } from '../../core/customfields.js'
import { decorate } from '../../core/fees.js'
import { currentUser } from '../session.js'

export function openReportModal(student) {
  const monthInput = h('input', { type: 'month', value: toMonth(toYmd()) })
  const comment = h('textarea', { placeholder: '예) 이번 달 수업 태도가 좋았고 진도도 계획대로 나갔습니다.' })
  const preview = h('div', { class: 'center', style: { minHeight: '160px', background: '#f9fafb', borderRadius: '12px', padding: '8px' } },
    h('span', { class: 'muted small' }, '미리보기를 눌러 리포트를 생성하세요'))
  let canvas = null

  async function build() {
    const month = monthInput.value
    const { from, to } = monthRange(month)
    const [att, pays] = await Promise.all([
      repo.attendanceOfStudentRange(student.id, from, to),
      repo.paymentsOfStudent(student.id, 36)
    ])
    const payment = pays.find((p) => p.month === month)
    const fields = repo.getSetting('customFields', [])
    const cls = repo.studentClasses(student.id)
    const teacher = cls.length ? repo.cache.userById.get(cls[0].teacher_id) : null

    canvas = await drawReportCard({
      student,
      month,
      className: cls.map((c) => c.name).join(', '),
      attendance: summarize(att),
      payment: payment ? decorate(payment) : null,
      customPairs: displayPairs(fields, student.custom || {}, 'report'),
      comment: comment.value.trim(),
      teacherName: teacher?.name || currentUser()?.name || ''
    })
    canvas.style.width = '100%'
    canvas.style.maxWidth = '340px'
    canvas.style.borderRadius = '10px'
    canvas.style.boxShadow = '0 6px 20px rgba(0,0,0,.15)'
    preview.replaceChildren(canvas)
  }

  modal({
    title: `${student.name} 학부모 리포트`,
    wide: true,
    body: h('div', {},
      h('div', { class: 'inline-fields' },
        field('대상 월', monthInput),
        field('담당 강사 코멘트', comment)
      ),
      h('div', { class: 'row', style: { marginBottom: '10px' } },
        h('button', { class: 'btn', onClick: build }, '미리보기 생성')
      ),
      preview
    ),
    actions: [
      {
        label: '이미지 공유/저장', kind: 'primary', keepOpen: true, onClick: async () => {
          if (!canvas) await build()
          const how = await shareReport(canvas, `${student.name}_${monthInput.value}_리포트.png`, `${repo.getSetting('branding')?.name || ''} 리포트`)
          toast(how === 'shared' ? '공유했습니다' : '이미지를 저장했습니다', 'ok')
          await repo.put('notices', {
            student_id: student.id, channel: 'report', template_id: 'report',
            sent_at: new Date().toISOString(), body: `${monthInput.value} 리포트`
          })
        }
      }
    ]
  })
}
