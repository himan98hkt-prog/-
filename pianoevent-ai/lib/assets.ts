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

/** 보관함 전체 장수 상한 — 실수로 수십 장을 올려 저장소를 채우지 않게 */
export const ASSET_MAX_COUNT = 40

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
