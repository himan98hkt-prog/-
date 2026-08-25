import { fail, guard, ok, readJson, str } from '@/lib/http'
import { currentAcademyId } from '@/lib/session'
import { getRepository } from '@/lib/store'

export async function PATCH(req: Request) {
  return guard(async () => {
    const repo = getRepository()
    const academy = await repo.ensureAcademy(currentAcademyId())
    const body = await readJson(req)

    const patch: Record<string, unknown> = {}
    const name = str(body.name, 60)
    if (name) patch.name = name
    const director = str(body.director_name, 40)
    if (director) patch.director_name = director
    const color = str(body.theme_color, 20)
    if (color && /^#[0-9a-fA-F]{6}$/.test(color)) patch.theme_color = color
    if (typeof body.logo_url === 'string') patch.logo_url = body.logo_url.trim() || null

    if (Object.keys(patch).length === 0) return fail('변경할 내용이 없습니다.')
    return ok({ academy: await repo.updateAcademy(academy.id, patch) })
  })
}
