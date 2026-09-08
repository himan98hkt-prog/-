import { fail, guard, int, ok, readJson, str } from '@/lib/http'
import { generateSeasonPack } from '@/lib/season/ai'
import { currentAcademyId } from '@/lib/session'
import { getRepository } from '@/lib/store'
import type { SeasonTheme } from '@/lib/types'

export const maxDuration = 60

const THEMES: SeasonTheme[] = ['halloween', 'christmas', 'vacation']

export async function POST(req: Request) {
  return guard(async () => {
    const body = await readJson(req)
    const theme = body.theme as SeasonTheme
    if (!THEMES.includes(theme)) return fail('테마를 선택해 주세요. (halloween · christmas · vacation)')

    const academy = await getRepository().ensureAcademy(currentAcademyId())
    const pack = await generateSeasonPack({
      theme,
      academyName: academy.name,
      weeks: int(body.weeks, 1, 12) ?? 4,
      target: str(body.target, 80) ?? '초등 저·중학년',
      focus: str(body.focus, 300) ?? '',
    })

    return ok({ pack })
  })
}
