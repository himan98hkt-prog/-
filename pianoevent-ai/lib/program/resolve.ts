import { applyOrder, buildProgram } from '@/lib/program/order'
import { DEFAULT_PROGRAM_OPTIONS, type EventStudent, type ProgramOptions, type ProgramPlan } from '@/lib/types'

/**
 * 저장된 순서가 있으면 그대로 쓰고, 없으면 규칙 엔진으로 미리보기를 만든다.
 * 서버 화면(인쇄·대본)과 클라이언트 화면이 같은 판단을 하도록 한곳에 모아 둔다.
 */
export function resolvePlan(
  students: EventStudent[],
  options: ProgramOptions = DEFAULT_PROGRAM_OPTIONS,
): { plan: ProgramPlan; saved: boolean } {
  if (students.length === 0) {
    return { plan: { items: [], breaks: [], play_sec: 0, total_sec: 0, warnings: [] }, saved: false }
  }

  const allOrdered = students.every((s) => s.order_no !== null)
  if (allOrdered) {
    const ids = [...students].sort((a, b) => (a.order_no ?? 0) - (b.order_no ?? 0)).map((s) => s.id)
    return { plan: applyOrder(students, ids, options), saved: true }
  }

  return { plan: buildProgram(students, options), saved: false }
}
