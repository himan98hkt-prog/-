// 알림 문구 생성 — 템플릿 + 변수 치환 → 클립보드 복사 / Web Share (자동 발송은 범위 외)

import { h, modal, field, toast, copyText } from '../dom.js'
import * as repo from '../../data/repo.js'
import { DEFAULT_TEMPLATES, renderTemplate, missingVars } from '../../core/templates.js'
import { toMonth, toYmd, monthRange } from '../../core/date.js'
import { formatWon } from '../../core/fees.js'
import { summarize } from '../../core/attendance.js'

export async function openNoticeModal({ student, templateId = 'absent', extra = {} }) {
  const templates = repo.getSetting('templates', DEFAULT_TEMPLATES)
  const branding = repo.getSetting('branding') || {}
  const month = extra.month || toMonth(toYmd())
  const cls = repo.studentClasses(student.id)
  const teacher = cls.length ? repo.cache.userById.get(cls[0].teacher_id) : null
  const { from, to } = monthRange(month)
  const att = summarize(await repo.attendanceOfStudentRange(student.id, from, to))

  const vars = {
    '{원생명}': student.name,
    '{학원명}': branding.name || '학원',
    '{반}': cls.map((c) => c.name).join(', '),
    '{과목}': cls.map((c) => repo.cache.subjectById.get(c.subject_id)?.name).filter(Boolean).join(', '),
    '{금액}': extra.amount != null ? formatWon(extra.amount) : '',
    '{월}': `${Number(month.slice(5, 7))}월`,
    '{날짜}': extra.date || toYmd(),
    '{출석률}': String(att.rate),
    '{강사}': teacher?.name || '',
    ...extra.vars
  }

  let current = templates.find((t) => t.id === templateId) || templates[0]
  const output = h('textarea', { style: { minHeight: '150px' } })
  const warn = h('div', { class: 'small', style: { color: 'var(--warn)' } })
  const chips = h('div', { class: 'row wrap' })

  const paint = () => {
    output.value = renderTemplate(current.body, vars)
    const miss = missingVars(output.value)
    warn.textContent = miss.length ? `값이 비어 있는 항목: ${miss.join(' ')} — 직접 채워 주세요` : ''
    chips.replaceChildren(...templates.map((t) => h('button', {
      class: `chip ${t.id === current.id ? 'active' : ''}`,
      onClick: () => { current = t; paint() }
    }, t.name)))
  }
  paint()

  modal({
    title: `${student.name} 알림 문구`,
    body: h('div', {}, field('템플릿', chips), field('보낼 문구', output), warn,
      h('p', { class: 'small muted' }, '문구를 복사해 문자·카톡에 붙여넣어 발송하세요. 발송 이력은 자동으로 기록됩니다.')),
    actions: [
      {
        label: '공유', keepOpen: true, onClick: async () => {
          if (navigator.share) {
            await navigator.share({ text: output.value })
            await logNotice()
            toast('공유했습니다', 'ok')
          } else {
            toast('이 브라우저는 공유를 지원하지 않습니다. 복사를 이용해 주세요')
          }
        }
      },
      {
        label: '복사', kind: 'primary', keepOpen: true, onClick: async () => {
          await copyText(output.value)
          await logNotice()
          toast('복사했습니다', 'ok')
        }
      }
    ]
  })

  async function logNotice() {
    await repo.put('notices', {
      student_id: student.id,
      channel: 'text',
      template_id: current.id,
      sent_at: new Date().toISOString(),
      body: output.value
    })
  }
}
