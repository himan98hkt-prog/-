import { formatEventDate } from '@/lib/format'
import type { EventRecord, ProgramPlan } from '@/lib/types'

/**
 * 감동영상 — 연주회 전에 틀거나, 끝나고 학부모에게 보내는 짧은 영상.
 *
 * 원장님이 하시던 일은 이렇다. 아이들 사진을 모으고, 무비메이커를 열고,
 * 한 장씩 끌어다 놓고, 이름을 자막으로 치고, 음악을 깔고, 길이를 맞춘다.
 * 30명이면 반나절이 간다.
 *
 * 여기서는 **명단이 이미 있다.** 누가 몇 번째로 무슨 곡을 치는지 알고 있으므로
 * 장면 순서와 자막은 계산하면 된다. 원장님은 사진만 고르시면 된다.
 *
 * 이 파일은 순수 계산만 한다 — 그려 내는 일은 `components/video/video-studio.tsx`.
 */

export type SceneKind = 'title' | 'student' | 'gallery' | 'clip' | 'closing'

export interface VideoScene {
  id: string
  kind: SceneKind
  /** 이 장면이 화면에 머무는 시간(초) */
  seconds: number
  /** 큰 글씨 */
  headline?: string
  /** 큰 글씨 아래 한 줄 */
  sub?: string
  /** 화면 위 작은 글씨 */
  eyebrow?: string
  /** 사진 주소 (data URI · blob URL) */
  image?: string
  /** 동영상 주소 (blob URL) */
  clip?: string
}

export interface StoryboardOptions {
  /** 아이 한 명이 화면에 머무는 시간(초) */
  student_seconds: number
  /** 표지·마무리 화면 시간(초) */
  title_seconds: number
  /** 추가 사진 한 장이 머무는 시간(초) */
  gallery_seconds: number
  /** 자막(이름·곡)을 넣을지 */
  captions: boolean
}

export const DEFAULT_STORYBOARD_OPTIONS: StoryboardOptions = {
  student_seconds: 3.5,
  title_seconds: 4,
  gallery_seconds: 3,
  captions: true,
}

/** 영상에 덧붙이는 자료 — 그 자리에서 고른 파일들 */
export interface ExtraMedia {
  id: string
  kind: 'image' | 'video'
  url: string
  label: string
  /** 동영상일 때만 — 실제 길이(초) */
  duration?: number
}

export interface StoryboardInput {
  event: EventRecord
  plan: ProgramPlan
  academyName: string
  /** 학생 id → 사진 주소 */
  photos: Record<string, string>
  /** 연습 장면 사진·동영상 */
  extras?: ExtraMedia[]
  options?: StoryboardOptions
  /** 마무리 문구 — 원장님이 고쳐 쓴다 */
  closing?: string
}

/** 동영상 한 편이 지나치게 길어지지 않게 — 15분을 넘기면 아무도 끝까지 보지 않는다 */
export const MAX_TOTAL_SEC = 15 * 60
/** 한 장면 최소·최대 */
export const SCENE_MIN_SEC = 1.5
export const SCENE_MAX_SEC = 12

export function buildStoryboard({
  event,
  plan,
  academyName,
  photos,
  extras = [],
  options = DEFAULT_STORYBOARD_OPTIONS,
  closing,
}: StoryboardInput): VideoScene[] {
  const clamp = (value: number) => Math.min(SCENE_MAX_SEC, Math.max(SCENE_MIN_SEC, value))
  const scenes: VideoScene[] = []

  scenes.push({
    id: 'title',
    kind: 'title',
    seconds: clamp(options.title_seconds),
    eyebrow: academyName,
    headline: event.title,
    sub: formatEventDate(event.event_at),
  })

  // 연습 사진이 있으면 앞에 한 묶음 — "이 무대까지 오는 동안"
  const images = extras.filter((item) => item.kind === 'image')
  const clips = extras.filter((item) => item.kind === 'video')
  if (images.length > 0) {
    scenes.push({
      id: 'gallery-intro',
      kind: 'title',
      seconds: clamp(options.title_seconds * 0.75),
      headline: '이 무대까지 오는 동안',
      sub: '연습실에서 보낸 시간들',
    })
    images.forEach((item, index) => {
      scenes.push({
        id: `gallery-${item.id}`,
        kind: 'gallery',
        seconds: clamp(options.gallery_seconds),
        image: item.url,
        sub: options.captions ? item.label : undefined,
        eyebrow: `${index + 1} / ${images.length}`,
      })
    })
  }

  for (const clip of clips) {
    scenes.push({
      id: `clip-${clip.id}`,
      kind: 'clip',
      // 동영상은 실제 길이만큼 튼다. 너무 길면 잘라 낸다
      seconds: Math.min(SCENE_MAX_SEC * 2, Math.max(SCENE_MIN_SEC, clip.duration ?? 6)),
      clip: clip.url,
      sub: options.captions ? clip.label : undefined,
    })
  }

  if (plan.items.length > 0) {
    scenes.push({
      id: 'roster-intro',
      kind: 'title',
      seconds: clamp(options.title_seconds * 0.75),
      headline: '오늘 무대에 서는 아이들',
      sub: `${plan.items.length}명`,
    })
    for (const item of plan.items) {
      const student = item.student
      scenes.push({
        id: `student-${student.id}`,
        kind: 'student',
        seconds: clamp(options.student_seconds),
        image: photos[student.id],
        eyebrow: `${item.order_no}번째 무대`,
        headline: student.student_name,
        sub: options.captions
          ? [student.piece_title, student.composer].filter(Boolean).join(' · ') || undefined
          : undefined,
      })
    }
  }

  scenes.push({
    id: 'closing',
    kind: 'closing',
    seconds: clamp(options.title_seconds * 1.2),
    headline: closing?.trim() || '오늘 이 무대에 선 모든 아이들에게',
    sub: academyName,
  })

  return scenes
}

export function totalSeconds(scenes: VideoScene[]): number {
  return scenes.reduce((sum, scene) => sum + scene.seconds, 0)
}

/** 15분을 넘으면 아이 한 명당 시간을 줄여 맞춘다 — 잘라 내면 누군가 빠진다 */
export function fitToLimit(scenes: VideoScene[], limit = MAX_TOTAL_SEC): VideoScene[] {
  const total = totalSeconds(scenes)
  if (total <= limit) return scenes
  const fixed = scenes.filter((scene) => scene.kind === 'clip')
  const fixedSec = totalSeconds(fixed)
  const flexible = total - fixedSec
  const room = Math.max(0, limit - fixedSec)
  if (flexible <= 0 || room <= 0) return scenes
  const ratio = room / flexible
  // 0.1초 단위로 **내림**한다. 반올림하면 장면 수가 많을 때 조금씩 넘쳐 한도를 넘는다.
  // 최소 시간(SCENE_MIN_SEC)에 걸리는 장면이 많으면 결과가 한도보다 길 수 있다 —
  // 얼굴을 알아볼 수 없을 만큼 짧게 스치는 것보다 조금 긴 편이 낫다.
  return scenes.map((scene) =>
    scene.kind === 'clip'
      ? scene
      : { ...scene, seconds: Math.max(SCENE_MIN_SEC, Math.floor(scene.seconds * ratio * 10) / 10) },
  )
}

export function formatLength(seconds: number): string {
  const total = Math.round(seconds)
  const m = Math.floor(total / 60)
  const s = total % 60
  return m > 0 ? `${m}분 ${String(s).padStart(2, '0')}초` : `${s}초`
}
