import { fail, guard, ok, readJson } from '@/lib/http'
import { getRepository } from '@/lib/store'
import type { Level } from '@/lib/types'

const LEVELS: Level[] = ['beginner', 'intermediate', 'advanced', 'ensemble']

export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const body = await readJson(req)
    const patch: Record<string, unknown> = {}

    if (typeof body.student_name === 'string' && body.student_name.trim()) {
      patch.student_name = body.student_name.trim().slice(0, 40)
    }
    if (typeof body.piece_title === 'string') patch.piece_title = body.piece_title.trim().slice(0, 120)
    if (typeof body.composer === 'string') patch.composer = body.composer.trim().slice(0, 80)
    if (typeof body.note === 'string') patch.note = body.note.trim().slice(0, 200) || null
    if (LEVELS.includes(body.level as Level)) patch.level = body.level
    if (body.duration_sec !== undefined) {
      const n = Number(body.duration_sec)
      patch.duration_sec = Number.isFinite(n) && n > 0 ? Math.round(n) : null
    }

    if (Object.keys(patch).length === 0) return fail('변경할 내용이 없습니다.')
    return ok({ student: await getRepository().updateStudent(params.id, patch) })
  })
}

export async function DELETE(_req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    await getRepository().deleteStudent(params.id)
    return ok({ deleted: true })
  })
}
