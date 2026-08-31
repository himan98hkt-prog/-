/**
 * 행사 하나를 파일 한 개로 내보내고 가져오기.
 *
 * 왜 필요한가. 원장님은 학원 컴퓨터에서 명단을 넣으시고, 집에서 인쇄물 문구를
 * 다듬으신다. 컴퓨터를 바꾸시는 해도 있다. 지금은 그때 처음부터 다시 하셔야 한다.
 *
 * 담는 것 — 행사 정보 · 명단 · 그 명단이 쓰는 사진.
 * 담지 않는 것 — 학부모 회신(개인 것이라 옮길 물건이 아니다) · 학원 계정.
 *
 * 파일은 이 컴퓨터에서 나와 이 컴퓨터로 들어간다. 어디로도 올라가지 않는다.
 */
import type { AcademyAsset } from '@/lib/assets'
import type { EventRecord, EventStudent } from '@/lib/types'

export const BUNDLE_VERSION = 1
export const BUNDLE_KIND = 'pianoevent.bundle'

export interface BundleStudent {
  student_name: string
  piece_title: string
  composer: string
  duration_sec: number | null
  level: EventStudent['level']
  note: string | null
  mc_script: string | null
  /** 보관함 사진을 가리키는 번호. 사진 자체는 assets 에 함께 담긴다 */
  photo_asset_id: string | null
  photo_asset_ids: string[] | null
}

export interface EventBundle {
  kind: typeof BUNDLE_KIND
  version: number
  exported_at: string
  academy_name: string
  event: {
    title: string
    type: EventRecord['type']
    event_at: string
    venue: string
    theme: EventRecord['theme']
    greeting: string | null
    mc_opening: string | null
    mc_closing: string | null
    design_theme: string | null
    design_template: string | null
    design_copy: Record<string, string> | null
    stage_prefs: EventRecord['stage_prefs']
    video_prefs: EventRecord['video_prefs']
    video_url: string | null
  }
  students: BundleStudent[]
  assets: AcademyAsset[]
}

/** 명단이 실제로 쓰는 사진만 담는다 — 보관함 전체를 넣으면 파일이 쓸데없이 커진다 */
export function usedAssetIds(students: EventStudent[]): string[] {
  const ids = new Set<string>()
  for (const s of students) {
    if (s.photo_asset_id) ids.add(s.photo_asset_id)
    for (const id of s.photo_asset_ids ?? []) ids.add(id)
  }
  return [...ids]
}

export function buildBundle(input: {
  academyName: string
  event: EventRecord
  students: EventStudent[]
  assets: AcademyAsset[]
  now?: string
}): EventBundle {
  const used = new Set(usedAssetIds(input.students))
  return {
    kind: BUNDLE_KIND,
    version: BUNDLE_VERSION,
    exported_at: input.now ?? new Date().toISOString(),
    academy_name: input.academyName,
    event: {
      title: input.event.title,
      type: input.event.type,
      event_at: input.event.event_at,
      venue: input.event.venue,
      theme: input.event.theme,
      greeting: input.event.greeting,
      mc_opening: input.event.mc_opening,
      mc_closing: input.event.mc_closing,
      design_theme: input.event.design_theme,
      design_template: input.event.design_template,
      design_copy: input.event.design_copy,
      stage_prefs: input.event.stage_prefs,
      video_prefs: input.event.video_prefs,
      video_url: input.event.video_url,
    },
    students: input.students.map((s) => ({
      student_name: s.student_name,
      piece_title: s.piece_title,
      composer: s.composer,
      duration_sec: s.duration_sec,
      level: s.level,
      note: s.note,
      mc_script: s.mc_script ?? null,
      photo_asset_id: s.photo_asset_id ?? null,
      photo_asset_ids: s.photo_asset_ids ?? null,
    })),
    assets: input.assets.filter((a) => used.has(a.id)),
  }
}

