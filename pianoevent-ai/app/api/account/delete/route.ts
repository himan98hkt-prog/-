import { rm } from 'node:fs/promises'
import { backupRoot } from '@/lib/paths'
import path from 'node:path'
import { cookies } from 'next/headers'
import { fail, guard, ok, readJson } from '@/lib/http'
import { ACADEMY_COOKIE, currentAcademyId } from '@/lib/session'
import { BACKUP_DIR } from '@/lib/events/backup'
import { getRepository } from '@/lib/store'

/**
 * 계정 및 데이터 완전 삭제.
 * Google Play "계정 삭제 요건" 대응 — 학원, 행사, 학생, RSVP 를 모두 지우고 세션 쿠키를 폐기한다.
 *
 * 자동 저장 폴더도 함께 지운다. 화면에 "백업본도 남기지 않습니다" 라고 적어 두었고,
 * 그 폴더 안에는 아이 이름과 사진이 그대로 들어 있다. 한 곳이라도 남으면 거짓말이 된다.
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
    await rm(backupRoot(BACKUP_DIR), { recursive: true, force: true })

    cookies().delete(ACADEMY_COOKIE)
    return ok({ deleted: true })
  })
}
