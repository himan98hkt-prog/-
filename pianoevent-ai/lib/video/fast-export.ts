import { Muxer as Mp4Muxer, ArrayBufferTarget as Mp4Target } from 'mp4-muxer'
import { Muxer as WebmMuxer, ArrayBufferTarget as WebmTarget } from 'webm-muxer'
import type { FrameSource, RenderOptions } from '@/lib/video/render'
import { renderFrame, type Timeline } from '@/lib/video/render'
import { clipWindow } from '@/lib/video/storyboard'

/**
 * 영상을 **그리는 속도만큼 빨리** 담는다.
 *
 * 지금까지는 화면에 그려지는 것을 그대로 녹화했다(MediaRecorder). 눈에 보이는 대로 나오는
 * 대신 **영상 길이만큼 시간이 걸렸다** — 12분짜리는 12분. 그 12분 동안 원장님은 창을
 * 그대로 두고 기다리셔야 했고, 다른 일을 하시면 영상이 끊겼다.
 *
 * 여기서는 화면을 거치지 않는다. 한 장씩 그려 **바로 encoder 에 넣는다.** 컴퓨터가 빠르면
 * 빠른 만큼 빨리 끝난다. 검사용 컴퓨터(그림판만으로 그리는 느린 쪽)에서 재어 보니
 * **23초짜리가 6.2초 — 3.7배**였다. 그림을 굽는 칩이 있는 컴퓨터는 더 빠르다.
 *
 * 그림을 그리는 함수(`renderFrame`)는 미리보기·녹화와 **같은 것을 쓴다.** 그래야 원장님이
 * 보신 화면과 나온 영상이 어긋나지 않는다.
 */

/** 이 컴퓨터에서 빠르게 담을 수 있는 조합 */
export interface FastPlan {
  container: 'mp4' | 'webm'
  /** WebCodecs 에 넘길 이름 (avc1.… / vp09.… ) */
  videoCodec: string
  /** 묶는 쪽이 쓰는 이름 */
  muxVideo: 'avc' | 'vp9'
  audioCodec: string
  muxAudio: 'aac' | 'opus'
  mimeType: string
}

/**
 * 뽑아 볼 조합 — **앞에 있는 것이 더 널리 열린다.**
 *
 * MP4(H.264)는 파워포인트에 넣히고 카카오톡으로도 보내진다. WebM 은 그렇지 못한 자리가
 * 있으므로 MP4 가 되면 MP4 로 만든다.
 */
const PLANS: FastPlan[] = [
  {
    container: 'mp4',
    videoCodec: 'avc1.4D002A',
    muxVideo: 'avc',
    audioCodec: 'mp4a.40.2',
    muxAudio: 'aac',
    mimeType: 'video/mp4',
  },
  {
    container: 'mp4',
    videoCodec: 'avc1.42002A',
    muxVideo: 'avc',
    audioCodec: 'mp4a.40.2',
    muxAudio: 'aac',
    mimeType: 'video/mp4',
  },
  {
    container: 'webm',
    videoCodec: 'vp09.00.10.08',
    muxVideo: 'vp9',
    audioCodec: 'opus',
    muxAudio: 'opus',
    mimeType: 'video/webm',
  },
]

const SAMPLE_RATE = 48_000

/** 이 브라우저가 빠른 길을 쓸 수 있는가 — 못 쓰면 null (예전 방식으로 담는다) */
export async function pickFastPlan(width: number, height: number): Promise<FastPlan | null> {
  if (typeof VideoEncoder === 'undefined' || typeof AudioEncoder === 'undefined') return null
  if (typeof VideoFrame === 'undefined') return null
  for (const plan of PLANS) {
    try {
      const video = await VideoEncoder.isConfigSupported({
        codec: plan.videoCodec,
        width,
        height,
        bitrate: height >= 1080 ? 8_000_000 : 4_500_000,
        framerate: 30,
      })
      if (!video.supported) continue
      const audio = await AudioEncoder.isConfigSupported({
        codec: plan.audioCodec,
        sampleRate: SAMPLE_RATE,
        numberOfChannels: 2,
        bitrate: 128_000,
      })
      if (!audio.supported) continue
      return plan
    } catch {
      /* 이 조합은 못 쓴다 — 다음 것을 본다 */
    }
  }
  return null
}

