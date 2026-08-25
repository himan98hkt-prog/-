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
