import { guard, ok } from '@/lib/http'
import { currentAcademyId } from '@/lib/session'
import { getRepository } from '@/lib/store'
import pkg from '@/package.json'

/**
 * "막히면 여기" 쪽지에 넣을 것 — 판 · 저장 방식 · 규모(숫자만).
 *
 * 이름은 하나도 내보내지 않는다. 세는 것만 센다.
 */
/** 학원 쿠키를 보므로 미리 구워 둘 수 없다 */
export const dynamic = 'force-dynamic'

export async function GET() {
  return guard(async () => {
    const repo = getRepository()
    const academy = await repo.ensureAcademy(currentAcademyId())
    const events = await repo.listEvents(academy.id)
    const students = await Promise.all(events.map(async (e) => (await repo.listStudents(e.id)).length))

    return ok({
      version: (pkg as { version?: string }).version ?? '0.0.0',
      driver: repo.driver,
      counts: {
        events: events.length,
        students: students.reduce((sum, n) => sum + n, 0),
        photos: (academy.assets ?? []).length,
      },
    })
  })
}