/** 영상에 얹을 소리 한 가닥 */
export interface SoundPiece {
  /** 소리가 든 파일 주소 (음악 파일 또는 올리신 동영상) */
  url: string
  /** 영상에서 **언제** 시작하는가(초) */
  at: number
  /** 그 파일의 **어디서부터** 쓰는가(초) */
  offset: number
  /** 얼마나 쓰는가(초). 비우면 끝까지 */
  seconds?: number
  /** 크기 (1 = 그대로) */
  volume?: number
  /** 시작과 끝을 부드럽게 줄일 것인가 — 배경음악에만 */
  fade?: boolean
}

/**
 * 영상에 얹을 소리 가닥을 **장면 표에서 뽑아낸다.**
 *
 * 실시간 녹화는 스피커로 흐르는 소리를 그대로 받았으므로 어디서부터 틀지 신경 쓸 일이
 * 없었다. 빨리 담을 때는 파일을 직접 읽어 섞으므로, **어느 자리를 쓰는지 여기서 정확히
 * 말해 주어야 한다** — 한 자리라도 어긋나면 아이 얼굴과 소리가 따로 논다.
 *
 * 잘라 쓰기(clipWindow)는 미리보기·녹화와 **같은 계산**을 쓴다.
 *
 * @param clipLength 동영상 주소를 주면 그 길이(초)를 돌려준다. 모르면 0.
 */
export function soundPieces(
  timeline: Timeline,
  clipLength: (url: string) => number,
  music?: { url: string; start?: number; volume?: number } | null,
): SoundPiece[] {
  const pieces: SoundPiece[] = []
  if (music) {
    pieces.push({
      url: music.url,
      at: 0,
      // 고르신 자리에서 시작한다 — 곡 앞부분이 조용하면 영상 앞이 빈 것처럼 들린다
      offset: Math.max(0, music.start ?? 0),
      volume: Math.max(0, Math.min(1, music.volume ?? 1)),
      fade: true,
    })
  }
  for (let i = 0; i < timeline.scenes.length; i += 1) {
    const scene = timeline.scenes[i]
    if (!scene.clip) continue
    pieces.push({
      url: scene.clip,
      at: timeline.starts[i],
      offset: clipWindow(scene, clipLength(scene.clip)).start,
      seconds: scene.seconds,
    })
  }
  return pieces
}

export interface FastExportInput {
  timeline: Timeline
  sources: FrameSource
  options: RenderOptions
  plan: FastPlan
  fps?: number
  sounds?: SoundPiece[]
  /** 0~1 — 얼마나 왔는지 알려 준다 */
  onProgress?: (done: number) => void
  /** 참이 되면 멈춘다 (담긴 데까지 돌려준다) */
  shouldStop?: () => boolean
}

/**
 * 소리를 **미리 통째로 섞는다.**
 *
 * 실시간 녹화는 스피커로 흐르는 소리를 받아 담았다. 빨리 담을 때는 흐를 시간이 없으므로,
 * 파일을 읽어 한 번에 섞어 둔다(OfflineAudioContext). 결과는 같다.
 */
