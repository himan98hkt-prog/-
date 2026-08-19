// 현황 탭 — 월별 매출·원생 증감·출석률(집계 캐시 사용) + 이탈 위험 감지

import { h, clear, toast } from '../dom.js'
import { formatWon } from '../../core/fees.js'
import { toMonth, toYmd, addMonths, lastNWeeks } from '../../core/date.js'
import { detectRisk, RISK_LEVEL } from '../../core/risk.js'
import { openNoticeModal } from './notice-modal.js'

export async function render(root, ctx) {
  const { repo } = ctx
  const month = toMonth(toYmd())
  const months = Array.from({ length: 6 }, (_, i) => addMonths(month, -(5 - i)))

  const statBox = h('div', { class: 'grid cols4' })
  const chartBox = h('div')
  const riskBox = h('div')
  const refreshBtn = h('button', {
    class: 'btn sm right', onClick: async () => {
      refreshBtn.disabled = true
      refreshBtn.textContent = '집계 중…'
      for (const m of months) await repo.recomputeMonth(m)
      await load()
      refreshBtn.disabled = false
      refreshBtn.textContent = '집계 새로고침'
      toast('통계를 다시 계산했습니다', 'ok')
    }
  }, '집계 새로고침')

  root.append(
    h('div', { class: 'card' }, h('div', { class: 'row' }, h('div', { class: 'card-title', style: { margin: 0 } }, `${month} 현황`), refreshBtn), statBox),
    h('div', { class: 'card', style: { marginTop: '12px' } }, h('div', { class: 'card-title' }, '최근 6개월'), chartBox),
    h('div', { class: 'card', style: { marginTop: '12px' } }, h('div', { class: 'card-title' }, '이탈 위험 원생'), riskBox)
  )

  async function load() {
    const stats = await repo.statsRange(months)
    const cur = stats[stats.length - 1]

    clear(statBox)
    statBox.append(
      stat('이번 달 수납', formatWon(cur.collected)),
      stat('미수금', formatWon(cur.outstanding), cur.outstanding ? 'danger' : ''),
      stat('순이익', formatWon(cur.net)),
      stat('출석률', `${cur.attendanceRate}%`),
      stat('재원생', `${cur.activeStudents}명`),
      stat('신규 등록', `+${cur.joined}`),
      stat('퇴원', `-${cur.left}`, cur.left ? 'danger' : ''),
      stat('미납 건수', `${cur.unpaidCount}건`)
    )

    clear(chartBox)
    const maxRev = Math.max(1, ...stats.map((s) => s.collected))
    for (const s of stats) {
      chartBox.append(h('div', { class: 'row', style: { gap: '10px', marginBottom: '8px' } },
        h('span', { class: 'small muted', style: { width: '62px' } }, s.month.slice(2)),
        h('div', { class: 'grow' },
          h('div', { class: 'progressbar' }, h('div', { style: { width: `${(s.collected / maxRev) * 100}%` } }))),
        h('span', { class: 'small', style: { width: '110px', textAlign: 'right' } }, formatWon(s.collected)),
        h('span', { class: 'small muted', style: { width: '86px', textAlign: 'right' } }, `출석 ${s.attendanceRate}%`),
        h('span', { class: 'small muted', style: { width: '76px', textAlign: 'right' } }, `원생 ${s.activeStudents}`)
      ))
    }

    // 이탈 위험 — 최근 4주 출결 + 최근 2개월 수납 + 상담 이력
    const today = toYmd()
    const { from, to } = lastNWeeks(today, 4)
    const [att, payThis, payPrev, counsel] = await Promise.all([
      repo.attendanceOfRange(from, to),
      repo.paymentsOfMonth(month),
      repo.paymentsOfMonth(addMonths(month, -1)),
      repo.counselRecent(500)
    ])
    const risks = detectRisk({
      students: repo.cache.students,
      attendance: att,
      counselLogs: counsel,
      payments: [...payThis, ...payPrev],
      today
    }).filter((r) => r.level !== RISK_LEVEL.LOW).slice(0, 20)

    clear(riskBox)
    if (!risks.length) {
      riskBox.append(h('p', { class: 'muted small' }, '위험 신호가 감지된 원생이 없습니다 👍'))
      return
    }
    for (const r of risks) {
      const student = repo.cache.studentById.get(r.student_id)
      riskBox.append(h('div', { class: 'row', style: { padding: '10px 0', borderBottom: '1px solid var(--line)' } },
        h('span', { class: `badge ${r.level === RISK_LEVEL.HIGH ? 'danger' : 'warn'}` }, r.level),
        h('div', { class: 'grow' },
          h('b', {}, r.name),
          h('div', { class: 'small muted' }, r.reasons.join(' · '))),
        h('span', { class: 'small muted' }, `${r.score}점`),
        student ? h('button', { class: 'btn sm', onClick: () => openNoticeModal({ student, templateId: 'absent' }) }, '연락') : null
      ))
    }
  }

  function stat(label, value, kind = '') {
    return h('div', { class: 'stat' },
      h('div', { class: 'v', style: kind === 'danger' ? { color: 'var(--danger)' } : {} }, value),
      h('div', { class: 'l' }, label))
  }

  await load()
  return () => {}
}
