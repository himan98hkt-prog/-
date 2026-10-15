import { fail, guard, ok, readJson } from '@/lib/http'
import { generateProgram } from '@/lib/program/ai'
import { getRepository } from '@/lib/store'
import { DEFAULT_PROGRAM_OPTIONS, type ProgramOptions } from '@/lib/types'

export const maxDuration = 60

function readOptions(body: Record<string, unknown>): ProgramOptions {
  const num = (v: unknown, fallback: number, max: number) => {
    const n = Number(v)
    return Number.isFinite(n) && n >= 0 && n <= max ? Math.round(n) : fallback
  }
  return {
    turnover_sec: num(body.turnover_sec, DEFAULT_PROGRAM_OPTIONS.turnover_sec, 300),
    intermission_after_sec: num(body.intermission_after_sec, DEFAULT_PROGRAM_OPTIONS.intermission_after_sec, 4 * 3600),
    intermission_sec: num(body.intermission_sec, DEFAULT_PROGRAM_OPTIONS.intermission_sec, 3600),
    max_total_sec: num(body.max_total_sec, DEFAULT_PROGRAM_OPTIONS.max_total_sec, 6 * 3600),
  }
}

/** 연주 순서 + 사회자 대본을 생성하고 DB 에 확정 저장한다 */
export async function POST(req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const repo = getRepository()
    const event = await repo.getEvent(params.id)
    if (!event) return fail('행사를 찾을 수 없습니다.', 404)

    const academy = await repo.getAcademy(event.academy_id)
    const students = await repo.listStudents(params.id)
    if (students.length === 0) return fail('학생 명단을 먼저 등록해 주세요.')

    const body = await readJson(req)
    const result = await generateProgram(
      {
        eventTitle: event.title,
        academyName: academy?.name ?? '피아노학원',
        eventAt: event.event_at,
        venue: event.venue,
        students,
      },
      readOptions(body),
    )

    await repo.saveProgram(
      params.id,
      result.plan.items.map((item) => ({
        id: item.student.id,
        order_no: item.order_no,
        mc_script: result.script.byStudentId[item.student.id] ?? null,
      })),
    )

    await repo.updateEvent(params.id, {
      status: event.status === 'draft' ? 'ready' : event.status,
      mc_opening: result.script.opening,
      mc_closing: result.script.closing,
      program_source: result.source,
      program_generated_at: new Date().toISOString(),
    })

    return ok({
      source: result.source,
      model: result.model,
      fallbackReason: result.fallbackReason,
      plan: result.plan,
      script: result.script,
    })
  })
}

/**
 * 원장이 손으로 고친 순서를 저장한다.
 *
 * 자동 배치는 출발점일 뿐이다. "이 아이는 앞쪽에", "형제는 붙여서" 같은
 * 원장만 아는 사정이 늘 있고, 그걸 못 바꾸면 자동 배치는 쓸모가 없다.
 * 멘트는 건드리지 않는다 — 순서만 바뀐다.
 */
export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const repo = getRepository()
    const event = await repo.getEvent(params.id)
    if (!event) return fail('행사를 찾을 수 없습니다.', 404)

    const students = await repo.listStudents(params.id)
    if (students.length === 0) return fail('학생 명단을 먼저 등록해 주세요.')

    const body = await readJson(req)
    const order = Array.isArray(body.order) ? body.order.filter((v): v is string => typeof v === 'string') : null
    if (!order) return fail('바뀐 순서를 받지 못했습니다.')

    const known = new Set(students.map((s) => s.id))
    const seen = new Set<string>()
    const clean: string[] = []
    for (const id of order) {
      if (!known.has(id) || seen.has(id)) continue
      seen.add(id)
      clean.push(id)
    }
    // 빠진 학생은 원래 순서대로 뒤에 붙인다 — 아무도 사라지지 않게
    for (const student of students) {
      if (!seen.has(student.id)) clean.push(student.id)
    }

    const byId = new Map(students.map((s) => [s.id, s]))
    await repo.saveProgram(
      params.id,
      clean.map((id, index) => ({
        id,
        order_no: index + 1,
        mc_script: byId.get(id)?.mc_script ?? null,
      })),
    )

    return ok({ order: clean })
  })
}
