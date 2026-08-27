'use client'

import { Download, Film, ImagePlus, Loader2, Music, Pause, Play, Square, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ThemePicker } from '@/components/design/theme-picker'
import { Button } from '@/components/ui/button'
import { Input, Label } from '@/components/ui/field'
import { getTheme } from '@/lib/design/themes'
import type { EventRecord, ProgramPlan } from '@/lib/types'
import { cn } from '@/lib/utils'
import {
  buildTimeline,
  describeRecordType,
  pickRecordType,
  renderFrame,
  type FrameSource,
} from '@/lib/video/render'
import {
  buildStoryboard,
  DEFAULT_STORYBOARD_OPTIONS,
  fitToLimit,
  formatLength,
  totalSeconds,
  type ExtraMedia,
  type StoryboardOptions,
} from '@/lib/video/storyboard'

/** 뽑는 크기 — 1080p 는 예쁘지만 느린 노트북에서 끊긴다 */
const SIZES = [
  { id: '720', label: 'HD 1280×720 (권장)', w: 1280, h: 720 },
  { id: '1080', label: 'FHD 1920×1080', w: 1920, h: 1080 },
] as const

/**
 * 감동영상 만들기.
 *
 * 사진과 영상, 음악을 고르면 한 편이 만들어진다. 전부 이 컴퓨터 안에서 처리한다 —
 * 아이들 사진과 얼굴이 어디로도 올라가지 않는다.
 *
 * 뽑는 일은 **실제 시간만큼 걸린다**(3분짜리는 3분). 브라우저가 화면을 그리면서
 * 녹화하는 방식이라 그렇다. 대신 프로그램을 따로 깔 필요가 없다.
 */
