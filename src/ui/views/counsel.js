// 상담 탭 — 상담일지 + 입회상담 → 등록 전환 퍼널

import { h, clear, toast, modal, field, confirmDialog } from '../dom.js'
import { COUNSEL_TYPES, FUNNEL_STAGES } from '../../data/repo.js'
import { toMonth, toYmd } from '../../core/date.js'

export async function render(root, ctx) {
  const { repo, user } = ctx
  const canWrite = ctx.can('counsel:write')
  let month = toMonth(toYmd())

  const funnelBox = h('div', { class: 'grid cols4' })
  const listBox = h('div')
  const monthInput = h('input', { type: 'month', value: month, style: { maxWidth: '160px' }, onChange: (e) => { month = e.target.value; load() } })

  root.append(
    h('div', { class: 'card' },
      h('div', { class: 'row wrap' },
        h('div', { class: 'card-title', style: { margin: 0 } }, '입회 상담 퍼널'),
        monthInput,
        canWrite ? h('button', { class: 'btn primary right', onClick: () => openEditor() }, '+ 상담 기록') : null
      ),
      h('div', { style: { marginTop: '10px' } }, funnelBox)
    ),
    h('div', { class: 'card', style: { marginTop: '12px' } }, h('div', { class: 'card-title' }, '최근 상담일지'), listBox)
  )

  async function load() {
    const funnel = await repo.counselFunnel(month)
    clear(funnelBox)
    for (const stage of FUNNEL_STAGES) {
      funnelBox.append(h('div', { class: 'stat' },
        h('div', { class: 'v' }, `${funnel.counts[stage] || 0}`),
        h('div', { class: 'l' }, stage)))
    }
    funnelBox.append(h('div', { class: 'stat' },
      h('div', { class: 'v', style: { color: 'var(--brand)' } }, `${funnel.conversion}%`),
      h('div', { class: 'l' }, `등록 전환율 (상담 ${funnel.total}건)`)))

    const rows = await repo.counselRecent(120)
    clear(listBox)
    if (!rows.length) { listBox.append(h('p', { class: 'muted small' }, '상담 기록이 없습니다')); return }
    for (const c of rows) {
      const st = repo.cache.studentById.get(c.student_id)
      listBox.append(h('div', {
        class: 'row', style: { padding: '10px 0', borderBottom: '1px solid var(--line)', alignItems: 'flex-start', cursor: canWrite ? 'pointer' : 'default' },
        onClick: () => canWrite && openEditor(c)
      },
        h('div', { class: 'grow' },
          h('div', { class: 'row', style: { gap: '6px' } },
            h('b', {}, st?.name || '(비원생)'),
            h('span', { class: 'badge' }, c.type),
            c.type === '입회상담' ? h('span', { class: `badge ${c.stage === '등록' ? 'ok' : c.stage === '보류' ? 'danger' : 'brand'}` }, c.stage || '상담중') : null),
          h('div', { class: 'small' }, c.content || ''),
          c.next_action ? h('div', { class: 'small', style: { color: 'var(--warn)' } }, `다음 액션: ${c.next_action}`) : null),
        h('span', { class: 'small muted' }, String(c.created_at || '').slice(0, 10))
      ))
    }
  }

  function openEditor(log = null) {
    const student = h('select', {}, h('option', { value: '' }, '원생 선택(입회 전이면 비워 두세요)'),
      ...repo.cache.students.map((s) => h('option', { value: s.id, selected: log?.student_id === s.id }, `${s.name} ${s.grade || ''}`)))
    const type = h('select', {}, ...COUNSEL_TYPES.map((t) => h('option', { value: t, selected: log?.type === t }, t)))
    const stage = h('select', {}, ...FUNNEL_STAGES.map((s) => h('option', { value: s, selected: (log?.stage || '상담중') === s }, s)))
    const content = h('textarea', { value: log?.content || '' })
    const next = h('input', { type: 'text', value: log?.next_action || '' })
    const date = h('input', { type: 'date', value: String(log?.created_at || new Date().toISOString()).slice(0, 10) })

    modal({
      title: log ? '상담 기록 수정' : '상담 기록',
      body: h('div', {},
        h('div', { class: 'inline-fields' }, field('원생', student), field('상담 종류', type), field('진행 단계', stage), field('상담일', date)),
        field('상담 내용', content),
        field('다음 액션', next, '예) 2주 뒤 재상담, 체험 수업 안내')
      ),
      actions: [
        log ? {
          label: '삭제', kind: 'danger', keepOpen: true, onClick: async (close) => {
            if (!await confirmDialog('이 상담 기록을 삭제할까요?', { danger: true, okLabel: '삭제' })) return false
            await repo.remove('counselLogs', log.id)
            await load()
            close()
          }
        } : null,
        {
          label: '저장', kind: 'primary', onClick: async () => {
            await repo.put('counselLogs', {
              ...(log || {}),
              student_id: student.value || null,
              type: type.value,
              stage: stage.value,
              content: content.value.trim(),
              next_action: next.value.trim(),
              created_by: user?.id || null,
              created_at: `${date.value}T09:00:00.000Z`
            })
            await load()
            toast('저장했습니다', 'ok')
          }
        }
      ].filter(Boolean)
    })
  }

  await load()
  return () => {}
}
