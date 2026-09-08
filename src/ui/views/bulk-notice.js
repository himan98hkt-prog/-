// 일괄 안내 — 미납·결석 대상을 한 번에 골라 문구를 만들고, 복사·CSV·문자앱으로 넘긴다.
//
// 원장이 매달 반복하는 "미납자 20명에게 같은 문자 보내기" 를 한 화면에서 끝내는 것이 목적이다.
// 실제 발송은 문자·카톡 앱이 한다(자동 발송은 통신사 정책상 범위 밖). 발송 이력은 남긴다.

import { h, modal, toast, copyText, clear } from '../dom.js'
import * as repo from '../../data/repo.js'
import { DEFAULT_TEMPLATES, renderTemplate } from '../../core/templates.js'
import { toMonth, toYmd } from '../../core/date.js'
import { formatWon } from '../../core/fees.js'
import { downloadCsv } from '../../core/csv.js'

/**
 * @param {object} opts
 * @param {string[]} opts.studentIds
 * @param {string} [opts.templateId]
 * @param {string} [opts.month]
 * @param {Object<string, number>} [opts.amounts]  원생별 금액(미납 안내용)
 * @param {string} [opts.title]
 */
export function openBulkNotice({ studentIds = [], templateId = 'absent', month, amounts = {}, title } = {}) {
  const templates = repo.getSetting('templates', DEFAULT_TEMPLATES)
  const brand = repo.getSetting('branding') || {}
  const m = month || toMonth(toYmd())
  let current = templates.find((t) => t.id === templateId) || templates[0]

  const targets = studentIds
    .map((id) => repo.cache.studentById.get(id))
    .filter(Boolean)
    .map((s) => ({ student: s, on: true }))

  const listBox = h('div', { style: { maxHeight: '240px', overflow: 'auto' } })
  const preview = h('textarea', { class: 'msg', readonly: true })
  const chips = h('div', { class: 'row wrap' })
  const summary = h('div', { class: 'small muted' })

  const phoneOf = (s) => (s.parent_phone || s.phone || '').trim()

  function messageFor(s) {
    const cls = repo.studentClasses(s.id)
    const teacher = cls.length ? repo.cache.userById.get(cls[0].teacher_id) : null
    return renderTemplate(current.body, {
      '{원생명}': s.name,
      '{학원명}': brand.name || '학원',
      '{반}': cls.map((c) => c.name).join(', '),
      '{과목}': cls.map((c) => repo.cache.subjectById.get(c.subject_id)?.name).filter(Boolean).join(', '),
      '{금액}': amounts[s.id] != null ? formatWon(amounts[s.id]) : '',
      '{월}': `${Number(m.slice(5, 7))}월`,
      '{날짜}': toYmd(),
      '{강사}': teacher?.name || ''
    })
  }

  const chosen = () => targets.filter((t) => t.on).map((t) => t.student)

  function paint() {
    chips.replaceChildren(...templates.map((t) => h('button', {
      class: `chip ${t.id === current.id ? 'active' : ''}`,
      onClick: () => { current = t; paint() }
    }, t.name)))

    clear(listBox)
    for (const row of targets) {
      const cb = h('input', { type: 'checkbox', checked: row.on })
      cb.addEventListener('change', () => { row.on = cb.checked; paint() })
      const phone = phoneOf(row.student)
      listBox.append(h('label', { class: 'pick-row' },
        cb,
        h('span', { class: 'grow' }, row.student.name,
          amounts[row.student.id] != null
            ? h('span', { class: 'small muted' }, ` · ${formatWon(amounts[row.student.id])}`)
            : null),
        h('span', { class: `small ${phone ? 'muted' : ''}`, style: phone ? {} : { color: 'var(--danger)' } },
          phone || '연락처 없음')))
    }

    const list = chosen()
    const noPhone = list.filter((s) => !phoneOf(s)).length
    summary.textContent = `${list.length}명 선택${noPhone ? ` · 연락처 없는 원생 ${noPhone}명` : ''}`
    preview.value = list.length ? messageFor(list[0]) : ''
  }
  paint()

  const toggleAll = (on) => { targets.forEach((t) => { t.on = on }); paint() }

  async function logSent(list) {
    if (!list.length) return
    await repo.putMany('notices', list.map((s) => ({
      student_id: s.id,
      channel: 'bulk-text',
      template_id: current.id,
      sent_at: new Date().toISOString(),
      body: messageFor(s)
    })))
  }

  modal({
    wide: true,
    title: title || `일괄 안내 (${targets.length}명)`,
    body: h('div', {},
      h('div', { class: 'row wrap', style: { marginBottom: '8px' } },
        chips,
        h('span', { class: 'right' }),
        h('button', { class: 'btn sm', onClick: () => toggleAll(true) }, '전체 선택'),
        h('button', { class: 'btn sm', onClick: () => toggleAll(false) }, '전체 해제')),
      listBox,
      summary,
      h('div', { style: { marginTop: '10px' } },
        h('div', { class: 'small muted', style: { marginBottom: '4px' } }, '미리보기 (첫 번째 대상 기준 — 이름·금액은 각자 값으로 바뀝니다)'),
        preview),
      h('p', { class: 'small muted' },
        '문구를 복사해 문자·카톡에 붙여넣어 발송하세요. 누르는 순간 발송 이력이 기록되어 "누구에게 보냈는지" 가 남습니다.')),
    actions: [
      {
        label: '번호만 복사', keepOpen: true, onClick: async () => {
          const phones = chosen().map(phoneOf).filter(Boolean)
          if (!phones.length) return toast('연락처가 있는 대상이 없습니다', 'error')
          await copyText(phones.join(', '))
          toast(`${phones.length}개 번호를 복사했습니다`, 'ok')
        }
      },
      {
        label: 'CSV 저장', keepOpen: true, onClick: async () => {
          const list = chosen()
          if (!list.length) return toast('대상을 선택해 주세요', 'error')
          downloadCsv(`안내_${current.id}_${toYmd()}.csv`,
            ['이름', '연락처', '금액', '문구'],
            list.map((s) => [s.name, phoneOf(s), amounts[s.id] ?? '', messageFor(s)]))
          await logSent(list)
          toast('CSV로 저장했습니다', 'ok')
        }
      },
      {
        label: '문자앱 열기', keepOpen: true, onClick: async () => {
          const list = chosen()
          const phones = list.map(phoneOf).filter(Boolean)
          if (!phones.length) return toast('연락처가 있는 대상이 없습니다', 'error')
          const body = encodeURIComponent(preview.value)
          location.href = `sms:${phones.join(',')}${/iPhone|iPad|Macintosh/.test(navigator.userAgent) ? '&' : '?'}body=${body}`
          await logSent(list)
        }
      },
      {
        label: '전체 문구 복사', kind: 'primary', keepOpen: true, onClick: async () => {
          const list = chosen()
          if (!list.length) return toast('대상을 선택해 주세요', 'error')
          const text = list.map((s) => `── ${s.name} ${phoneOf(s)}\n${messageFor(s)}`).join('\n\n')
          await copyText(text)
          await logSent(list)
          toast(`${list.length}명분 문구를 복사했습니다`, 'ok')
        }
      }
    ]
  })
}
