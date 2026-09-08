import { DESIGN_TEMPLATES } from '@/lib/design/templates'
import { DESIGN_THEMES } from '@/lib/design/themes'
import { fail, guard, ok, readJson, str } from '@/lib/http'
import { getRepository } from '@/lib/store'

/**
 * 지난 행사의 인쇄물 설정을 그대로 가져온다.
 *
 * 학원은 해마다 같은 얼굴이다. 작년에 맞춰 둔 테마·양식·문구를 다시 고를 이유가 없다.
 * 명단은 이미 "지난 행사에서 가져오기" 가 있었는데, 디자인만 매번 처음부터였다.
 *
 * 사진 지정(image_map)까지 함께 옮긴다 — 보관함은 학원 것이라 그대로 있다.
 * 다만 그 사이 지운 사진을 가리키고 있으면 그 자리만 빼고 가져온다.
 */
export async function POST(req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const repo = getRepository()
    const event = await repo.getEvent(params.id)
    if (!event) return fail('행사를 찾을 수 없습니다.', 404)

    const body = await readJson(req)
    const fromId = str(body.from_event_id, 64)
    if (!fromId) return fail('어느 행사에서 가져올지 골라 주세요.')
    if (fromId === params.id) return fail('같은 행사에서는 가져올 수 없습니다.')

    const source = await repo.getEvent(fromId)
    if (!source) return fail('가져올 행사를 찾을 수 없습니다.', 404)
    if (source.academy_id !== event.academy_id) return fail('다른 학원의 행사입니다.', 403)

    const patch: Record<string, unknown> = {}
    if (source.design_theme && DESIGN_THEMES.some((t) => t.id === source.design_theme)) {
      patch.design_theme = source.design_theme
    }
    if (source.design_template && DESIGN_TEMPLATES.some((t) => t.id === source.design_template)) {
      patch.design_template = source.design_template
    }

    // 문구는 행사 이름·날짜가 아니라 학원의 말투다. 그대로 옮겨도 어색하지 않다
    if (body.copy !== false && source.design_copy) patch.design_copy = { ...source.design_copy }

    if (body.images !== false && source.image_map) {
      const academy = await repo.getAcademy(event.academy_id)
      const known = new Set((academy?.assets ?? []).map((asset) => asset.id))
      const map: Record<string, string> = {}
      for (const [key, value] of Object.entries(source.image_map)) {
        if (typeof value === 'string' && known.has(value)) map[key] = value
      }
      patch.image_map = map
    }

    // 무대 화면·영상 설정도 저장해 두셨다면 함께
    if (body.screens !== false) {
      if (source.stage_prefs) patch.stage_prefs = source.stage_prefs
      if (source.video_prefs) patch.video_prefs = source.video_prefs
    }

    if (Object.keys(patch).length === 0) {
      return fail('그 행사에는 저장해 둔 디자인이 없습니다.')
    }
    return ok({ event: await repo.updateEvent(params.id, patch), applied: Object.keys(patch) })
  })
}