export function VideoStudio({
  event,
  plan,
  academyName,
  initialThemeId,
  photos,
}: {
  event: EventRecord
  plan: ProgramPlan
  academyName: string
  initialThemeId: string
  photos: Record<string, string>
}) {
  const [themeId, setThemeId] = useState(initialThemeId)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [options, setOptions] = useState<StoryboardOptions>(DEFAULT_STORYBOARD_OPTIONS)
  const [closing, setClosing] = useState('오늘 이 무대에 선 모든 아이들에게')
  const [extras, setExtras] = useState<ExtraMedia[]>([])
  const [music, setMusic] = useState<{ url: string; label: string } | null>(null)
  const [sizeId, setSizeId] = useState<(typeof SIZES)[number]['id']>('720')

  const [playing, setPlaying] = useState(false)
  const [recording, setRecording] = useState(false)
  const [clock, setClock] = useState(0)
  const [result, setResult] = useState<{ url: string; label: string; note: string; name: string; bytes: number } | null>(null)
  const [warning, setWarning] = useState<string | null>(null)
  const [ready, setReady] = useState(false)

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const sourcesRef = useRef<FrameSource>({ images: new Map(), videos: new Map() })
  const rafRef = useRef<number | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const theme = useMemo(() => getTheme(themeId), [themeId])
  const size = SIZES.find((item) => item.id === sizeId) ?? SIZES[0]

  const scenes = useMemo(
    () => fitToLimit(buildStoryboard({ event, plan, academyName, photos, extras, options, closing })),
    [event, plan, academyName, photos, extras, options, closing],
  )
  const timeline = useMemo(() => buildTimeline(scenes), [scenes])
  const withPhoto = Object.keys(photos).length
  // 서버에서는 브라우저가 무엇을 뽑을 수 있는지 알 수 없다.
  // 첫 그림을 서버와 똑같이 그린 뒤, 화면에 붙고 나서 알아본다 (그래야 화면이 어긋나지 않는다)
  const [recordType, setRecordType] = useState<string | null>(null)
  const [checkedRecorder, setCheckedRecorder] = useState(false)
  useEffect(() => {
    setRecordType(pickRecordType())
    setCheckedRecorder(true)
  }, [])

  /** 사진·동영상을 미리 다 읽어 둔다 — 그리는 도중에 읽으면 화면이 끊긴다 */
  useEffect(() => {
    let alive = true
    const sources: FrameSource = { images: new Map(), videos: new Map() }
    const urls = new Set<string>()
    for (const scene of scenes) {
      if (scene.image) urls.add(scene.image)
    }
    const jobs: Promise<void>[] = []
    for (const url of urls) {
      jobs.push(
        new Promise<void>((resolve) => {
          const img = new Image()
          img.crossOrigin = 'anonymous'
          img.onload = () => {
            sources.images.set(url, img)
            resolve()
          }
          img.onerror = () => resolve()
          img.src = url
        }),
      )
    }
    for (const scene of scenes) {
      if (!scene.clip) continue
      const el = document.createElement('video')
      el.src = scene.clip
      el.muted = false
      el.playsInline = true
      el.preload = 'auto'
      sources.videos.set(scene.clip, el)
      jobs.push(new Promise<void>((resolve) => {
        el.onloadeddata = () => resolve()
        el.onerror = () => resolve()
      }))
    }
    setReady(false)
    void Promise.all(jobs).then(() => {
      if (!alive) return
      sourcesRef.current = sources
      setReady(true)
      draw(0)
    })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenes])

  const draw = useCallback(
    (seconds: number) => {
      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      renderFrame(ctx, timeline, seconds, sourcesRef.current, {
        width: canvas.width,
        height: canvas.height,
        theme,
        academyName,
      })
    },
    [timeline, theme, academyName],
  )

  useEffect(() => {
    if (!playing && !recording) draw(clock)
  }, [draw, clock, playing, recording])

  /** 재생·녹화 공통 진행 루프 */
  const runLoop = useCallback(
    (onDone: () => void) => {
      const started = performance.now()
      const playedClips = new Set<string>()
      const step = () => {
        const seconds = (performance.now() - started) / 1000
        // 이 시각에 보여야 할 동영상은 재생시켜 둔다
        for (let i = 0; i < timeline.scenes.length; i += 1) {
          const scene = timeline.scenes[i]
          if (!scene.clip) continue
          const start = timeline.starts[i]
          const el = sourcesRef.current.videos.get(scene.clip)
          if (!el) continue
          if (seconds >= start && seconds < start + scene.seconds) {
            if (!playedClips.has(scene.clip)) {
              playedClips.add(scene.clip)
              el.currentTime = 0
              void el.play().catch(() => undefined)
            }
          } else if (playedClips.has(scene.clip) && !el.paused) {
            el.pause()
          }
        }
        draw(seconds)
        setClock(seconds)
        if (seconds >= timeline.total) {
          onDone()
          return
        }
        rafRef.current = requestAnimationFrame(step)
      }
      rafRef.current = requestAnimationFrame(step)
    },
    [draw, timeline],
  )

  function stopLoop() {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
    rafRef.current = null
    for (const el of sourcesRef.current.videos.values()) el.pause()
    audioRef.current?.pause()
  }

  function preview() {
    if (playing) {
      stopLoop()
      setPlaying(false)
      return
    }
    setPlaying(true)
    setClock(0)
    if (music && audioRef.current) {
      audioRef.current.currentTime = 0
      void audioRef.current.play().catch(() => undefined)
    }
    runLoop(() => {
      stopLoop()
      setPlaying(false)
      setClock(0)
      draw(0)
    })
  }

  async function record() {
    const canvas = canvasRef.current
    if (!canvas || !recordType) return
    setWarning(null)
    setResult(null)
    setRecording(true)
    setClock(0)

    const stream = canvas.captureStream(30)
    const audio = new AudioContext()
    const mixer = audio.createMediaStreamDestination()
    let anyAudio = false

    // 배경음악 — 시작과 끝을 부드럽게 줄인다
    if (music) {
      const el = new Audio(music.url)
      el.crossOrigin = 'anonymous'
      audioRef.current = el
      const source = audio.createMediaElementSource(el)
      const gain = audio.createGain()
      const now = audio.currentTime
      gain.gain.setValueAtTime(0, now)
      gain.gain.linearRampToValueAtTime(0.9, now + 1.5)
      gain.gain.setValueAtTime(0.9, now + Math.max(2, timeline.total - 2.5))
      gain.gain.linearRampToValueAtTime(0, now + timeline.total)
      source.connect(gain)
      gain.connect(mixer)
      el.currentTime = 0
      await el.play().catch(() => undefined)
      anyAudio = true
    }

    // 올린 동영상의 소리도 함께 담는다
    for (const el of sourcesRef.current.videos.values()) {
      try {
        const source = audio.createMediaElementSource(el)
        source.connect(mixer)
        anyAudio = true
      } catch {
        /* 이미 연결돼 있으면 그대로 둔다 */
      }
    }
    if (anyAudio) for (const track of mixer.stream.getAudioTracks()) stream.addTrack(track)

    const recorder = new MediaRecorder(stream, {
      mimeType: recordType,
      videoBitsPerSecond: size.h >= 1080 ? 8_000_000 : 4_500_000,
    })
    const chunks: BlobPart[] = []
    recorder.ondataavailable = (native) => {
      if (native.data.size > 0) chunks.push(native.data)
    }
    const finished = new Promise<void>((resolve) => {
      recorder.onstop = () => resolve()
    })
    recorder.start(500)

    const onHidden = () => {
      if (document.visibilityState === 'hidden') {
        setWarning('다른 창으로 넘어가면 영상이 끊깁니다. 이 창을 그대로 두세요.')
      }
    }
    document.addEventListener('visibilitychange', onHidden)

    runLoop(() => {
      stopLoop()
      recorder.stop()
    })

    await finished
    document.removeEventListener('visibilitychange', onHidden)
    void audio.close()
    const info = describeRecordType(recorder.mimeType || recordType)
    const blob = new Blob(chunks, { type: recorder.mimeType || recordType })
    setResult({
      url: URL.createObjectURL(blob),
      label: info.label,
      note: info.note,
      name: `${event.title.replace(/[\\/:*?"<>|]/g, ' ').trim() || '연주회'} 감동영상.${info.ext}`,
      bytes: blob.size,
    })
    setRecording(false)
    setClock(0)
    draw(0)
  }

  function addFiles(files: FileList, kind: 'image' | 'video') {
    const added: ExtraMedia[] = []
    for (const file of Array.from(files)) {
      added.push({
        id: `${kind}-${Date.now()}-${added.length}`,
        kind,
        url: URL.createObjectURL(file),
        label: file.name.replace(/\.[^.]+$/, ''),
      })
    }
    setExtras((prev) => [...prev, ...added])
    if (kind === 'video') {
      // 동영상 길이를 읽어 장면 시간에 반영한다
      for (const item of added) {
        const probe = document.createElement('video')
        probe.preload = 'metadata'
        probe.onloadedmetadata = () => {
          setExtras((prev) =>
            prev.map((row) => (row.id === item.id ? { ...row, duration: probe.duration } : row)),
          )
        }
        probe.src = item.url
      }
    }
  }

  const length = totalSeconds(scenes)

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
      <div className="grid content-start gap-3">
        <div className="overflow-hidden rounded-lg border border-border bg-black">
          <canvas
            ref={canvasRef}
            width={size.w}
            height={size.h}
            className="block h-auto w-full"
            aria-label="감동영상 미리보기"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={preview} disabled={recording || !ready}>
            {playing ? <Pause className="mr-1 h-4 w-4" /> : <Play className="mr-1 h-4 w-4" />}
            {playing ? '멈추기' : '미리보기'}
          </Button>
          <Button
            size="sm"
            variant={recording ? 'outline' : 'default'}
            onClick={() => (recording ? stopLoop() : void record())}
            disabled={!ready || !recordType || playing}
          >
            {recording ? <Square className="mr-1 h-4 w-4" /> : <Film className="mr-1 h-4 w-4" />}
            {recording ? '만드는 중…' : '영상 만들기'}
          </Button>
          <span className="text-sm tabular-nums text-muted-foreground" data-testid="video-length">
            {formatLength(clock)} / {formatLength(length)} · 장면 {scenes.length}개
          </span>
          {!ready && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" aria-label="사진 읽는 중" />}
        </div>

        {(playing || recording) && (
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full bg-accent transition-[width] duration-200"
              style={{ width: `${Math.min(100, (clock / Math.max(1, length)) * 100)}%` }}
            />
          </div>
        )}

        {recording && (
          <p className="rounded-md border border-accent/40 bg-accent/5 px-3 py-2.5 text-sm">
            <strong>이 창을 그대로 두세요.</strong> 영상은 화면을 그리면서 담기 때문에 실제 길이만큼
            ({formatLength(length)}) 걸립니다. 다른 창으로 넘어가면 끊깁니다.
          </p>
        )}
        {warning && <p className="text-sm text-destructive">{warning}</p>}

        {result && (
          <div className="grid gap-2 rounded-md border border-accent/40 bg-accent/5 p-3">
            <p className="text-sm font-medium">영상이 만들어졌습니다 · {result.label} · {Math.round(result.bytes / 1024 / 1024)}MB</p>
            <video src={result.url} controls className="w-full rounded-md" />
            <div className="flex flex-wrap items-center gap-2">
              <a
                href={result.url}
                download={result.name}
                className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
              >
                <Download className="mr-1 h-4 w-4" />
                내려받기
              </a>
              <span className="text-xs text-muted-foreground">{result.note}</span>
            </div>
          </div>
        )}

        {checkedRecorder && !recordType && (
          <p className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2.5 text-sm">
            이 브라우저는 영상 만들기를 지원하지 않습니다. <strong>크롬</strong>이나 <strong>엣지</strong>에서 열어 주세요.
            (미리보기는 그대로 됩니다)
          </p>
        )}
      </div>

      <div className="grid content-start gap-4">
        <section className="grid gap-2 rounded-lg border border-border p-3">
          <p className="text-sm font-medium">1 · 아이 사진</p>
          <p className="text-xs text-muted-foreground">
            명단에 넣어 둔 아이 사진 <strong>{withPhoto}명</strong> 분이 그대로 쓰입니다.
            {withPhoto < plan.items.length && ` 사진이 없는 ${plan.items.length - withPhoto}명은 이름만 나옵니다.`}
          </p>
        </section>

        <section className="grid gap-2 rounded-lg border border-border p-3">
          <p className="text-sm font-medium">2 · 연습 사진 · 동영상 더하기</p>
          <div className="flex flex-wrap gap-2">
            <label className="inline-flex h-9 cursor-pointer items-center rounded-md border border-input px-3 text-sm hover:bg-secondary">
              <ImagePlus className="mr-1 h-4 w-4" />
              사진 고르기
              <input
                type="file"
                accept="image/*"
                multiple
                className="sr-only"
                onChange={(native) => {
                  if (native.target.files?.length) addFiles(native.target.files, 'image')
                  native.target.value = ''
                }}
              />
            </label>
            <label className="inline-flex h-9 cursor-pointer items-center rounded-md border border-input px-3 text-sm hover:bg-secondary">
              <Film className="mr-1 h-4 w-4" />
              동영상 고르기
              <input
                type="file"
                accept="video/*"
                multiple
                className="sr-only"
                onChange={(native) => {
                  if (native.target.files?.length) addFiles(native.target.files, 'video')
                  native.target.value = ''
                }}
              />
            </label>
          </div>
          {extras.length > 0 && (
            <ul className="grid gap-1">
              {extras.map((item) => (
                <li key={item.id} className="flex items-center gap-2 text-xs">
                  <span className="rounded bg-secondary px-1.5 py-0.5">{item.kind === 'image' ? '사진' : '영상'}</span>
                  <span className="min-w-0 flex-1 truncate">{item.label}</span>
                  {item.duration ? <span className="tabular-nums text-muted-foreground">{Math.round(item.duration)}초</span> : null}
                  <button
                    type="button"
                    onClick={() => setExtras((prev) => prev.filter((row) => row.id !== item.id))}
                    aria-label={`${item.label} 빼기`}
                  >
                    <Trash2 className="h-3.5 w-3.5 text-destructive" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-muted-foreground">
            여기서 고른 파일은 <strong>저장되지 않습니다.</strong> 이 화면에서 영상을 만들 때만 쓰이고,
            컴퓨터 밖으로 나가지 않습니다.
          </p>
        </section>

        <section className="grid gap-2 rounded-lg border border-border p-3">
          <p className="text-sm font-medium">3 · 배경음악</p>
          <label className="inline-flex h-9 w-fit cursor-pointer items-center rounded-md border border-input px-3 text-sm hover:bg-secondary">
            <Music className="mr-1 h-4 w-4" />
            {music ? '음악 바꾸기' : '음악 고르기'}
            <input
              type="file"
              accept="audio/*"
              className="sr-only"
              onChange={(native) => {
                const file = native.target.files?.[0]
                if (file) setMusic({ url: URL.createObjectURL(file), label: file.name })
                native.target.value = ''
              }}
            />
          </label>
          {music && (
            <p className="flex items-center gap-2 text-xs">
              <span className="min-w-0 flex-1 truncate">{music.label}</span>
              <button type="button" onClick={() => setMusic(null)} aria-label="음악 빼기">
                <Trash2 className="h-3.5 w-3.5 text-destructive" />
              </button>
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            시작과 끝을 부드럽게 줄여 넣습니다. <strong>저작권이 있는 곡</strong>은 학원 밖으로 공개하지 마세요 —
            학부모에게 보내실 거라면 이용 허락을 받은 음원을 쓰십시오.
          </p>
        </section>

        <section className="grid gap-2 rounded-lg border border-border p-3">
          <p className="text-sm font-medium">4 · 모양과 길이</p>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setPickerOpen((prev) => !prev)}>
              테마 · {theme.name}
            </Button>
            <select
              value={sizeId}
              onChange={(native) => setSizeId(native.target.value as (typeof SIZES)[number]['id'])}
              className="h-9 rounded-md border border-border bg-background px-2 text-sm"
              aria-label="영상 크기"
            >
              {SIZES.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          {pickerOpen && <ThemePicker value={themeId} onChange={setThemeId} eventAt={event.event_at} compact />}

          <div className="grid gap-2 sm:grid-cols-2">
            <div>
              <Label htmlFor="v-student">아이 한 명당</Label>
              <Input
                id="v-student"
                type="number"
                min={1.5}
                max={12}
                step={0.5}
                value={options.student_seconds}
                onChange={(native) =>
                  setOptions((prev) => ({ ...prev, student_seconds: Number(native.target.value) || prev.student_seconds }))
                }
              />
            </div>
            <div>
              <Label htmlFor="v-title">표지 · 마무리</Label>
              <Input
                id="v-title"
                type="number"
                min={1.5}
                max={12}
                step={0.5}
                value={options.title_seconds}
                onChange={(native) =>
                  setOptions((prev) => ({ ...prev, title_seconds: Number(native.target.value) || prev.title_seconds }))
                }
              />
            </div>
          </div>
          <div>
            <Label htmlFor="v-closing">마무리 문구</Label>
            <Input id="v-closing" value={closing} onChange={(native) => setClosing(native.target.value)} />
          </div>
          <label className={cn('flex cursor-pointer items-center gap-2 text-sm')}>
            <input
              type="checkbox"
              checked={options.captions}
              onChange={(native) => setOptions((prev) => ({ ...prev, captions: native.target.checked }))}
              className="h-4 w-4"
            />
            이름·곡 자막 넣기
          </label>
        </section>
      </div>
    </div>
  )
}
