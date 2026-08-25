import { cookies } from 'next/headers'
import { fail, guard, ok, readJson } from '@/lib/http'
import { ACADEMY_COOKIE, currentAcademyId } from '@/lib/session'
import { getRepository } from '@/lib/store'

/**
 * 계정 및 데이터 완전 삭제.
 * Google Play "계정 삭제 요건" 대응 — 학원, 행사, 학생, RSVP 를 모두 지우고 세션 쿠키를 폐기한다.
 */
export async function POST(req: Request) {
  return guard(async () => {
    const body = await readJson(req)
    if (body.confirm !== '삭제') {
      return fail('확인란에 "삭제" 를 정확히 입력해 주세요.', 400)
    }

    const repo = getRepository()
    const id = currentAcademyId()
    const academy = await repo.ensureAcademy(id)
    await repo.deleteAcademy(academy.id)

    cookies().delete(ACADEMY_COOKIE)
    return ok({ deleted: true })
  })
}
