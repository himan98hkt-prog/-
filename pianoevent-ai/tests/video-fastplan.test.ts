import { describe, expect, it } from 'vitest'
import { isDowngrade } from '@/lib/video/fast-export'
import type { FastPlan } from '@/lib/video/fast-export'

/**
 * **빠른 길이 파일을 나쁘게 만들면 안 된다.**
 *
 * 영상을 빨리 뽑는 것보다 중요한 것이 있다 — 그 파일이 파워포인트에 들어가고
 * 카카오톡으로 보내져야 한다. 빨라진 대신 안 열리는 파일이 나오면 원장님은
 * **연주회 당일에** 그것을 아신다. 그래서 이 규칙만은 검사로 못박아 둔다.
 */
const mp4Aac: FastPlan = {
  container: 'mp4', videoCodec: 'avc1.4D002A', muxVideo: 'avc',
  audioCodec: 'mp4a.40.2', muxAudio: 'aac', mimeType: 'video/mp4',
}
const mp4Opus: FastPlan = {
  container: 'mp4', videoCodec: 'avc1.4D002A', muxVideo: 'avc',
  audioCodec: 'opus', muxAudio: 'opus', mimeType: 'video/mp4',
}
const webm: FastPlan = {
  container: 'webm', videoCodec: 'vp09.00.10.08', muxVideo: 'vp9',
  audioCodec: 'opus', muxAudio: 'opus', mimeType: 'video/webm',
}

const AAC_RECORDER = 'video/mp4;codecs="avc1.42E01E,mp4a.40.2"'
const MP4_RECORDER = 'video/mp4;codecs=avc1'
const WEBM_RECORDER = 'video/webm;codecs="vp9,opus"'

describe('isDowngrade', () => {
  it('MP4 를 만들 수 있는 컴퓨터에서 WebM 으로 내려가지 않는다', () => {
    expect(isDowngrade(webm, MP4_RECORDER, false)).toBe(true)
    expect(isDowngrade(webm, AAC_RECORDER, true)).toBe(true)
  })

  it('예전 방식도 WebM 뿐이면 WebM 이 내려가는 것이 아니다', () => {
    expect(isDowngrade(webm, WEBM_RECORDER, true)).toBe(false)
  })

  it('예전 방식이 AAC 를 넣을 수 있으면 Opus 로 내려가지 않는다', () => {
    // 여기서 Opus 를 쓰면 파워포인트에서 소리가 안 날 수 있다
    expect(isDowngrade(mp4Opus, AAC_RECORDER, true)).toBe(true)
  })

  it('소리를 안 얹으면 Opus 계획이어도 잃을 것이 없다', () => {
    // 소리 트랙 자체가 안 들어가므로 무엇으로 굽는지가 뜻이 없다
    expect(isDowngrade(mp4Opus, AAC_RECORDER, false)).toBe(false)
  })

  it('예전 방식도 AAC 를 못 넣으면 MP4+Opus 는 같은 것이다 — 세 배 빨리 줄 뿐', () => {
    // 설치본에서 직접 본 자리다: MediaRecorder 가 만든 것도 MP4+Opus 였다
    expect(isDowngrade(mp4Opus, MP4_RECORDER, true)).toBe(false)
  })

  it('AAC 계획은 언제나 내려가는 것이 아니다', () => {
    expect(isDowngrade(mp4Aac, AAC_RECORDER, true)).toBe(false)
    expect(isDowngrade(mp4Aac, MP4_RECORDER, true)).toBe(false)
    expect(isDowngrade(mp4Aac, WEBM_RECORDER, true)).toBe(false)
  })

  it('예전 방식이 아무것도 못 만들면 견줄 것이 없다', () => {
    expect(isDowngrade(webm, null, true)).toBe(false)
  })
})
