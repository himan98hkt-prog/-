import { fail, guard, ok, readJson, str } from '@/lib/http'
import { currentAcademyId } from '@/lib/session'
import { getRepository } from '@/lib/store'
import type { EventType, SeasonTheme } from '@/lib/types'

const EVENT_TYPES: EventType[] = ['recital', 'season']
const THEMES: SeasonTheme[] = ['halloween', 'christmas', 'vacation']

export async function POST(req: Request) {
  return guard(async () => {
    const repo = getRepository()
    const academy = await repo.ensureAcademy(currentAcademyId())
    const body = await readJson(req)

    const title = str(body.title, 120)
    const venue = str(body.venue, 160) ?? ''
    const eventAt = str(body.event_at, 40)
    const type = EVENT_TYPES.includes(body.type as EventType) ? (body.type as EventType) : 'recital'
    const theme = THEMES.includes(body.theme as SeasonTheme) ? (body.theme as SeasonTheme) : null

    if (!title) return fail('행사명을 입력해 주세요.')
    if (!eventAt || Number.isNaN(new Date(eventAt).getTime())) return fail('행사 일시를 올바르게 입력해 주세요.')

    const event = await repo.createEvent(academy.id, {
      title,
      type,
      event_at: new Date(eventAt).toISOString(),
      venue,
      theme,
      greeting: str(body.greeting, 800),
    })

    return ok({ event }, 201)
  })
}

export async function GET() {
  return guard(async () => {
    const repo = getRepository()
    const academy = await repo.ensureAcademy(currentAcademyId())
    return ok({ events: await repo.listEvents(academy.id) })
  })
}
