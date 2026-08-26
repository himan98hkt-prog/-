import { DESIGN_THEMES } from '@/lib/design/themes'
import { DESIGN_TEMPLATES } from '@/lib/design/templates'
import { normalizeEventAt } from '@/lib/format'
import { fail, guard, ok, readJson, str } from '@/lib/http'
import { getRepository } from '@/lib/store'
import type { EventStatus } from '@/lib/types'

const STATUSES: EventStatus[] = ['draft', 'ready', 'published', 'done']

export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const repo = getRepository()
    const event = await repo.getEvent(params.id)
    if (!event) return fail('행사를 찾을 수 없습니다.', 404)

    const body = await readJson(req)
    const patch: Record<string, unknown> = {}

    const title = str(body.title, 120)
    if (title) patch.title = title
    if (typeof body.venue === 'string') patch.venue = body.venue.trim().slice(0, 160)
    if (typeof body.greeting === 'string') patch.greeting = body.greeting.trim().slice(0, 800) || null
    const eventAt = str(body.event_at, 40)
    if (eventAt) {
      const iso = normalizeEventAt(eventAt)
      if (!iso) return fail('행사 일시를 올바르게 입력해 주세요.')
      patch.event_at = iso
    }
    if (STATUSES.includes(body.status as EventStatus)) patch.status = body.status

    const theme = str(body.design_theme, 40)
    if (theme && DESIGN_THEMES.some((t) => t.id === theme)) patch.design_theme = theme
    const template = str(body.design_template, 40)
    if (template && DESIGN_TEMPLATES.some((t) => t.id === template)) patch.design_template = template
    if (body.design_copy && typeof body.design_copy === 'object' && !Array.isArray(body.design_copy)) {
      // 문구는 자유 입력이라 키를 고정하고 길이를 제한한다
      const source = body.design_copy as Record<string, unknown>
      const copy: Record<string, string> = {}
      for (const key of ['subtitle', 'host', 'contact', 'footnote']) {
        if (typeof source[key] === 'string') copy[key] = (source[key] as string).trim().slice(0, 200)
      }
      patch.design_copy = copy
    }

    if (Object.keys(patch).length === 0) return fail('변경할 내용이 없습니다.')
    return ok({ event: await repo.updateEvent(params.id, patch) })
  })
}

export async function DELETE(_req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    await getRepository().deleteEvent(params.id)
    return ok({ deleted: true })
  })
}
