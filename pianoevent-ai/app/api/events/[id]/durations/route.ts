import { fail, guard, ok, readJson } from '@/lib/http'
import { ACTUAL_MAX_SEC, ACTUAL_MIN_SEC } from '@/lib/ops/live'
import { normalizeTimingLog, pushTimings } from '@/lib/ops/timing'
import { getRepository } from '@/lib/store'

/**
 * 당일에 실제로 걸린 시간을 명단에 되돌린다.
 *
 * 순서표의 예상 시간은 책에 적힌 평균이다. 그런데 그 학원 아이들은
 * 그보다 빠르거나 느리다. 한 번 무대에 올려 보고 그 시간을 적어 두면,
 * 다음 해 순서표의 종료 시각이 진짜가 된다.
 *
 * 한 줄씩 30번 부르는 대신 한 번에 받는다 — 당일 저녁에 누르는 단추라
 * 느리면 안 누르신다.
 */
export async function POST(req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const repo = getRepository()
    const event = await repo.getEvent(params.id)
    if (!event) return fail('행사를 찾을 수 없습니다.', 404)

    const body = await readJson(req)
    if (!Array.isArray(body.updates) || body.updates.length === 0) return fail('반영할 시간이 없습니다.')

    // 이 행사의 학생만 고친다 — 남의 명단을 건드릴 수 없게
    const students = await repo.listStudents(params.id)
    const byId = new Map(students.map((student) => [student.id, student]))
    const rows: { id: string; name: string; duration_sec: number }[] = []
    for (const raw of body.updates) {
      if (!raw || typeof raw !== 'object') continue
      const row = raw as Record<string, unknown>
      const id = typeof row.student_id === 'string' ? row.student_id : ''
      const student = byId.get(id)
      const seconds = Number(row.duration_sec)
      if (!student || !Number.isFinite(seconds)) continue
      // 20초 미만·20분 초과는 잘못 누른 것으로 본다 (lib/ops/live.ts 와 같은 기준)
      if (seconds < ACTUAL_MIN_SEC || seconds > ACTUAL_MAX_SEC) continue
      rows.push({ id, name: student.student_name, duration_sec: Math.round(seconds) })
    }
    if (rows.length === 0) return fail('반영할 만한 시간이 없습니다.')

    for (const row of rows) await repo.updateStudent(row.id, { duration_sec: row.duration_sec })

    // 학원에도 쌓아 둔다. 명단은 행사마다 새로 만들어지지만 아이는 그대로다 —
    // 몇 해가 쌓이면 그날 유난히 느렸던 한 번에 끌려다니지 않는다
    const academy = await repo.getAcademy(event.academy_id)
    if (academy) {
      const log = pushTimings(
        normalizeTimingLog(academy.timing_log),
        rows.map((row) => ({ name: row.name, seconds: row.duration_sec })),
      )
      await repo.updateAcademy(academy.id, { timing_log: log })
    }

    return ok({ updated: rows.length })
  })
}
