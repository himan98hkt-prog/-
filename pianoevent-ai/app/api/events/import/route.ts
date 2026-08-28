import { ASSET_KIND_LABEL, ASSET_MAX_COUNT, isAssetUrl, type AcademyAsset, type AssetKind } from '@/lib/assets'
import { BundleError, parseBundle, type EventBundle } from '@/lib/events/transfer'
import { fail, guard, ok, readJson } from '@/lib/http'
import { currentAcademyId } from '@/lib/session'
import { getRepository, type NewStudent } from '@/lib/store'

/**
 * 내보낸 행사 파일을 이 학원으로 들여온다.
 *
 * 늘 **새 행사로** 만든다. 지금 있는 행사를 덮어쓰지 않는다 — 잘못 고르셨을 때
 * 되돌릴 수 없는 일은 만들지 않는다. 겹치면 목록에 두 개가 보일 뿐이고,
 * 하나 지우는 것은 쉽다.
 *
 * 사진은 보관함으로 옮겨 붙인다. 같은 번호가 이미 있으면 그것을 그대로 쓴다 —
 * 같은 컴퓨터에서 내보냈다 다시 들여오실 때 사진이 두 벌 쌓이지 않게.
 */
export async function POST(req: Request) {
  return guard(async () => {
    const repo = getRepository()
    const academy = await repo.ensureAcademy(currentAcademyId())
    const body = await readJson(req)

    let bundle: EventBundle
    try {
      bundle = parseBundle(typeof body.text === 'string' ? body.text : JSON.stringify(body.bundle ?? {}))
    } catch (error) {
      return fail(error instanceof BundleError ? error.message : '행사 파일을 읽지 못했습니다.')
    }

    // ── 사진 먼저. 명단이 사진 번호를 가리키므로 보관함에 있어야 붙는다
    const have = new Map((academy.assets ?? []).map((a) => [a.id, a]))
    const room = ASSET_MAX_COUNT - have.size
    const incoming = bundle.assets.filter((a) => !have.has(a.id) && isAssetUrl(a.url)).slice(0, Math.max(0, room))
    const skippedPhotos = bundle.assets.length - incoming.length - bundle.assets.filter((a) => have.has(a.id)).length

    if (incoming.length > 0) {
      const added: AcademyAsset[] = incoming.map((a) => ({
        id: a.id,
        kind: (a.kind in ASSET_KIND_LABEL ? a.kind : 'photo') as AssetKind,
        label: (a.label || ASSET_KIND_LABEL.photo).slice(0, 40),
        url: a.url,
        created_at: a.created_at || new Date().toISOString(),
      }))
      await repo.updateAcademy(academy.id, { assets: [...(academy.assets ?? []), ...added] })
      for (const a of added) have.set(a.id, a)
    }

    // ── 행사
    const created = await repo.createEvent(academy.id, {
      title: bundle.event.title,
      type: bundle.event.type,
      event_at: bundle.event.event_at,
      venue: bundle.event.venue,
      theme: bundle.event.theme ?? undefined,
      greeting: bundle.event.greeting,
    })
    await repo.updateEvent(created.id, {
      mc_opening: bundle.event.mc_opening,
      mc_closing: bundle.event.mc_closing,
      design_theme: bundle.event.design_theme,
      design_template: bundle.event.design_template,
      design_copy: bundle.event.design_copy,
      stage_prefs: bundle.event.stage_prefs,
      video_prefs: bundle.event.video_prefs,
      video_url: bundle.event.video_url,
    })

    // ── 명단. 보관함에 없는 사진 번호는 떼고 넣는다 (깨진 그림 자리가 생기지 않게)
    const keep = (id: string | null) => (id && have.has(id) ? id : null)
    const rows: NewStudent[] = bundle.students.map((s) => {
      const many = (s.photo_asset_ids ?? []).filter((id) => have.has(id))
      return {
        student_name: s.student_name,
        piece_title: s.piece_title,
        composer: s.composer,
        duration_sec: s.duration_sec,
        level: s.level,
        note: s.note,
        photo_asset_id: keep(s.photo_asset_id) ?? many[0] ?? null,
        photo_asset_ids: many.length > 1 ? many : null,
      }
    })
    const students = rows.length > 0 ? await repo.addStudents(created.id, rows) : []

    return ok(
      {
        event: created,
        students,
        photos: incoming.length,
        skipped_photos: Math.max(0, skippedPhotos),
      },
      201,
    )
  })
}
