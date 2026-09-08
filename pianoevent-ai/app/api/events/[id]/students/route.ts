import { fail, guard, ok, readJson } from '@/lib/http'
import { parseLevel, parseRoster } from '@/lib/program/roster'
import { getRepository, type NewStudent } from '@/lib/store'
import type { Level } from '@/lib/types'

const LEVELS: Level[] = ['beginner', 'intermediate', 'advanced', 'ensemble']
const MAX_STUDENTS = 200

function toNewStudent(raw: unknown): NewStudent | null {
  if (!raw || typeof raw !== 'object') return null
  const row = raw as Record<string, unknown>
  const name = typeof row.student_name === 'string' ? row.student_name.trim() : ''
  if (!name) return null
  const level = LEVELS.includes(row.level as Level) ? (row.level as Level) : parseLevel(String(row.level ?? ''))
  const duration = Number(row.duration_sec)
  return {
    student_name: name.slice(0, 40),
    piece_title: (typeof row.piece_title === 'string' ? row.piece_title.trim() : '').slice(0, 120),
    composer: (typeof row.composer === 'string' ? row.composer.trim() : '').slice(0, 80),
    duration_sec: Number.isFinite(duration) && duration > 0 ? Math.round(duration) : null,
    level,
    note: typeof row.note === 'string' && row.note.trim() ? row.note.trim().slice(0, 200) : null,
  }
}

export async function GET(_req: Request, { params }: { params: { id: string } }) {
  return guard(async () => ok({ students: await getRepository().listStudents(params.id) }))
}

/**
 * body 는 두 가지를 받는다.
 *  - { text: "엑셀에서 복사한 표" }  → 서버에서 파싱
 *  - { students: [{...}] }          → 이미 정리된 행
 * mode=replace 면 기존 명단을 지우고 새로 넣는다.
 */
export async function POST(req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const repo = getRepository()
    const event = await repo.getEvent(params.id)
    if (!event) return fail('행사를 찾을 수 없습니다.', 404)

    const body = await readJson(req)
    const warnings: string[] = []
    let rows: NewStudent[] = []

    if (typeof body.text === 'string' && body.text.trim()) {
      const parsed = parseRoster(body.text)
      warnings.push(...parsed.errors)
      rows = parsed.rows.map((r) => ({
        student_name: r.student_name,
        piece_title: r.piece_title,
        composer: r.composer,
        duration_sec: r.duration_sec,
        level: r.level,
        note: r.note,
      }))
    } else if (Array.isArray(body.students)) {
      rows = body.students.map(toNewStudent).filter((r): r is NewStudent => r !== null)
    }

    if (rows.length === 0) return fail('추가할 학생이 없습니다.', 400, { warnings })
    if (rows.length > MAX_STUDENTS) return fail(`한 번에 ${MAX_STUDENTS}명까지 등록할 수 있습니다.`)

    const replace = new URL(req.url).searchParams.get('mode') === 'replace'
    const students = replace ? await repo.replaceStudents(params.id, rows) : await repo.addStudents(params.id, rows)

    return ok({ students, warnings }, 201)
  })
}
