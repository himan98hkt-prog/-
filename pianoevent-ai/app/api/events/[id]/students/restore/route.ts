import { fail, guard, ok, readJson } from '@/lib/http'
import { getRepository, type NewStudent } from '@/lib/store'
import type { Level } from '@/lib/types'

const LEVELS: Level[] = ['beginner', 'intermediate', 'advanced', 'ensemble']

/**
 * 붙여넣기 되돌리기.
 *
 * 명단 등록 화면은 붙여넣기 **직전의 명단**을 통째로 들고 있다가 이리로 보낸다.
 * 그래서 되돌리기는 "방금 넣은 것을 지운다" 가 아니라 "그때 그대로 되돌린다" 이다.
 * 교체로 넣으셨든 추가로 넣으셨든 결과가 같다.
 *
 * 빈 목록을 받는 것이 정상이다 — 처음 붙여넣으신 경우 되돌리면 빈 명단이 맞다.
 * (그래서 학생 등록 길과 따로 둔다. 그쪽은 빈 목록을 거절해야 한다.)
 */
export async function POST(req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const repo = getRepository()
    const event = await repo.getEvent(params.id)
    if (!event) return fail('행사를 찾을 수 없습니다.', 404)

    const body = await readJson(req)
    if (!Array.isArray(body.students)) return fail('되돌릴 명단을 찾지 못했습니다.')

    const rows: NewStudent[] = body.students
      .map((raw): NewStudent | null => {
        if (!raw || typeof raw !== 'object') return null
        const row = raw as Record<string, unknown>
        const name = typeof row.student_name === 'string' ? row.student_name.trim() : ''
        if (!name) return null
        const duration = Number(row.duration_sec)
        const many = Array.isArray(row.photo_asset_ids)
          ? row.photo_asset_ids.filter((v): v is string => typeof v === 'string')
          : null
        return {
          student_name: name.slice(0, 40),
          piece_title: (typeof row.piece_title === 'string' ? row.piece_title.trim() : '').slice(0, 120),
          composer: (typeof row.composer === 'string' ? row.composer.trim() : '').slice(0, 80),
          duration_sec: Number.isFinite(duration) && duration > 0 ? Math.round(duration) : null,
          level: LEVELS.includes(row.level as Level) ? (row.level as Level) : 'beginner',
          note: typeof row.note === 'string' && row.note.trim() ? row.note.trim().slice(0, 200) : null,
          // 사진까지 되돌린다. 사진이 사라지면 되돌린 것이 아니다.
          photo_asset_id: typeof row.photo_asset_id === 'string' ? row.photo_asset_id : null,
          photo_asset_ids: many && many.length > 1 ? many : null,
        }
      })
      .filter((r): r is NewStudent => r !== null)

    const students = await repo.replaceStudents(params.id, rows)
    return ok({ students })
  })
}
