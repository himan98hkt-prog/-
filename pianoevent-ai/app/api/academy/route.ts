import { DESIGN_THEMES } from '@/lib/design/themes'
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
    if (typeof body.photo_url === 'string') {
      const url = body.photo_url.trim()
      if (url && !/^(https?:\/\/|data:image\/)/i.test(url)) {
        return fail('사진 주소는 http(s) 또는 이미지 data URI 여야 합니다.')
      }
      patch.photo_url = url.slice(0, 4000) || null
    }
    const theme = str(body.design_theme, 40)
    if (theme && DESIGN_THEMES.some((t) => t.id === theme)) patch.design_theme = theme

    if (Object.keys(patch).length === 0) return fail('변경할 내용이 없습니다.')
    return ok({ academy: await repo.updateAcademy(academy.id, patch) })
  })
}
