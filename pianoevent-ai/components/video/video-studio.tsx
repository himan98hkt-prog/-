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
import type { DesignTheme } from '@/lib/design/themes'
import {
  buildStoryboard,
  DEFAULT_STORYBOARD_OPTIONS,
  fitToLimit,
  formatLength,
  isTextOnly,
  moveScene,
  sceneLabel,
  sortByFileName,
  totalSeconds,
  type CaptionPlace,
  type ExtraMedia,
  type StoryboardOptions,
  type VideoScene,
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
  const [editing, setEditing] = useState<string | null>(null)
  const [ready, setReady] = useState(false)

  const canvasRef = useRef<HTMLCanvasElement>(null)
  // 그리는 루프는 ref 로 읽고(매 프레임 새로 만들지 않으려고), 콘티는 state 로 다시 그린다
  const [sources, setSources] = useState<FrameSource>({ images: new Map(), videos: new Map() })
  const sourcesRef = useRef<FrameSource>(sources)
  /** 그리는 쪽에서 지금 시각을 읽을 수 있게 — state 는 저 안쪽 콜백에서 낡아 있다 */
  const clockRef = useRef(0)
  const rafRef = useRef<number | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const theme = useMemo(() => getTheme(themeId), [themeId])
  const size = SIZES.find((item) => item.id === sizeId) ?? SIZES[0]

  const auto = useMemo(
    () => fitToLimit(buildStoryboard({ event, plan, academyName, photos, extras, options, closing })),
    [event, plan, academyName, photos, extras, options, closing],
  )
  /**
   * 원장님이 손댄 장면 목록.
   * 자동으로 짠 것을 시작점으로 두고, 순서·문구·시간을 직접 고칠 수 있다.
   * 자동 쪽이 바뀌면(사진을 더 넣거나 시간을 바꾸면) 고치지 않은 장면만 따라 바뀐다.
   */
  const [edits, setEdits] = useState<Record<string, VideoScene>>({})
  const [order, setOrder] = useState<string[] | null>(null)

  const scenes = useMemo(() => {
    const merged = auto.map((scene) => (edits[scene.id] ? { ...scene, ...edits[scene.id] } : scene))
    if (!order) return merged
    const byId = new Map(merged.map((scene) => [scene.id, scene]))
    const sorted = order.map((id) => byId.get(id)).filter(Boolean) as VideoScene[]
    // 새로 생긴 장면(사진을 더 넣었을 때)은 뒤에 붙인다 — 사라지지 않게
    for (const scene of merged) if (!order.includes(scene.id)) sorted.push(scene)
    return sorted
  }, [auto, edits, order])

  const patchScene = (id: string, patch: Partial<VideoScene>) =>
    setEdits((prev) => ({ ...prev, [id]: { ...(prev[id] ?? ({} as VideoScene)), ...patch, edited: true } }))

  const shiftScene = (index: number, delta: number) =>
    setOrder(moveScene(scenes, index, delta).map((scene) => scene.id))

  const resetScenes = () => {
    setEdits({})
    setOrder(null)
  }
  const timeline = useMemo(() => buildTimeline(scenes), [scenes])
  const withPhoto = Object.keys(photos).length
  /** 지금 화면에 보이는 장면 — 콘티에서 표시해 준다 */
  const activeIndex = useMemo(() => {
    let found = 0
    for (let i = 0; i < timeline.starts.length; i += 1) {
      if (clock >= timeline.starts[i]) found = i
    }
    return found
  }, [timeline, clock])
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
    const loaded: FrameSource = { images: new Map(), videos: new Map() }
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
            loaded.images.set(url, img)
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
      loaded.videos.set(scene.clip, el)
      jobs.push(new Promise<void>((resolve) => {
        el.onloadeddata = () => resolve()
        el.onerror = () => resolve()
      }))
    }
    setReady(false)
    void Promise.all(jobs).then(() => {
      if (!alive) return
      sourcesRef.current = loaded
      setSources(loaded)
      setReady(true)
      // 보고 있던 자리를 지킨다 — 장면을 고칠 때마다 처음으로 튀지 않게
      draw(clockRef.current, true)
    })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenes])

  const draw = useCallback(
    (seconds: number, still = false) => {
      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      renderFrame(
        ctx,
        timeline,
        seconds,
        sourcesRef.current,
        { width: canvas.width, height: canvas.height, theme, academyName },
        still,
      )
    },
    [timeline, theme, academyName],
  )

  useEffect(() => {
    if (!playing && !recording) draw(clock, true)
  }, [draw, clock, playing, recording])

  /** 재생·녹화 공통 진행 루프 */
  const runLoop = useCallback(
    (onDone: () => void, from = 0) => {
      const started = performance.now() - from * 1000
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

  function preview(from = 0) {
    if (playing) {
      stopLoop()
      setPlaying(false)
      return
    }
    setPlaying(true)
    setClock(from)
    if (music && audioRef.current) {
      audioRef.current.currentTime = from
      void audioRef.current.play().catch(() => undefined)
    }
    runLoop(
      () => {
        stopLoop()
        setPlaying(false)
        setClock(0)
        draw(0)
      },
      from,
    )
  }

  /** 콘티에서 장면을 누르면 그 자리를 보여 준다 */
  function jumpTo(seconds: number) {
    if (recording) return
    if (playing) {
      stopLoop()
      setPlaying(false)
    }
    setClock(seconds)
    draw(seconds)
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
    // `01 입장.jpg` 처럼 앞에 번호를 붙여 두면 그 차례대로 늘어놓는다
    setExtras((prev) => sortByFileName([...prev, ...added]))
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
  const editingScene = scenes.find((scene) => scene.id === editing) ?? null
  clockRef.current = clock

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
          <Button size="sm" onClick={() => preview(playing ? 0 : clock)} disabled={recording || !ready}>
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
          {!recording && !playing && ready && (
            <span className="text-xs text-muted-foreground">
              만드는 데 <strong className="text-foreground">약 {formatLength(length)}</strong> 걸립니다
            </span>
          )}
          {(Object.keys(edits).length > 0 || order) && !recording && (
            <Button variant="ghost" size="sm" onClick={resetScenes}>
              고친 것 되돌리기
            </Button>
          )}
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

        <StoryboardStrip
          timeline={timeline}
          sources={sources}
          theme={theme}
          academyName={academyName}
          onJump={jumpTo}
          activeIndex={activeIndex}
          onPick={setEditing}
          editingId={editing}
          onMove={shiftScene}
        />

        {editingScene && (
          <SceneEditor
            scene={editingScene}
            index={scenes.findIndex((item) => item.id === editingScene.id)}
            total={scenes.length}
            onChange={(patch) => patchScene(editingScene.id, patch)}
            onMove={(delta) => shiftScene(scenes.findIndex((item) => item.id === editingScene.id), delta)}
            onClose={() => setEditing(null)}
          />
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
          <p className="text-xs text-muted-foreground">
            파일 이름 앞에 <code>01</code> <code>02</code> 처럼 번호를 붙여 두면{' '}
            <strong>그 차례대로</strong> 들어갑니다.
          </p>
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

/**
 * 만들어질 모습 미리보기 — 콘티.
 *
 * "만들기"를 누르면 몇 분을 기다려야 한다. 그 전에 **전체가 어떻게 나올지**
 * 눈으로 볼 수 있어야 마음 놓고 누른다. 장면마다 실제 화면을 그려서 보여 준다 —
 * 설명이 아니라 진짜 그 그림이다.
 */
function StoryboardStrip({
  timeline,
  sources,
  theme,
  academyName,
  onJump,
  activeIndex,
  onPick,
  editingId,
  onMove,
}: {
  timeline: ReturnType<typeof buildTimeline>
  sources: FrameSource
  theme: DesignTheme
  academyName: string
  onJump: (seconds: number) => void
  activeIndex: number
  onPick: (id: string | null) => void
  editingId: string | null
  onMove: (index: number, delta: number) => void
}) {
  const [shots, setShots] = useState<string[]>([])

  useEffect(() => {
    // 장면마다 한 장씩 실제로 그려서 그림으로 굽는다
    const canvas = document.createElement('canvas')
    canvas.width = 480
    canvas.height = 270
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const made: string[] = []
    for (let i = 0; i < timeline.scenes.length; i += 1) {
      // 장면 한가운데를 뽑는다 — 겹쳐 넘어가는 구간을 피한다
      const at = timeline.starts[i] + timeline.scenes[i].seconds / 2
      renderFrame(
        ctx,
        timeline,
        at,
        sources,
        { width: canvas.width, height: canvas.height, theme, academyName },
        true,
      )
      made.push(canvas.toDataURL('image/jpeg', 0.72))
    }
    setShots(made)
  }, [timeline, sources, theme, academyName])

  return (
    <section className="grid gap-2 rounded-lg border border-border p-3" data-testid="storyboard">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium">만들어질 모습 · 장면 {timeline.scenes.length}개</p>
        <p className="text-xs text-muted-foreground">
          전체 {formatLength(timeline.total)} · 아래 그림이 <strong>실제로 나올 화면 그대로</strong>입니다 ·
          누르면 그 장면을 고칠 수 있습니다
        </p>
      </div>
      <div className="grid max-h-[440px] grid-cols-2 gap-2 overflow-y-auto pr-1 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5">
        {timeline.scenes.map((scene, index) => (
          <div
            key={scene.id}
            className={cn(
              'group relative grid gap-1 rounded-md border p-1 text-left transition-colors',
              scene.id === editingId
                ? 'border-accent bg-accent/12'
                : index === activeIndex
                  ? 'border-accent bg-accent/8'
                  : 'border-border hover:bg-secondary',
            )}
          >
            <button
              type="button"
              onClick={() => {
                onJump(timeline.starts[index])
                onPick(scene.id)
              }}
              className="grid gap-1 text-left"
              aria-label={`${sceneLabel(scene)} 장면 고치기`}
            >
            <span className="relative block overflow-hidden rounded bg-black" style={{ aspectRatio: '16 / 9' }}>
              {shots[index] ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={shots[index]} alt="" className="h-full w-full object-cover" />
              ) : null}
              <span className="absolute bottom-1 right-1 rounded bg-black/70 px-1 text-[10px] tabular-nums text-white">
                {scene.seconds}초
              </span>
              {isTextOnly(scene) && (
                <span className="absolute left-1 top-1 rounded bg-black/70 px-1 text-[10px] text-white">사진 없음</span>
              )}
            </span>
              <span className="truncate px-0.5 text-xs leading-tight text-muted-foreground">
                <span className="tabular-nums">{index + 1}.</span> {sceneLabel(scene)}
              </span>
            </button>
            <div className="absolute right-1 top-1 flex gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
              <button
                type="button"
                onClick={() => onMove(index, -1)}
                disabled={index === 0}
                aria-label={`${sceneLabel(scene)} 앞으로`}
                className="rounded bg-black/70 px-1 text-[11px] text-white disabled:opacity-30"
              >
                ←
              </button>
              <button
                type="button"
                onClick={() => onMove(index, 1)}
                disabled={index === timeline.scenes.length - 1}
                aria-label={`${sceneLabel(scene)} 뒤로`}
                className="rounded bg-black/70 px-1 text-[11px] text-white disabled:opacity-30"
              >
                →
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

const CAPTION_PLACES: { id: CaptionPlace; label: string; hint: string }[] = [
  { id: 'bottom', label: '아래', hint: '사진 아래쪽에 이름' },
  { id: 'top', label: '위', hint: '얼굴이 아래쪽에 있을 때' },
  { id: 'center', label: '가운데 크게', hint: '감동 문구를 한가운데' },
  { id: 'none', label: '글자 없이', hint: '사진만 보여 줍니다' },
]

/**
 * 장면 하나 고치기.
 *
 * 자동으로 짜 준 것을 그대로 쓰셔도 되지만, 연주회는 원장님의 것이다.
 * 문구를 바꾸고, 순서를 옮기고, 머무는 시간을 늘리는 일은 손에 있어야 한다.
 */
function SceneEditor({
  scene,
  index,
  total,
  onChange,
  onMove,
  onClose,
}: {
  scene: VideoScene
  index: number
  total: number
  onChange: (patch: Partial<VideoScene>) => void
  onMove: (delta: number) => void
  onClose: () => void
}) {
  return (
    <section className="grid gap-3 rounded-lg border border-accent/50 bg-accent/5 p-3" data-testid="scene-editor">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-medium">
          {index + 1}번째 장면 고치기
          <span className="ml-1.5 text-xs font-normal text-muted-foreground">{sceneLabel(scene)}</span>
        </p>
        <div className="ml-auto flex items-center gap-1.5">
          <Button variant="outline" size="sm" onClick={() => onMove(-1)} disabled={index === 0}>
            ← 앞으로
          </Button>
          <Button variant="outline" size="sm" onClick={() => onMove(1)} disabled={index === total - 1}>
            뒤로 →
          </Button>
          <Button variant="ghost" size="sm" onClick={onClose}>
            닫기
          </Button>
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <div>
          <Label htmlFor="sc-head">큰 글씨</Label>
          <Input
            id="sc-head"
            value={scene.headline ?? ''}
            placeholder="아이 이름 · 감동 문구"
            onChange={(native) => onChange({ headline: native.target.value })}
          />
        </div>
        <div>
          <Label htmlFor="sc-sub">작은 글씨</Label>
          <Input
            id="sc-sub"
            value={scene.sub ?? ''}
            placeholder="연주곡 · 한 줄 설명"
            onChange={(native) => onChange({ sub: native.target.value })}
          />
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <div>
          <Label htmlFor="sc-eyebrow">맨 위 작은 글씨</Label>
          <Input
            id="sc-eyebrow"
            value={scene.eyebrow ?? ''}
            placeholder="1번째 무대"
            onChange={(native) => onChange({ eyebrow: native.target.value })}
          />
        </div>
        <div>
          <Label htmlFor="sc-sec">머무는 시간 (초)</Label>
          <Input
            id="sc-sec"
            type="number"
            min={1.5}
            max={20}
            step={0.5}
            value={scene.seconds}
            onChange={(native) => onChange({ seconds: Math.max(1.5, Number(native.target.value) || scene.seconds) })}
          />
        </div>
      </div>

      <div>
        <p className="mb-1 text-sm">글자 자리</p>
        <div className="flex flex-wrap gap-1.5">
          {CAPTION_PLACES.map((place) => (
            <button
              key={place.id}
              type="button"
              onClick={() => onChange({ caption: place.id })}
              aria-pressed={(scene.caption ?? 'bottom') === place.id}
              title={place.hint}
              className={cn(
                'rounded-full border px-3 py-1 text-xs transition-colors',
                (scene.caption ?? 'bottom') === place.id
                  ? 'border-accent bg-accent/15 font-medium'
                  : 'border-border text-muted-foreground hover:bg-secondary',
              )}
            >
              {place.label}
            </button>
          ))}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          아이 얼굴이 가려지면 자리를 옮기세요. <strong>가운데 크게</strong>는 감동 문구를 넣을 때 씁니다.
        </p>
      </div>
    </section>
  )
}
