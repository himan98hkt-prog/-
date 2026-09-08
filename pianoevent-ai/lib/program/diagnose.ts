import { formatDuration } from '@/lib/format'
import type { ProgramPlan } from '@/lib/types'

/**
 * 순서표 정밀 진단.
 *
 * 순서표는 나왔는데 원장이 그 뒤에 눈으로 훑으며 확인하던 것들이 있다.
 * "같은 곡이 두 번 나오지 않나", "형제자매가 멀리 떨어져 학부모가 두 번 와야 하나",
 * "제일 어린 아이가 맨 뒤라 한 시간을 앉아 기다리나".
 * 이걸 놓치면 당일에 학부모 전화를 받는다. 그래서 기계가 먼저 본다.
 *
 * order.ts 의 warnings 는 순서 배치 단계에서 나오는 기본 경고이고,
 * 여기는 완성된 순서표를 놓고 하는 최종 점검이다.
 */

export type IssueLevel = 'high' | 'medium' | 'low'

export const ISSUE_LEVEL_LABEL: Record<IssueLevel, string> = {
  high: '반드시 확인',
  medium: '확인 권장',
  low: '참고',
}

export interface ProgramIssue {
  id: string
  level: IssueLevel
  title: string
  /** 무엇이 문제인지 */
  detail: string
  /** 원장이 바로 할 수 있는 조치 */
  fix: string
  /** 관련된 순서 번호 */
  order_nos: number[]
}

/** 성이 같고 순서가 멀면 형제자매일 가능성이 있다 — 한국 이름 기준 첫 글자 */
function familyKey(name: string): string {
  const trimmed = name.trim()
  return trimmed.length >= 2 ? trimmed[0] : trimmed
}

function normalizePiece(title: string): string {
  return title.trim().toLowerCase().replace(/\s+/g, ' ')
}

