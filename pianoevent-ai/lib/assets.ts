import type { TemplateCategory } from '@/lib/design/templates'

/**
 * 학원 이미지 보관함.
 *
 * 원장이 인쇄물마다 사진 주소를 다시 찾아 붙여 넣던 것을 없앤다.
 * 학원 로고, 학원 상징(캐릭터·심볼), 사진 여러 장을 한 번 올려 두고
 * 인쇄물에서는 고르기만 한다.
 *
 * 이미지는 data URI 로 보관한다. 원장 컴퓨터에서 바로 올리고, 별도 이미지 호스팅이
 * 필요 없다. 대신 올리는 쪽에서 크기를 줄여 넣는다(lib/image.ts).
 */

export type AssetKind = 'logo' | 'symbol' | 'photo'

export const ASSET_KIND_LABEL: Record<AssetKind, string> = {
  logo: '학원 로고',
  symbol: '학원 상징',
  photo: '사진',
}

export const ASSET_KIND_HINT: Record<AssetKind, string> = {
  logo: '간판·명함에 쓰는 로고. 인쇄물 위쪽 로고 자리에 들어갑니다.',
  symbol: '캐릭터·심볼·건반 마크 등. 로고 대신 쓰거나 함께 씁니다.',
  photo: '학원 전경, 지난 연주회, 연습 장면. 포스터와 표지의 사진 자리에 들어갑니다.',
}

export interface AcademyAsset {
  id: string
  kind: AssetKind
  /** 원장이 알아볼 이름 — "2025 단체사진" 처럼 */
  label: string
  /** data:image/... 또는 http(s) */
  url: string
  created_at: string
}

/** 이미지 하나가 넘을 수 없는 크기(문자 기준). data URI 라 원본보다 약 1.37배 커진다 */
export const ASSET_MAX_CHARS = 900_000

/**
 * 보관함 전체 장수 상한.
 * 학생 사진을 아이마다 한 장씩 넣으면 한 반 30명 + 학원 사진이 들어가야 한다.
 */
export const ASSET_MAX_COUNT = 120

export function isAssetUrl(url: string): boolean {
  return /^(https?:\/\/|data:image\/(png|jpeg|jpg|webp|gif|svg\+xml);)/i.test(url)
}

/**
 * 인쇄물 갈래별 이미지 지정.
 * 비어 있으면 기본 사진을 쓴다. 포스터엔 단체사진, 표지엔 학원 전경처럼
 * 갈래마다 다르게 쓰고 싶을 때만 채운다.
 */
export type ImageMap = Partial<Record<TemplateCategory | 'default' | 'logo', string>>

export function assetById(assets: AcademyAsset[], id: string | null | undefined): AcademyAsset | null {
  if (!id) return null
  return assets.find((a) => a.id === id) ?? null
}

/** 이 인쇄물에 쓸 사진 — 갈래 지정 → 기본 지정 → 행사 사진 → 학원 대표 사진 순 */
export function resolvePhoto(
  assets: AcademyAsset[],
  map: ImageMap | null | undefined,
  category: TemplateCategory,
  fallbacks: (string | null | undefined)[] = [],
): string | null {
  const picked = assetById(assets, map?.[category]) ?? assetById(assets, map?.default)
  if (picked) return picked.url
  for (const url of fallbacks) {
    if (url && url.trim()) return url.trim()
  }
  return null
}

/** 이 행사에 쓸 로고 — 지정한 것이 있으면 그것, 없으면 학원 로고 */
export function resolveLogo(
  assets: AcademyAsset[],
  map: ImageMap | null | undefined,
  fallback: string | null | undefined,
): string | null {
  const picked = assetById(assets, map?.logo)
  if (picked) return picked.url
  return fallback?.trim() || null
}