export class BundleError extends Error {}

const LEVELS: EventStudent['level'][] = ['beginner', 'intermediate', 'advanced', 'ensemble']
const TYPES: EventRecord['type'][] = ['recital', 'season']

/**
 * 남이 준 파일을 읽는다. 사람이 실수로 다른 파일을 끌어다 놓는 일이 훨씬 흔하므로
 * 오류 문구는 "무엇이 잘못됐는지" 가 아니라 "무엇을 하시면 되는지" 로 적는다.
 */
export function parseBundle(text: string): EventBundle {
  let raw: unknown
  try {
    raw = JSON.parse(text)
  } catch {
    throw new BundleError('행사 파일이 아닙니다. 내보내기로 받은 .json 파일을 골라 주세요.')
  }
  if (!raw || typeof raw !== 'object') throw new BundleError('행사 파일이 아닙니다.')
  const body = raw as Record<string, unknown>
  if (body.kind !== BUNDLE_KIND) {
    throw new BundleError('행사 파일이 아닙니다. 내보내기로 받은 .json 파일을 골라 주세요.')
  }
  if (Number(body.version) > BUNDLE_VERSION) {
    throw new BundleError('더 새 판에서 내보낸 파일입니다. 프로그램을 새로 받아 주세요.')
  }
  const event = body.event as Record<string, unknown> | undefined
  if (!event || typeof event.title !== 'string' || !event.title.trim()) {
    throw new BundleError('파일 안에 행사 이름이 없습니다.')
  }

  const students = Array.isArray(body.students) ? body.students : []
  const assets = Array.isArray(body.assets) ? body.assets : []

  return {
    kind: BUNDLE_KIND,
    version: Number(body.version) || 1,
    exported_at: str(body.exported_at) ?? new Date().toISOString(),
    academy_name: str(body.academy_name) ?? '',
    event: {
      title: event.title.trim().slice(0, 120),
      type: TYPES.includes(event.type as EventRecord['type']) ? (event.type as EventRecord['type']) : 'recital',
      event_at: str(event.event_at) ?? new Date().toISOString(),
      venue: str(event.venue) ?? '',
      theme: (str(event.theme) as EventRecord['theme']) ?? null,
      greeting: str(event.greeting),
      mc_opening: str(event.mc_opening),
      mc_closing: str(event.mc_closing),
      design_theme: str(event.design_theme),
      design_template: str(event.design_template),
      design_copy: (event.design_copy as Record<string, string> | null) ?? null,
      stage_prefs: (event.stage_prefs as EventRecord['stage_prefs']) ?? null,
      video_prefs: (event.video_prefs as EventRecord['video_prefs']) ?? null,
      video_url: str(event.video_url),
    },
    students: students
      .map((s): BundleStudent | null => {
        if (!s || typeof s !== 'object') return null
        const row = s as Record<string, unknown>
        const name = str(row.student_name)
        if (!name) return null
        const duration = Number(row.duration_sec)
        return {
          student_name: name.slice(0, 40),
          piece_title: (str(row.piece_title) ?? '').slice(0, 120),
          composer: (str(row.composer) ?? '').slice(0, 80),
          duration_sec: Number.isFinite(duration) && duration > 0 ? Math.round(duration) : null,
          level: LEVELS.includes(row.level as EventStudent['level'])
            ? (row.level as EventStudent['level'])
            : 'beginner',
          note: str(row.note),
          mc_script: str(row.mc_script),
          photo_asset_id: str(row.photo_asset_id),
          photo_asset_ids: Array.isArray(row.photo_asset_ids)
            ? row.photo_asset_ids.filter((v): v is string => typeof v === 'string')
            : null,
        }
      })
      .filter((s): s is BundleStudent => s !== null),
    assets: assets.filter(
      (a): a is AcademyAsset =>
        !!a &&
        typeof a === 'object' &&
        typeof (a as AcademyAsset).id === 'string' &&
        typeof (a as AcademyAsset).url === 'string',
    ),
  }
}