export function diagnoseProgram(plan: ProgramPlan): ProgramIssue[] {
  const issues: ProgramIssue[] = []
  const items = plan.items
  if (items.length === 0) return issues

  // ── 같은 곡 중복 ────────────────────────────────────────────
  const byPiece = new Map<string, typeof items>()
  for (const item of items) {
    const key = normalizePiece(item.student.piece_title)
    if (!key) continue
    byPiece.set(key, [...(byPiece.get(key) ?? []), item])
  }
  for (const [, group] of byPiece) {
    if (group.length < 2) continue
    // 연탄·듀엣은 두 사람이 같은 곡을 치는 게 정상이다. 순서가 붙어 있으면 중복이 아니다.
    const allEnsemble = group.every((g) => g.student.level === 'ensemble')
    const adjacent = Math.max(...group.map((g) => g.order_no)) - Math.min(...group.map((g) => g.order_no)) === group.length - 1
    if (allEnsemble && adjacent) continue
    issues.push({
      id: `dup-piece-${group[0].order_no}`,
      level: 'medium',
      title: '같은 곡이 두 번 이상 연주됩니다',
      detail: `${group[0].student.piece_title} — ${group.map((g) => `${g.order_no}번 ${g.student.student_name}`).join(', ')}`,
      fix: '순서를 멀리 떨어뜨리거나, 한 명은 다른 곡으로 바꾸는 편이 관객에게 낫습니다.',
      order_nos: group.map((g) => g.order_no),
    })
  }

  // ── 형제자매 추정 분리 ──────────────────────────────────────
  const byFamily = new Map<string, typeof items>()
  for (const item of items) {
    const key = familyKey(item.student.student_name)
    if (!key) continue
    byFamily.set(key, [...(byFamily.get(key) ?? []), item])
  }
  for (const [surname, group] of byFamily) {
    if (group.length < 2) continue
    const first = Math.min(...group.map((g) => g.order_no))
    const last = Math.max(...group.map((g) => g.order_no))
    if (last - first < 6) continue
    issues.push({
      id: `family-split-${surname}`,
      level: 'medium',
      title: '형제자매일 수 있는 학생이 멀리 떨어져 있습니다',
      detail: `${group.map((g) => `${g.order_no}번 ${g.student.student_name}`).join(', ')} — ${last - first}순서 차이`,
      fix: '같은 집 아이라면 순서를 붙여 주세요. 학부모가 한 번 와서 두 무대를 다 봅니다.',
      order_nos: group.map((g) => g.order_no),
    })
  }

  // ── 어린 학생이 뒤쪽 순서 ───────────────────────────────────
  const half = Math.ceil(items.length / 2)
  const lateBeginners = items.filter((i) => i.student.level === 'beginner' && i.order_no > half)
  if (lateBeginners.length > 0 && items.length >= 8) {
    issues.push({
      id: 'late-beginner',
      level: lateBeginners.length >= 3 ? 'high' : 'medium',
      title: '기초·초급 학생이 후반부에 있습니다',
      detail: `${lateBeginners.map((i) => `${i.order_no}번 ${i.student.student_name}`).join(', ')} — 앞 순서를 앉아서 기다려야 합니다.`,
      fix: '어린 학생은 앞쪽에 두는 편이 안전합니다. 연주가 끝나면 객석에서 편하게 볼 수 있습니다.',
      order_nos: lateBeginners.map((i) => i.order_no),
    })
  }

  // ── 같은 작곡가 연속 ───────────────────────────────────────
  for (let i = 2; i < items.length; i += 1) {
    const composers = [items[i - 2], items[i - 1], items[i]].map((x) => x.student.composer.trim())
    if (!composers[0] || composers.some((c) => c !== composers[0])) continue
    issues.push({
      id: `composer-run-${items[i - 2].order_no}`,
      level: 'low',
      title: '같은 작곡가가 세 곡 연속입니다',
      detail: `${items[i - 2].order_no}~${items[i].order_no}번 모두 ${composers[0]}`,
      fix: '한 곡만 뒤로 옮겨도 프로그램이 훨씬 다채롭게 들립니다.',
      order_nos: [items[i - 2].order_no, items[i - 1].order_no, items[i].order_no],
    })
  }

  // ── 긴 곡이 몰려 있음 ──────────────────────────────────────
  const avg = items.reduce((s, i) => s + i.duration_sec, 0) / items.length
  for (let i = 1; i < items.length; i += 1) {
    const a = items[i - 1]
    const b = items[i]
    if (a.duration_sec > avg * 1.6 && b.duration_sec > avg * 1.6) {
      issues.push({
        id: `long-run-${a.order_no}`,
        level: 'low',
        title: '긴 곡이 연달아 있습니다',
        detail: `${a.order_no}번 ${formatDuration(a.duration_sec)} · ${b.order_no}번 ${formatDuration(b.duration_sec)} (평균 ${formatDuration(Math.round(avg))})`,
        fix: '사이에 짧은 곡을 하나 넣으면 객석 집중이 유지됩니다.',
        order_nos: [a.order_no, b.order_no],
      })
    }
  }

  // ── 마무리가 약함 ──────────────────────────────────────────
  const last = items[items.length - 1]
  if (items.length >= 6 && last.duration_sec < avg * 0.7) {
    issues.push({
      id: 'weak-finale',
      level: 'medium',
      title: '마지막 곡이 평균보다 짧습니다',
      detail: `${last.order_no}번 ${last.student.student_name} · ${formatDuration(last.duration_sec)}`,
      fix: '피날레는 길고 화려한 곡이나 앙상블로 두면 박수가 자연스럽게 커집니다.',
      order_nos: [last.order_no],
    })
  }

  // ── 휴식 없이 너무 김 ──────────────────────────────────────
  if (plan.breaks.length === 0 && plan.total_sec > 70 * 60) {
    issues.push({
      id: 'no-break',
      level: 'high',
      title: '휴식 없이 70분을 넘습니다',
      detail: `예상 러닝타임 ${Math.round(plan.total_sec / 60)}분`,
      fix: '중간 휴식 10분을 넣으세요. 유아 동반 학부모가 나갔다 들어올 수 있어야 합니다.',
      order_nos: [],
    })
  }

  // ── 멘트가 비어 있음 ───────────────────────────────────────
  const noScript = items.filter((i) => !i.student.mc_script?.trim())
  if (noScript.length > 0) {
    issues.push({
      id: 'missing-script',
      level: noScript.length === items.length ? 'high' : 'medium',
      title: '사회자 멘트가 없는 순서가 있습니다',
      detail: `${noScript.length}곡 — ${noScript.slice(0, 5).map((i) => `${i.order_no}번`).join(', ')}${noScript.length > 5 ? ' 외' : ''}`,
      fix: '순서표 화면에서 [사회자 대본 만들기]를 누르면 한 번에 채워집니다.',
      order_nos: noScript.map((i) => i.order_no),
    })
  }

  const rank: Record<IssueLevel, number> = { high: 0, medium: 1, low: 2 }
  return issues.sort((a, b) => rank[a.level] - rank[b.level] || a.order_nos[0] - b.order_nos[0])
}

export function issueSummary(issues: ProgramIssue[]): string {
  if (issues.length === 0) return '점검 결과 문제 없음'
  const high = issues.filter((i) => i.level === 'high').length
  const medium = issues.filter((i) => i.level === 'medium').length
  const parts: string[] = []
  if (high) parts.push(`반드시 확인 ${high}건`)
  if (medium) parts.push(`확인 권장 ${medium}건`)
  const low = issues.length - high - medium
  if (low) parts.push(`참고 ${low}건`)
  return parts.join(' · ')
}
