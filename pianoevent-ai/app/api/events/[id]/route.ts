import { DESIGN_THEMES } from '@/lib/design/themes'
import { DESIGN_TEMPLATES } from '@/lib/design/templates'
import { normalizeEventAt } from '@/lib/format'
import { fail, guard, ok, readJson, str } from '@/lib/http'
import { sanitizePrefs, STAGE_PREF_SPEC, VIDEO_PREF_SPEC } from '@/lib/prefs'
import { getRepository } from '@/lib/store'
import { videoEmbed } from '@/lib/video/embed'
import type { EventStatus } from '@/lib/types'

const STATUSES: EventStatus[] = ['draft', 'ready', 'published', 'done']

/** 인쇄물 갈래별 이미지 지정에 쓸 수 있는 키 */
const IMAGE_MAP_KEYS = ['default', 'logo', 'poster', 'program', 'invite', 'stage', 'ops']

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

    if (typeof body.photo_url === 'string') {
      const url = body.photo_url.trim()
      // data: URI 도 허용한다 (학원이 직접 붙여넣는 경우가 있다)
      if (url && !/^(https?:\/\/|data:image\/)/i.test(url)) {
        return fail('사진 주소는 http(s) 또는 이미지 data URI 여야 합니다.')
      }
      patch.photo_url = url.slice(0, 4000) || null
    }

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

    if (body.image_map && typeof body.image_map === 'object' && !Array.isArray(body.image_map)) {
      // 보관함에 실제로 있는 이미지만 받는다 — 지운 이미지를 가리키면 인쇄물이 비어 버린다
      const academy = await repo.getAcademy(event.academy_id)
      const known = new Set((academy?.assets ?? []).map((a) => a.id))
      const source = body.image_map as Record<string, unknown>
      const map: Record<string, string> = {}
      for (const key of IMAGE_MAP_KEYS) {
        const value = source[key]
        if (typeof value === 'string' && known.has(value)) map[key] = value
      }
      patch.image_map = map
    }

    // 무대 화면·감동영상 설정 — 아는 키만, 아는 범위 안에서만 받는다 (lib/prefs.ts)
    if ('stage_prefs' in body) patch.stage_prefs = sanitizePrefs(STAGE_PREF_SPEC, body.stage_prefs)
    if ('video_prefs' in body) patch.video_prefs = sanitizePrefs(VIDEO_PREF_SPEC, body.video_prefs)

    if (typeof body.video_url === 'string') {
      const raw = body.video_url.trim()
      if (!raw) {
        patch.video_url = null
      } else {
        // 초대장은 학부모가 여는 공개 화면이다 — http(s) 가 아닌 주소는 붙이지 않는다
        const embed = videoEmbed(raw)
        if (!embed) return fail('영상 주소는 http(s) 로 시작하는 주소여야 합니다.')
        patch.video_url = embed.href.slice(0, 500)
      }
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
