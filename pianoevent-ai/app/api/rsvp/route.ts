import { bool, fail, guard, int, ok, readJson, str } from '@/lib/http'
import { getRepository } from '@/lib/store'

/** 공개 초대장에서 학부모가 보내는 참석 회신. 로그인 없이 호출된다. */
export async function POST(req: Request) {
  return guard(async () => {
    const body = await readJson(req)
    const eventId = str(body.event_id, 64)
    if (!eventId) return fail('행사 정보가 없습니다.')

    const repo = getRepository()
    const event = await repo.getEvent(eventId)
    if (!event) return fail('행사를 찾을 수 없습니다.', 404)
    if (event.status === 'done') return fail('이미 종료된 행사입니다.', 409)

    const parentName = str(body.parent_name, 40)
    const studentName = str(body.student_name, 40)
    const attending = bool(body.attending, true)
    const headcount = attending ? int(body.headcount, 1, 20) : 0

    if (!parentName) return fail('보호자 성함을 입력해 주세요.')
    if (!studentName) return fail('학생 이름을 입력해 주세요.')
    if (attending && headcount === null) return fail('참석 인원은 1~20명 사이로 입력해 주세요.')

    // 같은 학생에 대해 다시 회신하면 이전 응답을 대체한다 (집계가 부풀지 않도록)
    const existing = await repo.listRsvps(eventId)
    const duplicate = existing.filter(
      (r) => r.student_name.trim() === studentName && r.parent_name.trim() === parentName,
    )
    for (const row of duplicate) await repo.deleteRsvp(row.id)

    const rsvp = await repo.createRsvp(eventId, {
      parent_name: parentName,
      student_name: studentName,
      headcount: headcount ?? 0,
      message: str(body.message, 300),
      attending,
    })

    return ok({ rsvp, replaced: duplicate.length > 0 }, 201)
  })
}
