import { formatEventDate } from '@/lib/format'
import { groupProgram, performerKey } from '@/lib/program/appearances'
import type { EventRecord, ProgramPlan } from '@/lib/types'
import type { CaptionAnim, IconAnim, PhotoMotion, TransitionKind } from '@/lib/video/templates'

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

export type SceneKind = 'title' | 'student' | 'gallery' | 'clip' | 'message' | 'closing'

/**
 * 화면에 글자를 어디에 놓을지.
 * 사진 위에 글자를 얹을 때 얼굴을 가리지 않도록 원장님이 고른다.
 */
export type CaptionPlace = 'bottom' | 'top' | 'center' | 'none'

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
  /**
   * 이 장면에서 넘겨 가며 보여 줄 사진들 (`image` 가 첫 장).
   * 한 아이가 3~4초 머무는데 사진이 한 장이면 정지 화면에 가깝다.
   */
  images?: string[]
  /** 동영상 주소 (blob URL) */
  clip?: string
  /**
   * 동영상의 **어디서부터** 쓸 것인가(초).
   *
   * 휴대폰으로 찍은 영상은 앞이 흔들리거나 「자, 시작」 같은 말이 들어 있다.
   * 그대로 넣으면 그 부분이 그대로 영상에 남는다. 여기서 앞을 잘라 낸다.
   * 얼마나 쓸지는 장면 시간(`seconds`)이 정한다 — 자르는 자리 둘을 따로 두면
   * 「끝이 시작보다 앞」 같은 상태가 생기고, 그것을 막는 규칙이 또 필요해진다.
   */
  clipStart?: number
  /** 글자 자리 */
  caption?: CaptionPlace
  /**
   * 글 위에 작게 얹는 동그란 사진 — 응원을 보낸 분의 아이 얼굴.
   * 누구 부모님 말인지 객석이 알아본다.
   */
  badge?: string
  /** 원장님이 직접 고친 장면인가 — 명단이 바뀌어도 덮어쓰지 않는다 */
  edited?: boolean
  /**
   * 이 장면으로 **넘어올 때** 쓰는 효과. 비어 있으면 「어울리게」.
   * 첫 장면에는 넘어옴이 없으므로 쓰이지 않는다.
   */
  transition?: TransitionKind
  /** 자막이 나타나는 방식. 비어 있으면 「어울리게」 */
  captionAnim?: CaptionAnim
  /** 작은 그림이 움직이는 방식. 비어 있으면 「톡 나타나기」 */
  iconAnim?: IconAnim
  /** 사진 움직임 — 비어 있으면 템플릿이 정한 대로 */
  motion?: PhotoMotion
  /** 화면 한쪽에 얹는 작은 그림 (하트·음표·별 …) */
  icon?: SceneIconId
}

/**
 * 장면에 얹는 작은 그림.
 *
 * 밖에서 그림 파일을 가져오지 않는다 — 저작권도 걸리고, 인터넷 없이 열려야 한다.
 * 전부 **선으로 그린다**(canvas path). 그래서 테마 색을 그대로 입고, 아무리 키워도
 * 깨지지 않는다.
 */
export type SceneIconId =
  | 'heart'
  | 'note'
  | 'star'
  | 'sparkle'
  | 'flower'
  | 'clap'
  | 'trophy'
  | 'ribbon'
  | 'piano'
  | 'cake'

export const SCENE_ICONS: { id: SceneIconId; label: string }[] = [
  { id: 'heart', label: '하트' },
  { id: 'note', label: '음표' },
  { id: 'star', label: '별' },
  { id: 'sparkle', label: '반짝임' },
  { id: 'flower', label: '꽃' },
  { id: 'clap', label: '박수' },
  { id: 'trophy', label: '트로피' },
  { id: 'ribbon', label: '리본' },
  { id: 'piano', label: '건반' },
  { id: 'cake', label: '케이크' },
]