async function mixSound(pieces: SoundPiece[], total: number): Promise<AudioBuffer | null> {
  if (pieces.length === 0) return null
  const decoder = new AudioContext({ sampleRate: SAMPLE_RATE })
  const decoded: { buffer: AudioBuffer; piece: SoundPiece }[] = []
  try {
    for (const piece of pieces) {
      try {
        const bytes = await (await fetch(piece.url)).arrayBuffer()
        decoded.push({ buffer: await decoder.decodeAudioData(bytes), piece })
      } catch {
        // 소리를 못 읽는 파일이 하나 있다고 영상 전체를 버릴 수는 없다 — 그것만 빼고 간다
      }
    }
  } finally {
    void decoder.close()
  }
  if (decoded.length === 0) return null

  const offline = new OfflineAudioContext(2, Math.ceil(total * SAMPLE_RATE), SAMPLE_RATE)
  for (const { buffer, piece } of decoded) {
    const node = offline.createBufferSource()
    node.buffer = buffer
    const gain = offline.createGain()
    const top = Math.max(0, piece.volume ?? 1)
    const at = Math.max(0, piece.at)
    const length = Math.min(piece.seconds ?? total, Math.max(0, total - at))
    if (piece.fade) {
      // 시작과 끝을 부드럽게 — 뚝 끊기면 완성도가 떨어져 보인다
      gain.gain.setValueAtTime(0, at)
      gain.gain.linearRampToValueAtTime(top, at + Math.min(1.5, length / 3))
      gain.gain.setValueAtTime(top, at + Math.max(0, length - 2.5))
      gain.gain.linearRampToValueAtTime(0, at + length)
    } else {
      gain.gain.setValueAtTime(top, at)
    }
    node.connect(gain)
    gain.connect(offline.destination)
    node.start(at, Math.max(0, piece.offset), length)
  }
  return offline.startRendering()
}

/** 섞어 둔 소리를 조각내어 encoder 에 넣는다 */
async function encodeSound(buffer: AudioBuffer, encoder: AudioEncoder) {
  const channels = Math.min(2, buffer.numberOfChannels)
  const chunk = SAMPLE_RATE // 1초씩
  const left = buffer.getChannelData(0)
  const right = channels > 1 ? buffer.getChannelData(1) : left
  for (let start = 0; start < buffer.length; start += chunk) {
    const count = Math.min(chunk, buffer.length - start)
    // WebCodecs 는 채널을 이어 붙인 모양(planar)을 받는다
    const data = new Float32Array(count * 2)
    data.set(left.subarray(start, start + count), 0)
    data.set(right.subarray(start, start + count), count)
    encoder.encode(
      new AudioData({
        format: 'f32-planar',
        sampleRate: SAMPLE_RATE,
        numberOfFrames: count,
        numberOfChannels: 2,
        timestamp: Math.round((start / SAMPLE_RATE) * 1_000_000),
        data,
      }),
    )
  }
}

/**
 * 동영상 장면은 **그 시각의 화면**이 필요하다.
 *
 * 실시간 녹화는 동영상을 그냥 틀어 두면 됐지만, 빨리 담을 때는 흐를 시간이 없다.
 * 그래서 한 장 그릴 때마다 그 자리로 옮겨 놓고 기다린다.
 */
async function seekClips(timeline: Timeline, sources: FrameSource, at: number) {
  const waits: Promise<void>[] = []
  for (let i = 0; i < timeline.scenes.length; i += 1) {
    const scene = timeline.scenes[i]
    if (!scene.clip) continue
    const start = timeline.starts[i]
    if (at < start || at >= start + scene.seconds) continue
    const el = sources.videos.get(scene.clip)
    if (!el) continue
    const want = clipWindow(scene, el.duration || 0).start + (at - start)
    if (Math.abs(el.currentTime - want) < 0.02) continue
    waits.push(
      new Promise<void>((resolve) => {
        const done = () => {
          el.removeEventListener('seeked', done)
          resolve()
        }
        el.addEventListener('seeked', done)
        // 못 옮기면 그냥 지금 화면을 쓴다 — 여기서 멈춰 서면 영상이 안 나온다
        window.setTimeout(done, 400)
        el.currentTime = want
      }),
    )
  }
  await Promise.all(waits)
}

