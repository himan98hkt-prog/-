import { randomUUID } from 'node:crypto'
import { ASSET_KIND_LABEL, ASSET_MAX_CHARS, ASSET_MAX_COUNT, isAssetUrl, type AcademyAsset, type AssetKind } from '@/lib/assets'
import { fail, guard, ok, readJson, str } from '@/lib/http'
import { currentAcademyId } from '@/lib/session'
import { getRepository } from '@/lib/store'

/** 보관함에 이미지 한 장 추가 */
export async function POST(req: Request) {
  return guard(async () => {
    const repo = getRepository()
    const academy = await repo.ensureAcademy(currentAcademyId())
    const body = await readJson(req)

    const kind = str(body.kind, 12) as AssetKind | null
    if (!kind || !(kind in ASSET_KIND_LABEL)) return fail('이미지 종류가 올바르지 않습니다.')

    const url = typeof body.url === 'string' ? body.url.trim() : ''
    if (!url) return fail('이미지가 비어 있습니다.')
    if (!isAssetUrl(url)) return fail('이미지 파일을 올리거나 http(s) 주소를 넣어 주세요.')
    if (url.length > ASSET_MAX_CHARS) {
      return fail('이미지가 너무 큽니다. 사진 크기를 줄여 다시 올려 주세요.')
    }

    const assets = academy.assets ?? []
    if (assets.length >= ASSET_MAX_COUNT) {
      return fail(`보관함은 ${ASSET_MAX_COUNT}장까지입니다. 쓰지 않는 이미지를 지워 주세요.`)
    }

    const asset: AcademyAsset = {
      id: randomUUID(),
      kind,
      label: str(body.label, 40) ?? ASSET_KIND_LABEL[kind],
      url,
      created_at: new Date().toISOString(),
    }

    const updated = await repo.updateAcademy(academy.id, { assets: [...assets, asset] })
    return ok({ academy: updated, asset }, 201)
  })
}
