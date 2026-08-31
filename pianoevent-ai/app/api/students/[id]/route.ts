import { STUDENT_PHOTO_MAX } from '@/lib/assets'
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

    // 이 아이의 사진 — 보관함에 실제로 있는 것만 받는다 (없는 id 를 넣어 두면 화면이 빈 상자가 된다)
    if (body.photo_asset_id !== undefined || body.photo_asset_ids !== undefined) {
      const repo = getRepository()
      const student = await repo.getStudent(params.id)
      if (!student) return fail('학생을 찾을 수 없습니다.', 404)
      const event = await repo.getEvent(student.event_id)
      const academy = event ? await repo.getAcademy(event.academy_id) : null
      const owned = new Set((academy?.assets ?? []).map((asset) => asset.id))

      if (body.photo_asset_id !== undefined) {
        const value = body.photo_asset_id
        if (value === null || value === '') {
          patch.photo_asset_id = null
        } else if (typeof value === 'string') {
          if (!owned.has(value)) return fail('보관함에 없는 사진입니다.')
          patch.photo_asset_id = value
        }
      }

      // 사진 여러 장 — 대표 사진은 늘 맨 앞이고, 나머지는 영상에서 넘겨 가며 보여 준다
      if (body.photo_asset_ids !== undefined) {
        const value = body.photo_asset_ids
        if (value === null) {
          patch.photo_asset_ids = null
        } else if (Array.isArray(value)) {
          const ids: string[] = []
          for (const raw of value) {
            if (typeof raw !== 'string' || !raw) continue
            if (!owned.has(raw)) return fail('보관함에 없는 사진입니다.')
            if (!ids.includes(raw)) ids.push(raw)
          }
          if (ids.length > STUDENT_PHOTO_MAX) {
            return fail(`아이 한 명당 사진은 ${STUDENT_PHOTO_MAX}장까지 넣을 수 있습니다.`)
          }
          patch.photo_asset_ids = ids.length > 0 ? ids : null
        }
      }
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