/** 화면에 보여 줄 용량 표기 */
export function assetSizeLabel(url: string): string {
  if (!url.startsWith('data:')) return '외부 주소'
  const kb = Math.round((url.length * 0.75) / 1024)
  return kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb} KB`
}

/**
 * 학생 id → 사진 주소.
 * 아이마다 지정한 사진만 담는다. 지정이 없으면 그 아이 화면에는 사진이 없다 —
 * 엉뚱한 아이 얼굴이 올라가느니 없는 편이 낫다.
 */
export function studentPhotos(
  assets: AcademyAsset[],
  students: { id: string; photo_asset_id: string | null }[],
): Record<string, string> {
  const byId = new Map(assets.map((asset) => [asset.id, asset.url]))
  const out: Record<string, string> = {}
  for (const student of students) {
    const url = student.photo_asset_id ? byId.get(student.photo_asset_id) : undefined
    if (url) out[student.id] = url
  }
  return out
}

/** 아이마다 사진 몇 장까지 붙일 수 있는가 — 영상에서 한 명이 머무는 시간은 몇 초뿐이다 */
export const STUDENT_PHOTO_MAX = 6

/**
 * 학생 id → 사진 주소 **여러 장** (보여 줄 차례대로).
 *
 * 감동영상에서 한 아이가 3~4초 머무는데 사진이 한 장이면 정지 화면에 가깝다.
 * 두세 장이 넘어가면 그 몇 초가 살아난다.
 *
 * 대표 사진(`photo_asset_id`)은 늘 맨 앞이다 — 무대 화면과 파워포인트는
 * 한 장만 쓰므로, 원장님이 고르신 그 사진이 거기에 들어가야 한다.
 */
export function studentPhotoList(
  assets: AcademyAsset[],
  students: { id: string; photo_asset_id: string | null; photo_asset_ids?: string[] | null }[],
): Record<string, string[]> {
  const byId = new Map(assets.map((asset) => [asset.id, asset.url]))
  const out: Record<string, string[]> = {}
  for (const student of students) {
    const ids = [student.photo_asset_id, ...(student.photo_asset_ids ?? [])]
    const urls: string[] = []
    for (const id of ids) {
      if (!id) continue
      const url = byId.get(id)
      // 보관함에서 지운 사진은 건너뛴다. 같은 사진을 두 번 넣어 두셨어도 한 번만
      if (url && !urls.includes(url)) urls.push(url)
    }
    if (urls.length > 0) out[student.id] = urls.slice(0, STUDENT_PHOTO_MAX)
  }
  return out
}

/**
 * 이 아이의 사진들을 다음 행사로 물려준다.
 *
 * 학원은 학생이 그대로다. 30명 얼굴을 해마다 다시 짝지을 이유가 없다.
 * 그 사이 보관함에서 지운 사진만 빼고 차례 그대로 넘긴다.
 */
export function carryPhotoIds(
  assets: AcademyAsset[],
  student: { photo_asset_id: string | null; photo_asset_ids?: string[] | null },
): string[] {
  const known = new Set(assets.map((asset) => asset.id))
  const out: string[] = []
  for (const id of [student.photo_asset_id, ...(student.photo_asset_ids ?? [])]) {
    if (id && known.has(id) && !out.includes(id)) out.push(id)
  }
  return out.slice(0, STUDENT_PHOTO_MAX)
}

/**
 * 당일에 몰아 찍은 사진에 붙이는 이름표.
 *
 * 리허설에서는 아이를 골라 가며 찍을 겨를이 없다. 일단 담아 두고 나중에 나눈다.
 * 담아 둔 것을 잃지 않으려면 그 자리에서 보관함에 넣어야 하고,
 * 그러면 "아직 아무 아이에게도 안 붙은 것" 을 가려낼 수 있어야 한다.
 */
export const UNSORTED_LABEL = '당일 사진'

/** 아직 아이에게 붙지 않은 당일 사진들 — 나중에 나누는 화면에 뜬다 */
export function unsortedPhotos(
  assets: AcademyAsset[],
  students: { photo_asset_id: string | null; photo_asset_ids?: string[] | null }[],
): AcademyAsset[] {
  const used = new Set<string>()
  for (const student of students) {
    if (student.photo_asset_id) used.add(student.photo_asset_id)
    for (const id of student.photo_asset_ids ?? []) used.add(id)
  }
  return assets.filter(
    (asset) => asset.kind === 'photo' && asset.label.startsWith(UNSORTED_LABEL) && !used.has(asset.id),
  )
}
