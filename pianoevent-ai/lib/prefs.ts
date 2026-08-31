import { DESIGN_THEMES } from '@/lib/design/themes'
import { STAGE_BACKDROPS } from '@/lib/stage/backdrops'
import { PHOTO_SHAPES, STAGE_LAYOUTS } from '@/lib/stage/layouts'
import { VIDEO_TEMPLATES } from '@/lib/video/templates'

/**
 * 무대 화면·감동영상 설정을 행사에 저장한다.
 *
 * 원장님은 테마를 고르고 배경을 맞추고 글자 자리를 잡는 데 한참을 쓰신다.
 * 그런데 창을 닫으면 전부 사라진다 — 다음 해에 처음부터 다시 한다.
 *
 * 그래서 고른 값을 행사에 붙여 둔다. 사진은 이미 보관함에 있으므로,
 * 설정만 있으면 **작년 것 그대로** 열린다.
 *
 * 값은 원장님 브라우저에서 오므로 그대로 믿지 않는다. 여기 적힌 키만,
 * 여기 적힌 범위 안에서만 받는다. 모르는 키는 조용히 버린다 —
 * 설정 하나가 잘못됐다고 저장 전체가 실패하면 그게 더 불편하다.
 */

export type PrefValue = string | number | boolean

export type PrefRule =
  | { type: 'enum'; values: readonly string[] }
  | { type: 'bool' }
  | { type: 'num'; min: number; max: number }
  | { type: 'text'; max: number }

export type PrefSpec = Record<string, PrefRule>

export type Prefs = Record<string, PrefValue>

const themeIds = () => DESIGN_THEMES.map((t) => t.id)

/** 무대 화면(연주회장 스크린)에서 원장님이 고르는 것들 */
export const STAGE_PREF_SPEC: PrefSpec = {
  theme: { type: 'enum', values: themeIds() },
  layout: { type: 'enum', values: STAGE_LAYOUTS.map((l) => l.id) },
  shape: { type: 'enum', values: PHOTO_SHAPES.map((s) => s.id) },
  backdrop: { type: 'enum', values: STAGE_BACKDROPS.map((b) => b.id) },
  dark: { type: 'bool' },
  show_commentary: { type: 'bool' },
  show_sections: { type: 'bool' },
  show_agenda: { type: 'bool' },
  show_photos: { type: 'bool' },
}

/** 감동영상 편집기에서 고르는 것들 */
export const VIDEO_PREF_SPEC: PrefSpec = {
  theme: { type: 'enum', values: themeIds() },
  template: { type: 'enum', values: VIDEO_TEMPLATES.map((t) => t.id) },
  size: { type: 'enum', values: ['720', '1080'] },
  logo_place: { type: 'enum', values: ['none', 'top-left', 'top-right', 'bottom-left', 'bottom-right'] },
  captions: { type: 'bool' },
  messages: { type: 'bool' },
  student_seconds: { type: 'num', min: 1.5, max: 12 },
  title_seconds: { type: 'num', min: 1.5, max: 12 },
  gallery_seconds: { type: 'num', min: 1.5, max: 12 },
  closing: { type: 'text', max: 120 },
}

/** 값 하나를 규칙에 맞게 다듬는다. 맞지 않으면 null — 부르는 쪽에서 버린다 */
export function sanitizePref(rule: PrefRule, value: unknown): PrefValue | null {
  switch (rule.type) {
    case 'enum':
      return typeof value === 'string' && rule.values.includes(value) ? value : null
    case 'bool':
      return typeof value === 'boolean' ? value : null
    case 'num': {
      const num = typeof value === 'number' ? value : Number(value)
      if (!Number.isFinite(num)) return null
      // 범위를 벗어나면 버리지 않고 끝에 붙인다 — 슬라이더를 끝까지 민 것과 같다
      return Math.min(rule.max, Math.max(rule.min, Math.round(num * 10) / 10))
    }
    case 'text': {
      if (typeof value !== 'string') return null
      const text = value.trim().slice(0, rule.max)
      return text || null
    }
  }
}

/** 통째로 받은 설정에서 아는 것만 골라 낸다 */
export function sanitizePrefs(spec: PrefSpec, input: unknown): Prefs {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return {}
  const source = input as Record<string, unknown>
  const out: Prefs = {}
  for (const [key, rule] of Object.entries(spec)) {
    if (!(key in source)) continue
    const value = sanitizePref(rule, source[key])
    if (value !== null) out[key] = value
  }
  return out
}

/** 저장된 설정에서 값 하나를 꺼낸다 — 없거나 이상하면 기본값 */
export function prefString<T extends string>(prefs: Prefs | null | undefined, key: string, fallback: T): T {
  const value = prefs?.[key]
  return typeof value === 'string' && value ? (value as T) : fallback
}

export function prefBool(prefs: Prefs | null | undefined, key: string, fallback: boolean): boolean {
  const value = prefs?.[key]
  return typeof value === 'boolean' ? value : fallback
}

export function prefNumber(prefs: Prefs | null | undefined, key: string, fallback: number): number {
  const value = prefs?.[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

/** 저장된 것이 있는가 — 화면에 "작년 것 불러오기" 를 띄울지 정한다 */
export function hasPrefs(prefs: Prefs | null | undefined): boolean {
  return !!prefs && Object.keys(prefs).length > 0
}