function str(v: unknown): string | null {
  return typeof v === 'string' && v.trim() ? v.trim() : null
}

/** 파일 이름 — 원장님 내려받기 폴더에서 알아보실 수 있게 */
export function bundleFilename(title: string, at: string): string {
  const day = at.slice(0, 10)
  const safe = title.replace(/[\\/:*?"<>|]/g, ' ').trim() || '행사'
  return `${safe} ${day}.json`
}

/** 가져온 뒤 화면에 적을 한 줄 */
export function bundleSummary(bundle: EventBundle): string {
  const people = new Set(bundle.students.map((s) => s.student_name)).size
  const photos = bundle.assets.length
  const parts = [`아이 ${people}명`, `무대 ${bundle.students.length}번`]
  if (photos > 0) parts.push(`사진 ${photos}장`)
  return `${bundle.event.title} — ${parts.join(' · ')}`
}

/* ─────────────────────────────────────────────────────────────────
   작년 파일로 올해 만들기
   ───────────────────────────────────────────────────────────────── */

/**
 * 행사 이름을 한 해 밀어 준다.
 *
 * "제12회 정기 연주회" → "제13회 정기 연주회"
 * "2025 봄 발표회"     → "2026 봄 발표회"
 * 규칙에 안 걸리면 **건드리지 않는다.** 지어내 바꾸면 원장님이 못 알아보신다.
 */
export function nextTitle(title: string): string {
  const round = title.match(/제\s*(\d+)\s*회/)
  if (round) return title.replace(round[0], `제${Number(round[1]) + 1}회`)

  const year = title.match(/(19|20)\d{2}/)
  if (year) return title.replace(year[0], String(Number(year[0]) + 1))

  return title
}

/** 날짜를 한 해 뒤로. 2월 29일은 그해에 없을 수 있어 28일로 내린다 */
export function nextYear(iso: string): string {
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return iso
  const moved = new Date(at)
  moved.setFullYear(at.getFullYear() + 1)
  // 2월 29일 → 다음 해 3월 1일로 넘어가 버리는 것을 막는다
  if (moved.getMonth() !== at.getMonth()) moved.setDate(0)
  return moved.toISOString()
}

/**
 * 작년 파일을 올해 것으로 손봐 준다.
 *
 * 무엇을 남기고 무엇을 비우는가가 전부다.
 *  남긴다 — 아이 이름 · 난이도 · 사진 · 인쇄물 설정 (학원은 해마다 같은 얼굴이다)
 *  비운다 — 연주곡 · 작곡가 · 시간 · 사회자 멘트 (올해 곡은 올해 정하신다)
 *
 * 작년 멘트를 남겨 두면 "작년에 처음 무대에 섰던" 아이 이야기가 올해 대본에 그대로
 * 실린다. 그건 남기는 것이 아니라 사고다.
 */
export function freshenBundle(bundle: EventBundle, at?: { title?: string; event_at?: string }): EventBundle {
  return {
    ...bundle,
    event: {
      ...bundle.event,
      title: at?.title?.trim() || nextTitle(bundle.event.title),
      event_at: at?.event_at || nextYear(bundle.event.event_at),
      mc_opening: null,
      mc_closing: null,
    },
    students: bundle.students.map((s) => ({
      ...s,
      piece_title: '',
      composer: '',
      duration_sec: null,
      mc_script: null,
    })),
  }
}

/** 가져오기 전에 무엇이 달라지는지 한 줄로 */
export function freshenSummary(bundle: EventBundle): string {
  const fresh = freshenBundle(bundle)
  const people = new Set(fresh.students.map((s) => s.student_name)).size
  return `${fresh.event.title} · ${fresh.event.event_at.slice(0, 10)} — 아이 ${people}명은 그대로, 곡은 비웁니다`
}
