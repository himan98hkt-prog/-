// 현황 탭 — 월별 매출·원생 증감·출석률(집계 캐시) + 이탈 위험 감지
//
// 렌더 전략: 캐시된 집계로 "먼저 그리고", 빠진 달과 이탈 위험은 백그라운드에서 채운다.
// 20만 건 규모에서 첫 진입 시 6개월치를 한 번에 계산하면 2초가 넘어가기 때문이다.

import { h, clear, toast } from '../dom.js'
import { formatWon } from '../../core/fees.js'
import { toMonth, toYmd, addMonths, lastNWeeks } from '../../core/date.js'
import { detectRisk, RISK_LEVEL } from '../../core/risk.js'
import { openNoticeModal } from './notice-modal.js'

export async function render(root, ctx) {
  const { repo } = ctx
  const month = toMonth(toYmd())
  const months = Array.from({ length: 6 }, (_, i) => addMonths(month, -(5 - i)))
  let cancelled = false

  const statBox = h('div', { class: 'grid cols4' })
  const chartBox = h('div')
  const riskBox = h('div', { class: 'muted small' }, '분석 중…')
  const note = h('span', { class: 'small muted' })
  const refreshBtn = h('button', {
    class: 'btn sm', onClick: async () => {
      refreshBtn.disabled = true
      refreshBtn.textContent = '집계 중…'
      for (const m of months) {
        if (cancelled) return
        await repo.recomputeMonth(m)
      }
      await hydrate(true)
      refreshBtn.disabled = false
      refreshBtn.textContent = '집계 새로고침'
      toast('통계를 다시 계산했습니다', 'ok')
    }
  }, '집계 새로고침')

  root.append(
    h('div', { class: 'card' },
      h('div', { class: 'row' }, h('div', { class: 'card-title', style: { margin: 0 } }, `${month} 현황`), note, h('span', { class: 'right' }, refreshBtn)),
      statBox),
    h('div', { class: 'card', style: { marginTop: '12px' } }, h('div', { class: 'card-title' }, '최근 6개월'), chartBox),
    h('div', { class: 'card', style: { marginTop: '12px' } }, h('div', { class: 'card-title' }, '이탈 위험 원생'), riskBox)
  )

  // 1차 페인트: 캐시에 있는 것만 (즉시)
  let stats = await repo.cachedStats(months)
  paint()

  // 2차: 빠진 달과 위험 분석은 화면을 넘긴 뒤에 채운다
  setTimeout(() => hydrate().catch((e) => console.warn(e)), 0)

  async function hydrate(force = false) {
    if (force) stats = await repo.cachedStats(months)
    for (let i = months.length - 1; i >= 0; i--) {
      if (cancelled) return
      if (stats[i]) continue
      note.textContent = `${months[i]} 집계 중…`
      stats[i] = await repo.monthlyStats(months[i])
      paint()
      await new Promise((r) => setTimeout(r, 0)) // 브라우저에 렌더 기회를 준다
    }
    note.textContent = ''
    if (!cancelled) await loadRisk()
  }

  function paint() {
    const cur = stats[stats.length - 1] || {}
    clear(statBox)
    statBox.append(
      stat('이번 달 수납', money(cur.collected)),
      stat('미수금', money(cur.outstanding), cur.outstanding ? 'danger' : ''),
      stat('순이익', money(cur.net)),
      stat('출석률', cur.attendanceRate == null ? '…' : `${cur.attendanceRate}%`),
      stat('재원생', cur.activeStudents == null ? '…' : `${cur.activeStudents}명`),
      stat('신규 등록', cur.joined == null ? '…' : `+${cur.joined}`),
      stat('퇴원', cur.left == null ? '…' : `-${cur.left}`, cur.left ? 'danger' : ''),
      stat('미납 건수', cur.unpaidCount == null ? '…' : `${cur.unpaidCount}건`)
    )

    clear(chartBox)
    const maxRev = Math.max(1, ...stats.map((s) => s?.collected || 0))
    stats.forEach((s, i) => {
      chartBox.append(h('div', { class: 'row', style: { gap: '10px', marginBottom: '8px' } },
        h('span', { class: 'small muted', style: { width: '62px' } }, months[i].slice(2)),
        h('div', { class: 'grow' },
          h('div', { class: 'progressbar' }, h('div', { style: { width: `${((s?.collected || 0) / maxRev) * 100}%` } }))),
        h('span', { class: 'small', style: { width: '110px', textAlign: 'right' } }, s ? formatWon(s.collected) : '집계 대기'),
        h('span', { class: 'small muted', style: { width: '86px', textAlign: 'right' } }, s ? `출석 ${s.attendanceRate}%` : ''),
        h('span', { class: 'small muted', style: { width: '76px', textAlign: 'right' } }, s ? `원생 ${s.activeStudents}` : '')
      ))
    })
  }

  async function loadRisk() {
    const today = toYmd()
    const { from, to } = lastNWeeks(today, 4)
    const [att, payThis, payPrev, counsel] = await Promise.all([
      repo.attendanceOfRange(from, to),
      repo.paymentsOfMonth(month),
      repo.paymentsOfMonth(addMonths(month, -1)),
      repo.counselRecent(500)
    ])
    if (cancelled) return
    const risks = detectRisk({
      students: repo.cache.students,
      attendance: att,
      counselLogs: counsel,
      payments: [...payThis, ...payPrev],
      today
    }).filter((r) => r.level !== RISK_LEVEL.LOW).slice(0, 20)

    clear(riskBox)
    riskBox.className = ''
    if (!risks.length) {
      riskBox.append(h('p', { class: 'muted small' }, '위험 신호가 감지된 원생이 없습니다 👍'))
      return
    }
    for (const r of risks) {
      const student = repo.cache.studentById.get(r.student_id)
      riskBox.append(h('div', { class: 'row', style: { padding: '10px 0', borderBottom: '1px solid var(--line)' } },
        h('span', { class: `badge ${r.level === RISK_LEVEL.HIGH ? 'danger' : 'warn'}` }, r.level),
        h('div', { class: 'grow' }, h('b', {}, r.name), h('div', { class: 'small muted' }, r.reasons.join(' · '))),
        h('span', { class: 'small muted' }, `${r.score}점`),
        student ? h('button', { class: 'btn sm', onClick: () => openNoticeModal({ student, templateId: 'absent' }) }, '연락') : null
      ))
    }
  }

  function money(v) {
    return v == null ? '…' : formatWon(v)
  }

  function stat(label, value, kind = '') {
    return h('div', { class: 'stat' },
      h('div', { class: 'v', style: kind === 'danger' ? { color: 'var(--danger)' } : {} }, value),
      h('div', { class: 'l' }, label))
  }

  return () => { cancelled = true }
}
