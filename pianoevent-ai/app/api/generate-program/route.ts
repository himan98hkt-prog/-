import { randomUUID } from 'node:crypto'
import { fail, guard, ok, readJson } from '@/lib/http'
import { generateProgram } from '@/lib/program/ai'
import { parseLevel } from '@/lib/program/roster'
import { DEFAULT_PROGRAM_OPTIONS, type EventStudent, type Level } from '@/lib/types'

export const maxDuration = 60

const LEVELS: Level[] = ['beginner', 'intermediate', 'advanced', 'ensemble']

/**
 * 저장 없이 순서표만 받아 보는 무상태 엔드포인트 (개발 지시서 Step 2 그대로).
 * body: { eventTitle, academyName?, students: [{ name|student_name, piece, composer, level, duration }] }
 */
export async function POST(req: Request) {
  return guard(async () => {
    const body = await readJson(req)
    const eventTitle = typeof body.eventTitle === 'string' && body.eventTitle.trim() ? body.eventTitle.trim() : '정기 연주회'
    const academyName =
      typeof body.academyName === 'string' && body.academyName.trim() ? body.academyName.trim() : '피아노학원'

    if (!Array.isArray(body.students) || body.students.length === 0) {
      return fail('students 배열이 필요합니다.')
    }
    if (body.students.length > 200) return fail('한 번에 200명까지 처리할 수 있습니다.')

    const now = new Date().toISOString()
    const students: EventStudent[] = body.students.flatMap((raw, index) => {
      if (!raw || typeof raw !== 'object') return []
      const row = raw as Record<string, unknown>
      const name = String(row.student_name ?? row.name ?? '').trim()
      if (!name) return []
      const level = LEVELS.includes(row.level as Level) ? (row.level as Level) : parseLevel(String(row.level ?? ''))
      const duration = Number(row.duration_sec ?? row.duration)
      return [
        {
          id: typeof row.id === 'string' && row.id ? row.id : randomUUID(),
          event_id: 'stateless',
          student_name: name,
          piece_title: String(row.piece_title ?? row.piece ?? '').trim(),
          composer: String(row.composer ?? '').trim(),
          duration_sec: Number.isFinite(duration) && duration > 0 ? Math.round(duration) : 0,
          level,
          order_no: index + 1,
          mc_script: null,
          photo_asset_id: null,
          note: typeof row.note === 'string' ? row.note.trim() : null,
          created_at: now,
        },
      ]
    })

    if (students.length === 0) return fail('유효한 학생이 없습니다. 이름은 필수입니다.')

    const result = await generateProgram(
      {
        eventTitle,
        academyName,
        eventAt: typeof body.eventAt === 'string' ? body.eventAt : now,
        venue: typeof body.venue === 'string' ? body.venue : '',
        students,
      },
      DEFAULT_PROGRAM_OPTIONS,
    )

    return ok({
      source: result.source,
      model: result.model,
      fallbackReason: result.fallbackReason,
      totalSec: result.plan.total_sec,
      warnings: result.plan.warnings,
      openingScript: result.script.opening,
      closingScript: result.script.closing,
      program: result.plan.items.map((item) => ({
        order_no: item.order_no,
        stage: item.stage,
        student_name: item.student.student_name,
        piece_title: item.student.piece_title,
        composer: item.student.composer,
        duration_sec: item.duration_sec,
        start_offset_sec: item.start_offset_sec,
        mc_script: result.script.byStudentId[item.student.id] ?? null,
      })),
      breaks: result.plan.breaks,
    })
  })
}
