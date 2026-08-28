import { formatLength } from '@/lib/video/storyboard'

/**
 * 만든 토막들을 한 편으로 잇기.
 *
 * 긴 영상은 두세 토막으로 나눠 만드는 편이 낫다(중간에 끊겨도 잃는 것이 적다).
 * 그런데 학부모에게 보낼 때는 한 편이어야 한다.
 *
 * **파일을 그냥 이어 붙일 수는 없다.** MP4·WebM 은 앞머리에 전체 길이와 자리표가
 * 들어 있어서, 두 파일을 바이트로 붙이면 재생기마다 다르게 굴고 길이가 어긋난다.
 * "대개 재생되는" 파일을 학부모께 보내시게 할 수는 없다.
 *
 * 그래서 **다시 한 번 담는다** — 토막을 차례로 틀면서 그 화면을 새로 녹화한다.
 * 토막 길이의 합만큼 시간이 걸린다. 대신 나오는 것은 진짜 한 편이다.
 * (그 사실을 화면에도 그대로 적어 둔다. 눌러 놓고 기다리다 속았다고 느끼면 안 된다)
 *
 * 이 파일은 계산만 한다 — 실제로 담는 일은 components/video/video-studio.tsx.
 */

export interface VideoPart {
  id: string
  /** 화면에 보여 줄 이름 */
  label: string
  /** blob URL */
  url: string
  /** 초. 아직 못 읽었으면 0 */
  seconds: number
  /** 이 자리에서 만든 것인가 — 파일에서 가져온 것과 구분해 보여 준다 */
  made: boolean
}

/** 토막 전체 길이(초) */
export function partsSeconds(parts: VideoPart[]): number {
  return parts.reduce((sum, part) => sum + (Number.isFinite(part.seconds) ? part.seconds : 0), 0)
}

/** 이을 수 있는가 — 두 토막부터 의미가 있다 */
export function canJoin(parts: VideoPart[]): boolean {
  return parts.length >= 2 && parts.every((part) => part.seconds > 0)
}

/** 왜 아직 이을 수 없는지 한 줄로 (이을 수 있으면 null) */
export function joinBlocker(parts: VideoPart[]): string | null {
  if (parts.length === 0) return '아직 만든 토막이 없습니다.'
  if (parts.length === 1) return '토막이 하나뿐입니다. 두 개부터 이을 수 있습니다.'
  if (parts.some((part) => part.seconds <= 0)) return '길이를 읽지 못한 토막이 있습니다.'
  return null
}

/** "3토막 · 8분 20초 — 잇는 데 그만큼 걸립니다" */
export function joinLabel(parts: VideoPart[]): string {
  return `${parts.length}토막 · ${formatLength(partsSeconds(parts))}`
}

/** 토막 하나를 위·아래로 옮긴다 */
export function movePart(parts: VideoPart[], index: number, delta: number): VideoPart[] {
  const target = index + delta
  if (index < 0 || index >= parts.length || target < 0 || target >= parts.length) return parts
  const next = [...parts]
  const [moved] = next.splice(index, 1)
  next.splice(target, 0, moved)
  return next
}

/**
 * 이어 붙인 파일 이름.
 * 토막 이름을 그대로 이으면 길어지므로 행사 이름으로 되돌린다.
 */
export function joinedName(eventTitle: string, ext: string): string {
  const clean = eventTitle.replace(/[\\/:*?"<>|]/g, ' ').trim() || '연주회'
  return `${clean} 감동영상 (한 편).${ext}`
}