/** 표지·마무리처럼 얌전하게 넘어가야 하는 자리인가 */
export function isCalmScene(kind: SceneKind): boolean {
  return kind === 'title' || kind === 'closing' || kind === 'message'
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
  /** 학부모가 초대장에 남긴 응원 메시지를 마지막에 넣을지 */
  messages: boolean
}

export const DEFAULT_STORYBOARD_OPTIONS: StoryboardOptions = {
  student_seconds: 3.5,
  title_seconds: 4,
  gallery_seconds: 3,
  captions: true,
  messages: true,
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

/** 학부모가 초대장에서 남긴 응원 한 줄 */
export interface CheerMessage {
  name: string
  message: string
  /** 회신에 적어 주신 아이 이름 — 그 아이 얼굴을 함께 띄운다 */
  student?: string
}

/** 영상에 넣는 응원 메시지 수 — 다 넣으면 영상이 문자 낭독이 된다 */
export const MAX_MESSAGE_SCENES = 12

export interface StoryboardInput {
  event: EventRecord
  plan: ProgramPlan
  academyName: string
  /** 학생 id → 사진 주소 (대표 한 장) */
  photos: Record<string, string>
  /** 학생 id → 사진 여러 장. 있으면 이쪽이 먼저다 */
  photoSets?: Record<string, string[]>
  /** 학부모 응원 메시지 (초대장 회신에서 온다) */
  messages?: CheerMessage[]
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
/**
 * 올리신 동영상 한 개가 처음에 차지하는 최대 시간.
 *
 * 30초짜리 휴대폰 영상을 통째로 넣으면 그 아이 하나가 영상의 절반을 먹는다.
 * 앞머리만 쓰고, 어느 자리를 쓸지는 원장님이 미셔서 정하시게 둔다.
 */
export const CLIP_MAX_SEC = 12

export function buildStoryboard({
  event,
  plan,
  academyName,
  photos,
  photoSets = {},
  messages = [],
  extras = [],
  options = DEFAULT_STORYBOARD_OPTIONS,
  closing,
}: StoryboardInput): VideoScene[] {
  /**
   * 장면 시간을 범위 안에 넣고 **0.1초로 끊는다.**
   *
   * 「글자 수에 따라 조금 늘린다」 같은 셈은 3.6666666666666666 을 만든다.
   * 그 값이 콘티의 「3.6666666666666666초」로 그대로 나왔다 —
   * 원장님께 보여 드릴 숫자가 아니고, 고치실 때 입력칸에도 그대로 들어간다.
   */
  const clamp = (value: number) =>
    Math.round(Math.min(SCENE_MAX_SEC, Math.max(SCENE_MIN_SEC, value)) * 10) / 10
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
      // 짧은 것은 통째로 튼다. 긴 것은 앞머리만 쓰고, 어느 자리를 쓸지는
      // 장면 고치기의 「동영상에서 쓸 자리」로 원장님이 미신다 (clipWindow)
      seconds: Math.min(CLIP_MAX_SEC, Math.max(SCENE_MIN_SEC, clip.duration ?? 6)),
      clip: clip.url,
      sub: options.captions ? clip.label : undefined,
    })
  }

  if (plan.items.length > 0) {
    // 한 아이가 독주도 하고 듀엣도 하면 순서표에는 두 줄이지만,
    // 영상에서는 같은 얼굴이 두 번 지나가는 꼴이 된다. 사람 단위로 묶어 한 장면에 담는다.
    const performers = groupProgram(plan.items)
    scenes.push({
      id: 'roster-intro',
      kind: 'title',
      seconds: clamp(options.title_seconds * 0.75),
      headline: '오늘 무대에 서는 아이들',
      sub:
        performers.length === plan.items.length
          ? `${performers.length}명`
          : `${performers.length}명 · ${plan.items.length}곡`,
    })
    for (const performer of performers) {
      const first = performer.rows[0]
      const student = first.student
      // 사진은 그 아이 줄 어디에든 붙어 있으면 된다. 여러 장이면 넘겨 가며 보여 준다
      const shots: string[] = []
      for (const row of performer.rows) {
        for (const url of photoSets[row.student.id] ?? (photos[row.student.id] ? [photos[row.student.id]] : [])) {
          if (!shots.includes(url)) shots.push(url)
        }
      }
      const pieces = performer.rows
        .map((row) => [row.student.piece_title, row.student.composer].filter(Boolean).join(' · '))
        .filter(Boolean)
      // 사진이 여러 장이면 한 장에 최소 1.4초는 머물게 늘린다 — 스치면 얼굴이 안 남는다
      const base = options.student_seconds * (performer.rows.length > 1 ? 1.25 : 1)
      scenes.push({
        id: `student-${student.id}`,
        kind: 'student',
        seconds: clamp(Math.max(base, shots.length > 1 ? shots.length * 1.4 : 0)),
        image: shots[0],
        images: shots.length > 1 ? shots : undefined,
        eyebrow:
          performer.rows.length > 1
            ? `${performer.rows.map((row) => row.order_no).join(' · ')}번째 무대`
            : `${first.order_no}번째 무대`,
        headline: student.student_name,
        sub: options.captions ? pieces.join('  /  ') || undefined : undefined,
      })
    }
  }

  // 학부모가 초대장에 남긴 응원 — 이미 모여 있는 것을 영상 끝에 흘린다.
  // 시상식 전에 이 대목에서 객석이 조용해진다.
  const cheers = options.messages ? cleanMessages(messages) : []
  if (cheers.length > 0) {
    scenes.push({
      id: 'cheer-intro',
      kind: 'title',
      seconds: clamp(options.title_seconds * 0.75),
      headline: '부모님이 보내 주신 말',
      sub: `초대장에 남겨 주신 ${cheers.length}통`,
    })
    // 회신에 적힌 아이 이름으로 그 아이 얼굴을 찾는다 — 누구 부모님 말인지 보이게
    const faceByName = new Map<string, string>()
    for (const item of plan.items) {
      const key = performerKey(item.student.student_name)
      const shot = (photoSets[item.student.id] ?? [])[0] ?? photos[item.student.id]
      if (shot && !faceByName.has(key)) faceByName.set(key, shot)
    }
    cheers.forEach((cheer, index) => {
      scenes.push({
        id: `cheer-${index}`,
        kind: 'message',
        // 읽을 시간을 준다 — 글자 수에 따라 조금 늘린다
        seconds: clamp(3 + Math.min(3, cheer.message.length / 24)),
        headline: cheer.message,
        sub: `— ${cheer.name}`,
        caption: 'center',
        badge: cheer.student ? faceByName.get(performerKey(cheer.student)) : undefined,
      })
    })
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

/**
 * 영상에 넣을 만한 응원만 고른다.
 * 너무 긴 글은 화면에 다 들어가지 않고, 빈 글은 검은 화면이 된다.
 */
export function cleanMessages(messages: CheerMessage[], limit = MAX_MESSAGE_SCENES): CheerMessage[] {
  const seen = new Set<string>()
  const out: CheerMessage[] = []
  for (const item of messages) {
    const message = (item.message ?? '').trim().replace(/\s+/g, ' ')
    const name = (item.name ?? '').trim()
    if (!message || message.length > 90) continue
    if (seen.has(message)) continue
    seen.add(message)
    out.push({ name: name || '학부모님', message, student: item.student?.trim() || undefined })
    if (out.length >= limit) break
  }
  return out
}

export function totalSeconds(scenes: VideoScene[]): number {
  return scenes.reduce((sum, scene) => sum + scene.seconds, 0)
}

/** 맛보기 길이 — 이만큼만 먼저 만들어 보신다 */
export const TASTER_SEC = 30

/**
 * **30초만 먼저 만들어 보기.**
 *
 * 12분짜리 영상은 만드는 데도 12분이 걸린다 (화면을 그리면서 담기 때문에).
 * 그런데 그 12분을 다 기다리신 뒤에야 "글씨가 작네", "이 사진이 아닌데" 를 아신다.
 * 앞 30초만 먼저 만들어 보시면 그 자리에서 아신다.
 *
 * 앞에서부터 30초를 넘지 않는 데까지 담되, **최소 두 장면**은 넣는다 —
 * 제목 한 장만 나오면 아이가 어떻게 나오는지 못 보신다.
 * 전체가 이미 30초 안팎이면 맛보기가 뜻이 없으므로 `null` 을 준다.
 */
export function tasterRange(
  scenes: VideoScene[],
  seconds = TASTER_SEC,
  from = 0,
): { from: number; to: number } | null {
  if (scenes.length < 2) return null
  if (totalSeconds(scenes) <= seconds * 1.5) return null
  const start = Math.max(0, Math.min(from, scenes.length - 2))
  let sum = 0
  let to = start
  for (let i = start; i < scenes.length; i += 1) {
    sum += scenes[i].seconds
    if (sum > seconds && i > start) break
    to = i
  }
  return { from: start, to: Math.max(start + 1, to) }
}

/**
 * **앞 · 가운데 · 끝을 조금씩.**
 *
 * 앞 30초만 보시면 표지와 첫 아이까지만 아신다. 그런데 정작 걱정되는 것은
 * "끝까지 이 느낌인가", "마무리는 어떻게 나오나" 다. 그러려면 앞·가운데·끝을
 * 조금씩 이어 보셔야 한다.
 *
 * 장면을 잘라 내지는 않는다 — 장면 단위로 앞에서 하나, 가운데에서 하나, 끝에서 하나를
 * 고른다. 이어 놓으면 30초 안팎에 영상 전체의 분위기가 담긴다.
 * 장면이 너무 적으면 나눌 것이 없으므로 `null` 을 준다.
 */
export function tasterSpread(scenes: VideoScene[], seconds = TASTER_SEC): number[] | null {
  if (scenes.length < 5) return null
  if (totalSeconds(scenes) <= seconds * 1.5) return null

  const last = scenes.length - 1
  const middle = Math.floor(scenes.length / 2)
  const picked = [...new Set([0, middle, last])].sort((a, b) => a - b)

  // 아직 자리가 남으면 앞·가운데 사이에서 한 장면 더 — 30초를 알차게 쓴다
  const used = () => picked.reduce((sum, i) => sum + scenes[i].seconds, 0)
  for (const extra of [Math.floor(scenes.length / 4), Math.floor((scenes.length * 3) / 4)]) {
    if (picked.includes(extra)) continue
    if (used() + scenes[extra].seconds > seconds) break
    picked.push(extra)
  }

  return picked.sort((a, b) => a - b)
}

/**
 * 맛보기를 **어디서부터** 담을지.
 *
 * 앞 30초는 대개 표지와 인사말이다. 정작 보고 싶으신 것은 **아이가 나오는 화면**인데,
 * 그건 30초 뒤에 나온다. 그래서 시작 자리를 둘 준다 — 처음부터, 아이 장면부터.
 * 아이 장면이 맨 앞이면(표지를 끄셨다면) 하나만 준다.
 */
export interface TasterStart {
  id: 'head' | 'performers' | 'spread'
  label: string
  index: number
}

export function tasterStarts(scenes: VideoScene[]): TasterStart[] {
  const out: TasterStart[] = [{ id: 'head', label: '처음부터', index: 0 }]
  const first = scenes.findIndex((scene) => scene.kind === 'student')
  if (first > 0 && first < scenes.length - 1) {
    out.push({ id: 'performers', label: '아이 장면부터', index: first })
  }
  // 앞·가운데·끝을 조금씩 — 이어 붙이는 것이라 시작 자리가 하나가 아니다 (index 는 안 쓴다)
  if (tasterSpread(scenes)) out.push({ id: 'spread', label: '앞·가운데·끝', index: 0 })
  return out
}

/**
 * **맛보기를 보시고 나서 무엇을 만지면 되는가.**
 *
 * 30초를 보여 드리는 것까지는 했는데, 보시고 "글씨가 작네" 하신 다음이 없었다.
 * 그 화면 어디에 그 설정이 있는지 원장님은 모르신다. 그래서 흔히 걸리는 넷을
 * 그 자리에 붙여 둔다 — 무엇이 마음에 안 드는지 → 어디를 만지는지.
 *
 * 지어내지 않는다. 넷 다 이 화면에 실제로 있는 자리다.
 */
export interface TasterFix {
  /** 보시고 이런 생각이 드셨다면 */
  symptom: string
  /** 여기를 만지시면 됩니다 */
  where: string
  /** 어떻게 */
  how: string
}

export const TASTER_FIXES: TasterFix[] = [
  {
    symptom: '글씨가 작아 안 읽힙니다',
    where: '0 · 영상 템플릿',
    how: '글씨가 큰 템플릿으로 바꾸세요. "이름만 크게" 쪽이 뒷줄에서도 읽힙니다.',
  },
  {
    symptom: '사진이 이상하게 잘립니다',
    where: '아래 [만들어질 모습]',
    how: '그 장면을 누르면 장면 고치기가 열립니다. 글자 자리를 옮기거나, 명단에서 사진을 바꾸세요.',
  },
  {
    symptom: '너무 빨리 넘어갑니다',
    where: '4 · 모양과 길이',
    how: '아이 한 명당 시간을 늘리세요. 늘리면 전체 길이도 그만큼 늡니다.',
  },
  {
    symptom: '음악이 없어 허전합니다',
    where: '3 · 배경음악',
    how: '학원에서 쓰시던 음악 파일을 끌어다 놓으세요. 저작권 때문에 음악은 넣어 드리지 못합니다.',
  },
]

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

/** 장면 이름 — 미리보기 창에서 원장님이 알아볼 말로 */
export function sceneLabel(scene: VideoScene): string {
  switch (scene.kind) {
    case 'title':
      return scene.headline ?? '표지'
    case 'gallery':
      return scene.sub ? `연습 사진 · ${scene.sub}` : '연습 사진'
    case 'clip':
      return scene.sub ? `동영상 · ${scene.sub}` : '동영상'
    case 'student':
      return [scene.eyebrow, scene.headline].filter(Boolean).join(' · ')
    case 'message':
      return scene.sub ? `응원 ${scene.sub}` : '응원 메시지'
    case 'closing':
      return '마무리'
  }
}

/** 이 장면에 사진이 없어 이름만 나오는가 — 미리보기에서 표시해 준다 */
export function isTextOnly(scene: VideoScene): boolean {
  return scene.kind === 'student' && !scene.image
}

/**
 * 파일 이름 앞에 붙은 번호로 차례를 정한다.
 *
 * 원장님이 `01 입장.jpg` `02 리허설.jpg` 처럼 이름을 붙여 한꺼번에 고르면
 * 그 번호대로 늘어놓는다. 번호가 없으면 고른 차례를 그대로 쓴다.
 * (브라우저가 파일을 넘겨주는 차례는 들쭉날쭉해서 믿을 수 없다)
 */
export function leadingNumber(name: string): number | null {
  const match = /^\s*(\d{1,4})\s*[._\-)\s]/.exec(name) || /^\s*(\d{1,4})\s*$/.exec(name.replace(/\.[^.]+$/, ''))
  return match ? Number(match[1]) : null
}