/**
 * 빠르게 담는다. 나온 파일은 예전 방식으로 담은 것과 **같은 화면·같은 소리**다.
 *
 * 중간에 멈추셔도(`shouldStop`) 담긴 데까지 파일로 돌려준다 —
 * 8분짜리를 7분째에 잃는 일이 없어야 한다.
 */
export async function fastExport({
  timeline,
  sources,
  options,
  plan,
  fps = 30,
  sounds = [],
  onProgress,
  shouldStop,
}: FastExportInput): Promise<{ blob: Blob; mimeType: string; partial: boolean }> {
  const { width, height } = options
  const total = timeline.total
  const frames = Math.max(1, Math.ceil(total * fps))

  const sound = await mixSound(sounds, total)

  const target = plan.container === 'mp4' ? new Mp4Target() : new WebmTarget()
  const muxer =
    plan.container === 'mp4'
      ? new Mp4Muxer({
          target: target as Mp4Target,
          video: { codec: 'avc', width, height, frameRate: fps },
          ...(sound ? { audio: { codec: 'aac' as const, numberOfChannels: 2, sampleRate: SAMPLE_RATE } } : {}),
          fastStart: 'in-memory',
        })
      : new WebmMuxer({
          target: target as WebmTarget,
          video: { codec: 'V_VP9', width, height, frameRate: fps },
          ...(sound ? { audio: { codec: 'A_OPUS' as const, numberOfChannels: 2, sampleRate: SAMPLE_RATE } } : {}),
        })

  let failure: Error | null = null
  const videoEncoder = new VideoEncoder({
    output: (chunk, meta) => muxer.addVideoChunk(chunk, meta),
    error: (error) => {
      failure = error
    },
  })
  videoEncoder.configure({
    codec: plan.videoCodec,
    width,
    height,
    bitrate: height >= 1080 ? 8_000_000 : 4_500_000,
    framerate: fps,
  })

  let audioEncoder: AudioEncoder | null = null
  if (sound) {
    audioEncoder = new AudioEncoder({
      output: (chunk, meta) => muxer.addAudioChunk(chunk, meta),
      error: (error) => {
        failure = error
      },
    })
    audioEncoder.configure({
      codec: plan.audioCodec,
      sampleRate: SAMPLE_RATE,
      numberOfChannels: 2,
      bitrate: 128_000,
    })
    await encodeSound(sound, audioEncoder)
  }

  const canvas = new OffscreenCanvas(width, height)
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('그림을 그릴 자리를 만들지 못했습니다.')

  let partial = false
  for (let i = 0; i < frames; i += 1) {
    if (failure) throw failure
    if (shouldStop?.()) {
      partial = true
      break
    }
    const at = i / fps
    await seekClips(timeline, sources, at)
    renderFrame(ctx as unknown as CanvasRenderingContext2D, timeline, at, sources, options)
    const frame = new VideoFrame(canvas, {
      timestamp: Math.round(at * 1_000_000),
      duration: Math.round(1_000_000 / fps),
    })
    // 2초에 한 번은 통째로 담는다 — 앞으로 감기가 매끄럽고, 중간에 멈춰도 열린다
    videoEncoder.encode(frame, { keyFrame: i % (fps * 2) === 0 })
    frame.close()
    // encoder 가 밀리면 기다린다. 안 그러면 메모리가 계속 쌓인다
    if (videoEncoder.encodeQueueSize > fps * 2) {
      await new Promise((resolve) => window.setTimeout(resolve, 8))
    }
    if (i % fps === 0) onProgress?.(i / frames)
  }

  await videoEncoder.flush()
  videoEncoder.close()
  if (audioEncoder) {
    await audioEncoder.flush()
    audioEncoder.close()
  }
  if (failure) throw failure
  muxer.finalize()
  onProgress?.(1)

  const buffer = (target as Mp4Target | WebmTarget).buffer
  if (!buffer) throw new Error('영상을 묶지 못했습니다.')
  return { blob: new Blob([buffer], { type: plan.mimeType }), mimeType: plan.mimeType, partial }
}
