import { describe, expect, it } from 'vitest'
import { soundPieces } from '@/lib/video/fast-export'
import { buildTimeline } from '@/lib/video/render'
import type { VideoScene } from '@/lib/video/storyboard'

/**
 * **빠르게 담을 때의 소리 자리.**
 *
 * 실시간 녹화는 스피커로 흐르는 소리를 그대로 받았으므로 자리를 계산할 일이 없었다.
 * 빠른 길은 파일을 직접 읽어 섞으므로, 어느 자리를 쓰는지 **여기서 틀리면**
 * 아이 얼굴과 소리가 따로 논다 — 게다가 다 만들고 틀어 보기 전까지 모른다.
 */
const scene = (over: Partial<VideoScene>): VideoScene => ({
  id: 'x',
  kind: 'student',
  seconds: 4,
  ...over,
})

describe('soundPieces', () => {
  it('음악이 없고 동영상도 없으면 얹을 소리가 없다', () => {
    const line = buildTimeline([scene({ id: 'a' }), scene({ id: 'b' })])
    expect(soundPieces(line, () => 0, null)).toEqual([])
  })

  it('배경음악은 처음부터, 고르신 자리에서, 고르신 크기로 · 앞뒤를 줄인다', () => {
    const line = buildTimeline([scene({ id: 'a' })])
    const [music] = soundPieces(line, () => 0, { url: 'blob:m', start: 12, volume: 0.9 })
    expect(music).toEqual({ url: 'blob:m', at: 0, offset: 12, volume: 0.9, fade: true })
  })

  it('소리 크기는 0~1 을 넘지 않는다', () => {
    const line = buildTimeline([scene({ id: 'a' })])
    const loud = soundPieces(line, () => 0, { url: 'blob:m', volume: 4 })[0]
    const back = soundPieces(line, () => 0, { url: 'blob:m', volume: -1 })[0]
    expect(loud.volume).toBe(1)
    expect(back.volume).toBe(0)
  })

  it('동영상 장면은 그 장면이 시작하는 자리에 놓인다', () => {
    const line = buildTimeline([
      scene({ id: 'a', seconds: 5 }),
      scene({ id: 'b', seconds: 3 }),
      scene({ id: 'c', kind: 'clip', clip: 'blob:v', seconds: 6 }),
    ])
    const [clip] = soundPieces(line, () => 30, null)
    expect(clip.at).toBe(8)
    expect(clip.seconds).toBe(6)
  })

  it('잘라 쓰기로 하신 자리에서 소리도 시작한다', () => {
    const line = buildTimeline([scene({ id: 'c', kind: 'clip', clip: 'blob:v', seconds: 6, clipStart: 5 })])
    expect(soundPieces(line, () => 30, null)[0].offset).toBe(5)
  })

  it('너무 뒤로 미신 자리는 화면과 똑같이 당겨 쓴다', () => {
    // 10초짜리에 6초 장면 — 8초부터는 2초가 빈다. 화면은 4초로 당겨 쓴다(clipWindow).
    const line = buildTimeline([scene({ id: 'c', kind: 'clip', clip: 'blob:v', seconds: 6, clipStart: 8 })])
    expect(soundPieces(line, () => 10, null)[0].offset).toBe(4)
  })

  it('길이를 모르는 동영상도 빠뜨리지 않는다 — 소리는 파일에서 읽어 오므로', () => {
    const line = buildTimeline([scene({ id: 'c', kind: 'clip', clip: 'blob:v', seconds: 6, clipStart: 3 })])
    const pieces = soundPieces(line, () => 0, null)
    expect(pieces).toHaveLength(1)
    expect(pieces[0].offset).toBe(3)
  })

  it('음악과 동영상이 함께 있으면 둘 다 얹는다 · 음악이 먼저', () => {
    const line = buildTimeline([
      scene({ id: 'a', seconds: 4 }),
      scene({ id: 'c', kind: 'clip', clip: 'blob:v', seconds: 6 }),
      scene({ id: 'd', kind: 'clip', clip: 'blob:w', seconds: 5 }),
    ])
    const pieces = soundPieces(line, () => 20, { url: 'blob:m' })
    expect(pieces.map((p) => p.url)).toEqual(['blob:m', 'blob:v', 'blob:w'])
    expect(pieces.map((p) => p.at)).toEqual([0, 4, 10])
  })

  it('사진 장면은 소리를 얹지 않는다', () => {
    const line = buildTimeline([
      scene({ id: 'a', image: 'blob:p' }),
      scene({ id: 'b', kind: 'message' }),
    ])
    expect(soundPieces(line, () => 20, null)).toEqual([])
  })
})