export function sortByFileName<T extends { label: string }>(items: T[]): T[] {
  return [...items]
    .map((item, index) => ({ item, index, no: leadingNumber(item.label) }))
    .sort((a, b) => {
      if (a.no !== null && b.no !== null) return a.no - b.no || a.index - b.index
      if (a.no !== null) return -1
      if (b.no !== null) return 1
      return a.item.label.localeCompare(b.item.label, 'ko') || a.index - b.index
    })
    .map((entry) => entry.item)
}

/** 장면 하나를 위·아래로 옮긴다 */
export function moveScene(scenes: VideoScene[], index: number, delta: number): VideoScene[] {
  const target = index + delta
  if (index < 0 || index >= scenes.length || target < 0 || target >= scenes.length) return scenes
  const next = [...scenes]
  const [moved] = next.splice(index, 1)
  next.splice(target, 0, moved)
  return next
}

/**
 * 응원 메시지가 있는 구간 (머릿말 포함).
 *
 * 연주회 전날 밤에 영상을 만드는데 회신은 당일 아침에도 온다.
 * 그때 전체를 다시 만들 이유가 없다 — 응원 부분만 다시 만들어 뒤에 이으면 된다.
 */
export function cheerRange(scenes: VideoScene[]): { from: number; to: number } | null {
  const first = scenes.findIndex((scene) => scene.id === 'cheer-intro' || scene.kind === 'message')
  if (first < 0) return null
  let last = first
  for (let i = first; i < scenes.length; i += 1) {
    if (scenes[i].kind === 'message' || scenes[i].id === 'cheer-intro') last = i
  }
  return { from: first, to: last }
}

