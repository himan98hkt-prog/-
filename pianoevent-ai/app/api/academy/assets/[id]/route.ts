import { guard, fail, ok, readJson, str } from '@/lib/http'
import { ASSET_KIND_LABEL, type AssetKind } from '@/lib/assets'
import { currentAcademyId } from '@/lib/session'
import { getRepository } from '@/lib/store'

/** 이름·종류 고치기 */
export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const repo = getRepository()
    const academy = await repo.ensureAcademy(currentAcademyId())
    const assets = academy.assets ?? []
    if (!assets.some((a) => a.id === params.id)) return fail('그 이미지를 찾지 못했습니다.', 404)

    const body = await readJson(req)
    const label = str(body.label, 40)
    const kind = str(body.kind, 12) as AssetKind | null

    const next = assets.map((a) =>
      a.id === params.id
        ? { ...a, label: label ?? a.label, kind: kind && kind in ASSET_KIND_LABEL ? kind : a.kind }
        : a,
    )
    return ok({ academy: await repo.updateAcademy(academy.id, { assets: next }) })
  })
}

/** 보관함에서 지우기 */
export async function DELETE(_req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const repo = getRepository()
    const academy = await repo.ensureAcademy(currentAcademyId())
    const assets = academy.assets ?? []
    const next = assets.filter((a) => a.id !== params.id)
    if (next.length === assets.length) return fail('그 이미지를 찾지 못했습니다.', 404)
    return ok({ academy: await repo.updateAcademy(academy.id, { assets: next }) })
  })
}