/**
 * 사진을 아직 안 넣은 아이들 — **이름으로** 돌려준다.
 *
 * 「사진이 없는 2명은 이름만 나옵니다」만 적어 두면, 원장님은 그 둘이 누구인지
 * 알아내려고 명단을 뒤지셔야 한다. 그러라고 만든 프로그램이 아니다.
 *
 * 세는 단위는 **곡이 아니라 사람**이다. 한 아이가 독주도 하고 듀엣도 하면 순서표에는
 * 두 줄이지만 사람은 하나다 — 줄로 세면 사진을 다 넣으셨는데도 「없는 사람이 있다」고
 * 나온다(실제로 그렇게 세고 있었다).
 */
export function missingPhotos(
  items: { student: { id: string; student_name: string } }[],
  photos: Record<string, string>,
): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const item of items) {
    const key = performerKey(item.student.student_name)
    if (seen.has(key)) continue
    seen.add(key)
    if (!photos[item.student.id]) out.push(item.student.student_name.trim())
  }
  return out
}

/** 동영상 장면에서 **어느 구간을 쓸 것인가** — 눌러 넣은 결과 */
export interface ClipWindow {
  /** 실제로 재생을 시작할 자리(초). 동영상 길이 안으로 눌러 넣은 값 */
  start: number
  /** 시작 자리를 밀 수 있는 가장 뒤. 이보다 뒤로 밀면 끝이 넘친다 */
  maxStart: number
  /** 동영상이 모자라 **멈춘 화면으로 남는** 시간(초). 0이면 딱 맞다 */
  short: number
}

/**
 * 자를 자리를 동영상 길이 안으로 눌러 넣는다.
 *
 * 원장님은 슬라이더를 끝까지 밀어 보신다. 그때 화면이 검게 남으면 고장으로 보인다 —
 * 그래서 넘치는 값은 **저장은 그대로 두되 쓸 때만** 당겨 쓴다. 되돌리실 수 있어야 하니까.
 * 길이를 아직 못 쟀으면(0) 누를 근거가 없으므로 적으신 값을 그대로 돌려준다.
 */
export function clipWindow(scene: Pick<VideoScene, 'seconds' | 'clipStart'>, length: number): ClipWindow {
  const asked = Math.max(0, scene.clipStart ?? 0)
  if (!(length > 0)) return { start: asked, maxStart: 0, short: 0 }
  const maxStart = Math.max(0, length - scene.seconds)
  const start = Math.min(asked, maxStart)
  return { start, maxStart, short: Math.max(0, scene.seconds - (length - start)) }
}
