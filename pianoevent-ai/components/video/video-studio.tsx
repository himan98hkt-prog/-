'use client'

import {
  ChevronDown,
  Download,
  Film,
  Gauge,
  ImagePlus,
  Link2,
  Loader2,
  MessageSquareHeart,
  Music,
  Pause,
  Play,
  Merge,
  Scissors,
  Square,
  Timer,
  Trash2,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { PrefsBar, type PastPrefs } from '@/components/design/prefs-bar'
import { ThemePicker } from '@/components/design/theme-picker'
import { Button } from '@/components/ui/button'
import { Input, Label } from '@/components/ui/field'
import { getTheme } from '@/lib/design/themes'
import { prefBool, prefNumber, prefString, type Prefs } from '@/lib/prefs'
import { embedHint, videoEmbed } from '@/lib/video/embed'
import {
  canJoin,
  joinBlocker,
  joinedName,
  joinLabel,
  movePart,
  partsSeconds,
  type VideoPart,
} from '@/lib/video/join'
import type { EventRecord, ProgramPlan } from '@/lib/types'
import {
  DEFAULT_VIDEO_TEMPLATE,
  getVideoTemplate,
  VIDEO_TEMPLATES,
  type VideoTemplate,
} from '@/lib/video/templates'
import { cn } from '@/lib/utils'
import {
  buildTimeline,
  describeRecordType,
  getLogoPlace,
  LOGO_PLACES,
  pickRecordType,
  renderFrame,
  type FrameSource,
  type LogoMark,
  type LogoPlace,
  type Timeline,
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
  cheerRange,
  sortByFileName,
  TASTER_FIXES,
  TASTER_SEC,
  tasterRange,
  tasterSpread,
  tasterStarts,
  totalSeconds,
  type CaptionPlace,
  type CheerMessage,
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
 * 미리보기 배속.
 *
 * 3분짜리 영상을 확인하려고 3분을 앉아 있는 건 말이 안 된다.
 * 녹화는 화면을 실제로 그려 담는 방식이라 늘 1배지만, **확인만은** 빠르게 돌린다.
 */
const SPEEDS = [1, 2, 4] as const

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
  photoSets = {},
  messages = [],
  logoUrl = null,
  savedPrefs = null,
  pastPrefs = [],
}: {
  event: EventRecord
  plan: ProgramPlan
  academyName: string
  initialThemeId: string
  photos: Record<string, string>
  /** 학생 id → 사진 여러 장 — 한 아이가 머무는 몇 초 동안 넘겨 가며 보여 준다 */
  photoSets?: Record<string, string[]>
  /** 학부모가 초대장에 남긴 응원 메시지 */
  messages?: CheerMessage[]
  /** 학원 로고 — 영상 구석에 작게 넣을 수 있다 */
  logoUrl?: string | null
  /** 이 행사에 저장해 둔 설정 */
  savedPrefs?: Prefs | null
  /** 설정을 저장해 둔 지난 행사들 — "작년 것 불러오기" */
  pastPrefs?: PastPrefs[]
}) {
  const [themeId, setThemeId] = useState(() => prefString(savedPrefs, 'theme', initialThemeId))
  const [pickerOpen, setPickerOpen] = useState(false)
  const [options, setOptions] = useState<StoryboardOptions>(() => ({
    student_seconds: prefNumber(savedPrefs, 'student_seconds', DEFAULT_STORYBOARD_OPTIONS.student_seconds),
    title_seconds: prefNumber(savedPrefs, 'title_seconds', DEFAULT_STORYBOARD_OPTIONS.title_seconds),
    gallery_seconds: prefNumber(savedPrefs, 'gallery_seconds', DEFAULT_STORYBOARD_OPTIONS.gallery_seconds),
    captions: prefBool(savedPrefs, 'captions', DEFAULT_STORYBOARD_OPTIONS.captions),
    messages: prefBool(savedPrefs, 'messages', DEFAULT_STORYBOARD_OPTIONS.messages),
  }))
  const [closing, setClosing] = useState<string>(() =>
    prefString(savedPrefs, 'closing', '오늘 이 무대에 선 모든 아이들에게'),
  )
  const [extras, setExtras] = useState<ExtraMedia[]>([])
  const [music, setMusic] = useState<{ url: string; label: string } | null>(null)
  const [sizeId, setSizeId] = useState<(typeof SIZES)[number]['id']>(() =>
    prefString<(typeof SIZES)[number]['id']>(savedPrefs, 'size', '720'),
  )
  const [templateId, setTemplateId] = useState(() =>
    prefString(savedPrefs, 'template', DEFAULT_VIDEO_TEMPLATE.id),
  )
  // 로고가 있으면 오른쪽 아래가 기본이다 — 얼굴을 가장 덜 가리는 자리
  const [logoPlace, setLogoPlace] = useState<LogoPlace>(() =>
    getLogoPlace(prefString(savedPrefs, 'logo_place', logoUrl ? 'bottom-right' : 'none')),
  )
  /** 미리보기 배속 — 녹화는 늘 1배다 */
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1)
  /**
   * 만들 구간 (장면 번호, 0부터).
   *
   * 8분짜리를 7분째에 끊어 먹으면 다시 8분이다. 두세 토막으로 나눠 만들면
   * 한 토막이 짧아 다시 만들기도 쉽고, 나중에 이어 붙이시면 된다.
   */
  const [range, setRange] = useState<{ from: number; to: number } | null>(null)
  /**
   * 고칠 것이 많으면 그것대로 막힌다.
   * 처음에는 **고르지 않아도 되는 것**을 감춰 둔다 — 그대로 만드셔도 좋은 영상이 나온다.
   */
  const [advanced, setAdvanced] = useState(false)
  /** 만들다 끊긴 것인가 — 그래도 담긴 데까지는 드린다 */
  const recorderRef = useRef<MediaRecorder | null>(null)
  const abortedRef = useRef(false)
  /** 만들어 둔 토막들 — 나중에 한 편으로 잇는다 */
  const [parts, setParts] = useState<VideoPart[]>([])
  const [joining, setJoining] = useState<string | null>(null)

  const [playing, setPlaying] = useState(false)
  const [recording, setRecording] = useState(false)
  const [clock, setClock] = useState(0)
  const [result, setResult] = useState<{
    url: string
    label: string
    note: string
    name: string
    bytes: number
    partial: boolean
    /** 맛보기로 만든 것인가 — 보시고 무엇을 만질지 함께 알려 드린다 */
    taster?: boolean
  } | null>(null)
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
  const template = useMemo(() => getVideoTemplate(templateId), [templateId])
  const size = SIZES.find((item) => item.id === sizeId) ?? SIZES[0]

  /** 로고 그림 — 그릴 때 읽으면 첫 프레임이 비어 나온다. 미리 읽어 둔다 */
  const [logoImg, setLogoImg] = useState<HTMLImageElement | null>(null)
  useEffect(() => {
    if (!logoUrl) {
      setLogoImg(null)
      return
    }
    let alive = true
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => alive && setLogoImg(img)
    img.onerror = () => alive && setLogoImg(null)
    img.src = logoUrl
    return () => {
      alive = false
    }
  }, [logoUrl])

  const logo: LogoMark | null = useMemo(() => {
    if (!logoImg || logoPlace === 'none') return null
    return {
      image: logoImg,
      width: logoImg.naturalWidth || logoImg.width,
      height: logoImg.naturalHeight || logoImg.height,
      place: logoPlace,
    }
  }, [logoImg, logoPlace])

  const auto = useMemo(
    () =>
      fitToLimit(
        buildStoryboard({ event, plan, academyName, photos, photoSets, messages, extras, options, closing }),
      ),
    [event, plan, academyName, photos, photoSets, messages, extras, options, closing],
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
  /** 이번에 실제로 담을 장면들 — 구간을 고르지 않으셨으면 전부 */
  const recordScenes = useMemo(() => {
    if (!range) return scenes
    const from = Math.min(Math.max(0, range.from), scenes.length - 1)
    const to = Math.min(Math.max(from, range.to), scenes.length - 1)
    return scenes.slice(from, to + 1)
  }, [scenes, range])
  const recordTimeline = useMemo(() => buildTimeline(recordScenes), [recordScenes])
  /**
   * 앞 30초만 먼저 만들어 보실 구간.
   *
   * 12분짜리는 만드는 데도 12분이 걸린다. 다 기다리신 뒤에 "이게 아닌데" 를 아시면
   * 그 12분이 통째로 날아간다. 짧은 영상이면 굳이 나눌 것이 없으므로 안 보여 준다.
   */
  const starts = useMemo(() => tasterStarts(scenes), [scenes])
  /**
   * 어디를 맛볼지.
   *
   * 앞 30초는 대개 표지라 아이 장면부터도 고르실 수 있고, 앞·가운데·끝을 조금씩
   * 이어 보실 수도 있다 — 걱정되는 것은 대개 "끝까지 이 느낌인가" 라서다.
   */
  const [startId, setStartId] = useState<'head' | 'performers' | 'spread'>('head')
  const start = starts.find((item) => item.id === startId) ?? starts[0]
  const spread = useMemo(() => (startId === 'spread' ? tasterSpread(scenes) : null), [startId, scenes])
  const taster = useMemo(
    () => (spread ? { from: spread[0], to: spread[spread.length - 1] } : tasterRange(scenes, TASTER_SEC, start?.index ?? 0)),
    [spread, scenes, start],
  )
  /** 실제로 담기는 장면들 — 이어 붙이기면 고른 것만, 아니면 구간 통째로 */
  const tasterScenes = useMemo(() => {
    if (spread) return spread.map((i) => scenes[i])
    return taster ? scenes.slice(taster.from, taster.to + 1) : []
  }, [spread, taster, scenes])
  const tasterSec = useMemo(() => totalSeconds(tasterScenes), [tasterScenes])
  const withPhoto = Object.keys(photos).length
  /**
   * 지금 화면에 보이는 장면 — 콘티에서 표시해 준다.
   * 구간만 만드는 중에는 시계가 그 구간 기준이므로 시작 장면만큼 밀어 준다.
   */
  const activeIndex = useMemo(() => {
    const line = recording ? recordTimeline : timeline
    const offset = recording && range ? range.from : 0
    let found = 0
    for (let i = 0; i < line.starts.length; i += 1) {
      if (clock >= line.starts[i]) found = i
    }
    return found + offset
  }, [timeline, recordTimeline, recording, range, clock])
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
      // 한 장면 안에서 넘어가는 사진들과, 응원에 얹는 아이 얼굴도 미리 읽는다
      for (const shot of scene.images ?? []) urls.add(shot)
      if (scene.badge) urls.add(scene.badge)
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

  const drawOn = useCallback(
    (line: Timeline, seconds: number, still = false) => {
      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      renderFrame(
        ctx,
        line,
        seconds,
        sourcesRef.current,
        { width: canvas.width, height: canvas.height, theme, academyName, template, logo },
        still,
      )
    },
    [theme, academyName, template, logo],
  )

  const draw = useCallback(
    (seconds: number, still = false) => drawOn(timeline, seconds, still),
    [drawOn, timeline],
  )

  useEffect(() => {
    if (!playing && !recording) draw(clock, true)
  }, [draw, clock, playing, recording])

  /**
   * 재생·녹화 공통 진행 루프.
   *
   * `rate` 는 **미리보기 전용**이다. 녹화는 화면에 그려지는 그대로 담기므로
   * 빨리 돌리면 영상 자체가 빨라진다 — 그래서 record() 는 늘 1을 준다.
   */
  const runLoop = useCallback(
    (onDone: () => void, from = 0, rate = 1, line: Timeline = timeline) => {
      const started = performance.now() - (from * 1000) / rate
      const playedClips = new Set<string>()
      const step = () => {
        const seconds = ((performance.now() - started) * rate) / 1000
        // 이 시각에 보여야 할 동영상은 재생시켜 둔다
        for (let i = 0; i < line.scenes.length; i += 1) {
          const scene = line.scenes[i]
          if (!scene.clip) continue
          const start = line.starts[i]
          const el = sourcesRef.current.videos.get(scene.clip)
          if (!el) continue
          if (seconds >= start && seconds < start + scene.seconds) {
            if (!playedClips.has(scene.clip)) {
              playedClips.add(scene.clip)
              el.currentTime = 0
              // 올린 동영상도 같은 배속으로 — 4배는 브라우저가 거절할 수 있어 받아 낸다
              try {
                el.playbackRate = rate
              } catch {
                /* 못 바꾸면 제 속도로 둔다 */
              }
              void el.play().catch(() => undefined)
            }
          } else if (playedClips.has(scene.clip) && !el.paused) {
            el.pause()
          }
        }
        drawOn(line, seconds)
        setClock(seconds)
        if (seconds >= line.total) {
          onDone()
          return
        }
        rafRef.current = requestAnimationFrame(step)
      }
      rafRef.current = requestAnimationFrame(step)
    },
    [drawOn, timeline],
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
      audioRef.current.playbackRate = speed
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
      speed,
    )
  }

  /**
   * 재생 중에 속도를 바꾸면 그 자리에서 바로 바뀐다.
   * 멈췄다 다시 누르게 하면 보던 자리를 놓친다.
   */
  function changeSpeed(next: (typeof SPEEDS)[number]) {
    setSpeed(next)
    if (!playing) return
    const from = clockRef.current
    stopLoop()
    if (music && audioRef.current) {
      audioRef.current.currentTime = from
      audioRef.current.playbackRate = next
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
      next,
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

  /** 만드는 중에 멈추기 — 담긴 데까지는 파일로 드린다 */
  function stopRecording() {
    abortedRef.current = true
    stopLoop()
    try {
      recorderRef.current?.stop()
    } catch {
      /* 이미 멈춰 있으면 그대로 */
    }
  }

  /**
   * 영상 담기.
   *
   * `override` 를 주면 그 구간만 담는다. 화면의 구간 상태를 바꾼 **직후**에도
   * 바로 담을 수 있어야 해서다 — 상태는 다음 그림에서야 바뀌므로 그때까지
   * 기다리면 엉뚱한 구간이 담긴다.
   */
  async function record(
    override?: { from: number; to: number },
    isTaster = false,
    /** 이어 붙여 담을 장면들 (앞·가운데·끝처럼 떨어져 있는 것) */
    picked?: VideoScene[],
  ) {
    const canvas = canvasRef.current
    if (!canvas || !recordType) return
    setWarning(null)
    setResult(null)
    setRecording(true)
    setClock(0)
    abortedRef.current = false
    const span = override ?? range
    const line = picked?.length
      ? buildTimeline(picked)
      : override
        ? buildTimeline(
            scenes.slice(
              Math.min(Math.max(0, override.from), scenes.length - 1),
              Math.min(Math.max(0, override.to), scenes.length - 1) + 1,
            ),
          )
        : recordTimeline

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
      gain.gain.setValueAtTime(0.9, now + Math.max(2, line.total - 2.5))
      gain.gain.linearRampToValueAtTime(0, now + line.total)
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
    recorderRef.current = recorder
    // 500ms 마다 조각을 받아 둔다 — 중간에 끊겨도 여기까지는 남는다
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

    runLoop(
      () => {
        stopLoop()
        try {
          recorder.stop()
        } catch {
          /* 이미 멈춰 있으면 그대로 */
        }
      },
      0,
      1,
      line,
    )

    await finished
    document.removeEventListener('visibilitychange', onHidden)
    recorderRef.current = null
    void audio.close()
    const info = describeRecordType(recorder.mimeType || recordType)
    const blob = new Blob(chunks, { type: recorder.mimeType || recordType })
    const partial = abortedRef.current
    const label = isTaster
      ? ` (${TASTER_SEC}초 맛보기${picked?.length ? ' · 앞가운데끝' : span && span.from > 0 ? ' · 아이 장면부터' : ''})`
      : span
        ? ` ${span.from + 1}-${Math.min(span.to, scenes.length - 1) + 1}장면`
        : ''
    const madeUrl = URL.createObjectURL(blob)
    // 만든 것은 토막 목록에 남겨 둔다 — 나중에 한 편으로 이을 수 있게
    setParts((prev) => [
      ...prev,
      {
        id: `part-${Date.now()}`,
        label: `${isTaster ? `${TASTER_SEC}초 맛보기${picked?.length ? ' · 앞가운데끝' : ''}` : span ? `${span.from + 1}-${Math.min(span.to, scenes.length - 1) + 1}장면` : '전체'}${partial ? ' (중간까지)' : ''}`,
        url: madeUrl,
        seconds: partial ? Math.round(clockRef.current) : Math.round(line.total),
        made: true,
      },
    ])
    setResult({
      url: madeUrl,
      label: partial ? `${info.label} · 중간까지` : isTaster ? `${info.label} · 맛보기` : info.label,
      note: partial
        ? `만들다 멈춰 ${formatLength(clockRef.current)} 까지만 담겼습니다. 그래도 재생됩니다 — 이어서 만드시려면 아래 [만들 구간]에서 멈춘 장면부터 고르세요.`
        : isTaster
          ? picked?.length
            ? '앞·가운데·끝에서 한 장면씩 이어 붙인 맛보기입니다. 장면 사이가 건너뛴 것처럼 보이는 것은 그래서이고, 진짜 영상은 이어집니다. 마음에 드시면 [영상 만들기] 로 전체를 만드세요.'
            : '앞부분만 담은 맛보기입니다. 글씨 크기·사진·음악을 여기서 확인하시고, 마음에 드시면 [영상 만들기] 로 전체를 만드세요.'
          : info.note,
      name: `${event.title.replace(/[\\/:*?"<>|]/g, ' ').trim() || '연주회'} 감동영상${label}${partial ? ' (중간까지)' : ''}.${info.ext}`,
      bytes: blob.size,
      partial,
      taster: isTaster,
    })
    setRecording(false)
    setClock(0)
    draw(0)
  }

  /**
   * 토막들을 한 편으로 잇는다.
   *
   * 파일을 바이트로 붙일 수는 없다(lib/video/join.ts 에 적어 두었다).
   * 토막을 차례로 틀면서 그 화면을 새로 담는다 — 토막 길이의 합만큼 걸리지만
   * 나오는 것은 진짜 한 편이다.
   */
  async function joinParts() {
    const canvas = canvasRef.current
    if (!canvas || !recordType || !canJoin(parts)) return
    setWarning(null)
    setResult(null)
    setJoining('준비 중…')
    abortedRef.current = false

    // 이 컴퓨터에 빠른 잇기 도구가 있으면 몇 초에 끝난다. 원장님께 묻지 않는다 —
    // 있으면 쓰고 없으면 하던 대로 다시 담는다
    if (await joinFast()) return

    // 토막을 미리 다 읽어 둔다 — 트는 도중에 읽으면 사이가 끊긴다
    const players: HTMLVideoElement[] = []
    await Promise.all(
      parts.map(
        (part) =>
          new Promise<void>((resolve) => {
            const el = document.createElement('video')
            el.src = part.url
            el.preload = 'auto'
            el.playsInline = true
            players.push(el)
            el.onloadeddata = () => resolve()
            el.onerror = () => resolve()
          }),
      ),
    )

    const ctx = canvas.getContext('2d')
    if (!ctx) {
      setJoining(null)
      return
    }

    const stream = canvas.captureStream(30)
    const audio = new AudioContext()
    const mixer = audio.createMediaStreamDestination()
    let anyAudio = false
    for (const el of players) {
      try {
        audio.createMediaElementSource(el).connect(mixer)
        anyAudio = true
      } catch {
        /* 소리가 없는 토막은 그대로 둔다 */
      }
    }
    if (anyAudio) for (const track of mixer.stream.getAudioTracks()) stream.addTrack(track)

    const recorder = new MediaRecorder(stream, {
      mimeType: recordType,
      videoBitsPerSecond: size.h >= 1080 ? 8_000_000 : 4_500_000,
    })
    recorderRef.current = recorder
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

    // 한 토막씩 틀면서 그대로 캔버스에 옮겨 그린다
    for (let index = 0; index < players.length && !abortedRef.current; index += 1) {
      const el = players[index]
      setJoining(`${index + 1} / ${players.length} · ${parts[index].label}`)
      el.currentTime = 0
      await el.play().catch(() => undefined)
      await new Promise<void>((resolve) => {
        let raf = 0
        const step = () => {
          if (abortedRef.current || el.ended) {
            cancelAnimationFrame(raf)
            resolve()
            return
          }
          // 토막마다 가로세로가 다를 수 있다 — 가운데에 맞춰 넣는다
          const vw = el.videoWidth || canvas.width
          const vh = el.videoHeight || canvas.height
          const scale = Math.min(canvas.width / vw, canvas.height / vh)
          const dw = vw * scale
          const dh = vh * scale
          ctx.fillStyle = '#000000'
          ctx.fillRect(0, 0, canvas.width, canvas.height)
          ctx.drawImage(el, (canvas.width - dw) / 2, (canvas.height - dh) / 2, dw, dh)
          raf = requestAnimationFrame(step)
        }
        el.onended = () => {
          cancelAnimationFrame(raf)
          resolve()
        }
        raf = requestAnimationFrame(step)
      })
      el.pause()
    }

    try {
      recorder.stop()
    } catch {
      /* 이미 멈춰 있으면 그대로 */
    }
    await finished
    document.removeEventListener('visibilitychange', onHidden)
    recorderRef.current = null
    void audio.close()

    const info = describeRecordType(recorder.mimeType || recordType)
    const blob = new Blob(chunks, { type: recorder.mimeType || recordType })
    setResult({
      url: URL.createObjectURL(blob),
      label: `${info.label} · ${parts.length}토막을 이음`,
      note: info.note,
      name: joinedName(event.title, info.ext),
      bytes: blob.size,
      partial: abortedRef.current,
    })
    setJoining(null)
    draw(0)
  }

  /**
   * 빠른 잇기 — 이 컴퓨터에 도구가 있을 때만.
   * 되면 true, 안 되면 false 를 돌려주고 부르는 쪽이 하던 대로 간다.
   */
  async function joinFast(): Promise<boolean> {
    try {
      const probe = await fetch('/api/video/join')
      if (!probe.ok || !(await probe.json()).available) return false
      setJoining('빠르게 잇는 중…')

      const form = new FormData()
      for (const [index, part] of parts.entries()) {
        const blob = await (await fetch(part.url)).blob()
        const ext = blob.type.includes('mp4') ? 'mp4' : 'webm'
        form.append('parts', new File([blob], `part-${index}.${ext}`, { type: blob.type }))
      }
      const res = await fetch('/api/video/join', { method: 'POST', body: form })
      if (!res.ok) return false

      const blob = await res.blob()
      if (blob.size < 1000) return false
      const ext = blob.type.includes('mp4') ? 'mp4' : 'webm'
      setResult({
        url: URL.createObjectURL(blob),
        label: `${parts.length}토막을 이음 · 빠르게`,
        note: '이 컴퓨터에 있는 도구로 몇 초 만에 이었습니다. 다시 담지 않아 화질도 그대로입니다.',
        name: joinedName(event.title, ext),
        bytes: blob.size,
        partial: false,
      })
      setJoining(null)
      return true
    } catch {
      // 빠른 길이 막히면 조용히 제 길로 간다 — 원장님은 몰라도 된다
      return false
    }
  }

  function addParts(files: FileList) {
    const added: VideoPart[] = []
    for (const file of Array.from(files)) {
      const url = URL.createObjectURL(file)
      const id = `part-${Date.now()}-${added.length}`
      added.push({ id, label: file.name.replace(/\.[^.]+$/, ''), url, seconds: 0, made: false })
      // 길이를 읽어 둔다 — 잇는 데 얼마나 걸릴지 먼저 알려 드려야 한다
      const probe = document.createElement('video')
      probe.preload = 'metadata'
      probe.onloadedmetadata = () => {
        setParts((prev) =>
          prev.map((row) => (row.id === id ? { ...row, seconds: Math.round(probe.duration) || 0 } : row)),
        )
      }
      probe.src = url
    }
    setParts((prev) => [...prev, ...added])
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

  /** 지금 화면에서 고른 값 — 이대로 행사에 저장한다 */
  const currentPrefs: Prefs = {
    theme: themeId,
    template: templateId,
    size: sizeId,
    logo_place: logoPlace,
    captions: options.captions,
    messages: options.messages,
    student_seconds: options.student_seconds,
    title_seconds: options.title_seconds,
    gallery_seconds: options.gallery_seconds,
    closing,
  }

  /** 저장해 둔 설정을 화면에 얹는다. 없는 값은 지금 것을 그대로 둔다 */
  function applyPrefs(prefs: Prefs) {
    setThemeId((prev) => prefString(prefs, 'theme', prev))
    setTemplateId((prev) => prefString(prefs, 'template', prev))
    setSizeId((prev) => prefString<(typeof SIZES)[number]['id']>(prefs, 'size', prev))
    setLogoPlace((prev) => getLogoPlace(prefString(prefs, 'logo_place', prev)))
    setClosing((prev) => prefString(prefs, 'closing', prev))
    setOptions((prev) => ({
      student_seconds: prefNumber(prefs, 'student_seconds', prev.student_seconds),
      title_seconds: prefNumber(prefs, 'title_seconds', prev.title_seconds),
      gallery_seconds: prefNumber(prefs, 'gallery_seconds', prev.gallery_seconds),
      captions: prefBool(prefs, 'captions', prev.captions),
      messages: prefBool(prefs, 'messages', prev.messages),
    }))
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
      <div className="grid min-w-0 content-start gap-3">
        {/* 미리보기는 화면에 붙여 둔다 — 아래에서 템플릿을 고르는 동안에도 늘 보여야 한다.
            예전에는 고르러 내려가면 화면이 위로 사라져, 무엇이 바뀌었는지 볼 수가 없었다. */}
        <div className="sticky top-16 z-10 overflow-hidden rounded-lg border border-border bg-black lg:top-20">
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
            onClick={() => (recording ? stopRecording() : void record())}
            disabled={!ready || !recordType || playing}
          >
            {recording ? <Square className="mr-1 h-4 w-4" /> : <Film className="mr-1 h-4 w-4" />}
            {recording ? '여기까지 만들고 멈추기' : range ? '고른 구간 만들기' : '영상 만들기'}
          </Button>
          {/* 다 만든 뒤에 아시면 늦다. 앞 30초로 먼저 확인하시게 */}
          {taster && !recording && (
            <span className="flex flex-wrap items-center gap-1.5">
              <Button
                size="sm"
                variant="outline"
                onClick={() => void record(taster, true, spread ? tasterScenes : undefined)}
                disabled={!ready || !recordType || playing}
                data-testid="video-taster"
                title={
                  spread
                    ? `앞·가운데·끝에서 ${tasterScenes.length}장면(${formatLength(tasterSec)})을 이어 붙여 담습니다`
                    : `${taster.from + 1}~${taster.to + 1}장면 ${tasterScenes.length}장면(${formatLength(tasterSec)})만 담아 봅니다`
                }
              >
                <Timer className="mr-1 h-4 w-4" aria-hidden />
                {TASTER_SEC}초만 먼저 만들어 보기
              </Button>
              {/* 앞 30초는 대개 표지다. 정작 보고 싶으신 것은 아이가 나오는 화면이다 */}
              {starts.length > 1 && (
                <span className="flex items-center gap-0.5 rounded-md border border-border p-0.5" data-testid="taster-start">
                  {starts.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setStartId(item.id)}
                      aria-pressed={item.id === startId}
                      disabled={recording}
                      className={cn(
                        'rounded px-2 py-1 text-xs transition-colors disabled:opacity-40',
                        item.id === startId ? 'bg-primary font-medium text-primary-foreground' : 'hover:bg-secondary',
                      )}
                    >
                      {item.label}
                    </button>
                  ))}
                </span>
              )}
            </span>
          )}
          <div className="flex items-center gap-1" data-testid="preview-speed">
            <Gauge className="h-4 w-4 text-muted-foreground" aria-hidden />
            {SPEEDS.map((rate) => (
              <button
                key={rate}
                type="button"
                onClick={() => changeSpeed(rate)}
                aria-pressed={speed === rate}
                aria-label={`${rate}배 속도로 보기`}
                disabled={recording}
                className={cn(
                  'rounded-full border px-2.5 py-1 text-xs tabular-nums transition-colors disabled:opacity-40',
                  speed === rate
                    ? 'border-accent bg-accent/10 font-medium text-foreground'
                    : 'border-border text-muted-foreground hover:bg-secondary',
                )}
              >
                {rate}배
              </button>
            ))}
          </div>
          <span className="text-sm tabular-nums text-muted-foreground" data-testid="video-length">
            {formatLength(clock)} / {formatLength(length)} · 장면 {scenes.length}개
          </span>
          {!recording && !playing && ready && (
            <span className="text-xs text-muted-foreground">
              만드는 데 <strong className="text-foreground">약 {formatLength(recordTimeline.total)}</strong> 걸립니다
              {speed > 1 && (
                <>
                  {' '}· 미리보기는 <strong className="text-foreground">{formatLength(length / speed)}</strong> 만에
                  끝납니다
                </>
              )}
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
            ({formatLength(recordTimeline.total)}) 걸립니다. 다른 창으로 넘어가면 끊깁니다.
            <br />
            급하시면 <strong>[여기까지 만들고 멈추기]</strong> 를 누르세요 — 담긴 데까지 파일로 드립니다.
          </p>
        )}
        {warning && <p className="text-sm text-destructive">{warning}</p>}

        {result && (
          <div className="grid gap-2 rounded-md border border-accent/40 bg-accent/5 p-3">
            <p className="text-sm font-medium">
              {result.partial ? '여기까지 만들어졌습니다' : '영상이 만들어졌습니다'} · {result.label} ·{' '}
              {Math.round(result.bytes / 1024 / 1024)}MB
            </p>
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

            {/* 보시고 "이게 아닌데" 하신 다음이 없었다 — 어디를 만지는지 그 자리에 적어 둔다 */}
            {result.taster && !result.partial && (
              <div className="grid gap-1.5 rounded-md border border-border bg-background p-3" data-testid="taster-fixes">
                <p className="text-sm font-medium">보시고 마음에 안 드는 것이 있으면</p>
                <dl className="grid gap-1.5 text-xs">
                  {TASTER_FIXES.map((fix) => (
                    <div key={fix.symptom} className="sm:flex sm:gap-2">
                      <dt className="shrink-0 font-medium sm:w-40">{fix.symptom}</dt>
                      <dd className="text-muted-foreground">
                        <strong className="text-foreground">{fix.where}</strong> — {fix.how}
                      </dd>
                    </div>
                  ))}
                </dl>
                <p className="text-xs text-muted-foreground">
                  고치신 뒤에 <strong>다시 30초만</strong> 만들어 보시면 됩니다. 30초면 끝나니 몇 번이든 하세요.
                </p>
              </div>
            )}
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
          template={template}
          logo={logo}
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

      <div className="grid min-w-0 content-start gap-4">
        <section className="grid gap-1.5 rounded-lg border border-accent/40 bg-accent/5 p-3" data-testid="video-ready">
          <p className="text-sm font-medium">이대로 만드셔도 됩니다</p>
          <p className="text-xs text-muted-foreground">
            명단과 아이 사진에서 <strong>{scenes.length}장면 · {formatLength(length)}</strong> 짜리가 이미 짜여 있습니다.
            아래 그림이 나올 화면 그대로입니다. 왼쪽 <strong>[영상 만들기]</strong> 만 누르시면 됩니다.
          </p>
          <p className="text-xs text-muted-foreground">
            바꾸고 싶은 것이 있을 때만 아래를 손보세요.
          </p>
        </section>

        <section className="grid gap-2 rounded-lg border border-border p-3" data-testid="video-templates">
          <p className="text-sm font-medium">
            0 · 영상 템플릿 · {VIDEO_TEMPLATES.length}종
            <span className="ml-1.5 text-xs font-normal text-muted-foreground">
              사진을 어떻게 놓고 어떤 배경을 깔지
            </span>
          </p>
          <div className="flex flex-wrap gap-1.5">
            {VIDEO_TEMPLATES.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTemplateId(item.id)}
                aria-pressed={item.id === templateId}
                title={item.hint}
                className={cn(
                  'rounded-full border px-2.5 py-1 text-xs transition-colors',
                  item.id === templateId
                    ? 'border-accent bg-accent/10 font-medium text-foreground'
                    : 'border-border text-muted-foreground hover:bg-secondary',
                )}
              >
                {item.name}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">{template.hint}</p>
        </section>

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

        <div className="no-print">
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={() => setAdvanced((prev) => !prev)}
            aria-expanded={advanced}
            data-testid="video-advanced-toggle"
          >
            <ChevronDown className={cn('mr-1 h-4 w-4 transition-transform', advanced && 'rotate-180')} />
            {advanced ? '자세한 설정 접기' : '자세히 고치기 — 테마 · 길이 · 로고 · 구간 · 초대장'}
          </Button>
        </div>

        <section className={cn('grid gap-2 rounded-lg border border-border p-3', !advanced && 'hidden')}>
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

          <label className={cn('flex cursor-pointer items-center gap-2 text-sm')}>
            <input
              type="checkbox"
              checked={options.messages}
              onChange={(native) => setOptions((prev) => ({ ...prev, messages: native.target.checked }))}
              className="h-4 w-4"
              disabled={messages.length === 0}
              aria-label="학부모 응원 메시지 넣기"
            />
            <MessageSquareHeart className="h-4 w-4 text-accent" aria-hidden />
            학부모 응원 메시지 넣기
            <span className="text-xs text-muted-foreground">
              {messages.length > 0 ? `초대장에 ${messages.length}통 와 있습니다` : '아직 온 메시지가 없습니다'}
            </span>
          </label>

          <div data-testid="logo-place">
            <p className="mb-1 text-sm">학원 로고</p>
            {logoUrl ? (
              <>
                <div className="flex flex-wrap gap-1.5">
                  {LOGO_PLACES.map((place) => (
                    <button
                      key={place.id}
                      type="button"
                      onClick={() => setLogoPlace(place.id)}
                      aria-pressed={logoPlace === place.id}
                      className={cn(
                        'rounded-full border px-3 py-1 text-xs transition-colors',
                        logoPlace === place.id
                          ? 'border-accent bg-accent/15 font-medium'
                          : 'border-border text-muted-foreground hover:bg-secondary',
                      )}
                    >
                      {place.label}
                    </button>
                  ))}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  영상은 학부모 휴대폰을 돌아다닙니다. 구석에 작게 넣어 두면 어느 학원 것인지 남습니다.
                </p>
              </>
            ) : (
              <p className="text-xs text-muted-foreground">
                학원 로고를 올려 두시면 영상 구석에 넣을 수 있습니다 —{' '}
                <a href="/settings" className="underline underline-offset-4">
                  학원 설정
                </a>
                에서 올리세요.
              </p>
            )}
          </div>
        </section>

        <section
          className={cn('grid gap-2 rounded-lg border border-border p-3', !advanced && 'hidden')}
          data-testid="record-range"
        >
          <p className="text-sm font-medium">
            5 · 만들 구간
            <span className="ml-1.5 text-xs font-normal text-muted-foreground">토막을 나눠 만들 수 있습니다</span>
          </p>
          <p className="text-xs text-muted-foreground">
            긴 영상은 <strong>두세 토막</strong>으로 나눠 만드시는 편이 낫습니다. 한 토막이 짧아 다시 만들기도 쉽고,
            중간에 끊겨도 잃는 시간이 적습니다. 받으신 파일은 이어 붙이시면 한 편이 됩니다.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={range ? range.from : 0}
              onChange={(native) =>
                setRange((prev) => {
                  const from = Number(native.target.value)
                  const to = Math.max(from, prev?.to ?? scenes.length - 1)
                  return { from, to }
                })
              }
              className="h-9 min-w-0 max-w-[46%] flex-1 rounded-md border border-border bg-background px-2 text-sm"
              aria-label="시작 장면"
            >
              {scenes.map((scene, index) => (
                <option key={scene.id} value={index}>
                  {index + 1}. {sceneLabel(scene)}
                </option>
              ))}
            </select>
            <span className="text-sm text-muted-foreground">부터</span>
            <select
              value={range ? Math.min(range.to, scenes.length - 1) : scenes.length - 1}
              onChange={(native) =>
                setRange((prev) => {
                  const to = Number(native.target.value)
                  const from = Math.min(to, prev?.from ?? 0)
                  return { from, to }
                })
              }
              className="h-9 min-w-0 max-w-[46%] flex-1 rounded-md border border-border bg-background px-2 text-sm"
              aria-label="끝 장면"
            >
              {scenes.map((scene, index) => (
                <option key={scene.id} value={index}>
                  {index + 1}. {sceneLabel(scene)}
                </option>
              ))}
            </select>
          </div>
          <p className="flex flex-wrap items-center gap-2 text-xs">
            <Scissors className="h-3.5 w-3.5 text-accent" aria-hidden />
            <span className="text-muted-foreground">
              고른 구간 <strong className="text-foreground">{recordScenes.length}장면 · {formatLength(recordTimeline.total)}</strong>
            </span>
            {range && (
              <Button variant="ghost" size="sm" onClick={() => setRange(null)}>
                전체로 되돌리기
              </Button>
            )}
          </p>
        </section>

        <section
          className={cn('grid gap-2 rounded-lg border border-border p-3', !advanced && 'hidden')}
          data-testid="join-parts"
        >
          <p className="text-sm font-medium">
            6 · 토막을 한 편으로 잇기
            <span className="ml-1.5 text-xs font-normal text-muted-foreground">
              {parts.length > 0 ? joinLabel(parts) : '아직 만든 토막이 없습니다'}
            </span>
          </p>
          {parts.length > 0 && (
            <ul className="grid gap-1">
              {parts.map((part, index) => (
                <li key={part.id} className="flex items-center gap-2 text-xs">
                  <span className="w-4 shrink-0 tabular-nums text-muted-foreground">{index + 1}</span>
                  <span className="rounded bg-secondary px-1.5 py-0.5">{part.made ? '만든 것' : '파일'}</span>
                  <span className="min-w-0 flex-1 truncate">{part.label}</span>
                  <span className="shrink-0 tabular-nums text-muted-foreground">
                    {part.seconds > 0 ? formatLength(part.seconds) : '읽는 중…'}
                  </span>
                  <button
                    type="button"
                    onClick={() => setParts((prev) => movePart(prev, index, -1))}
                    disabled={index === 0 || !!joining}
                    aria-label={`${part.label} 앞으로`}
                    className="px-1 text-muted-foreground disabled:opacity-30"
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    onClick={() => setParts((prev) => movePart(prev, index, 1))}
                    disabled={index === parts.length - 1 || !!joining}
                    aria-label={`${part.label} 뒤로`}
                    className="px-1 text-muted-foreground disabled:opacity-30"
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    onClick={() => setParts((prev) => prev.filter((row) => row.id !== part.id))}
                    disabled={!!joining}
                    aria-label={`${part.label} 빼기`}
                  >
                    <Trash2 className="h-3.5 w-3.5 text-destructive" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          {/* 연주회 전날 밤에 만들었는데 회신이 당일 아침에 온다 — 그 부분만 다시 만들면 된다 */}
          {(() => {
            const cheer = cheerRange(scenes)
            if (!cheer) return null
            const seconds = scenes.slice(cheer.from, cheer.to + 1).reduce((sum, scene) => sum + scene.seconds, 0)
            return (
              <div className="grid gap-1 rounded-md border border-accent/40 bg-accent/5 px-3 py-2">
                <p className="text-xs">
                  <strong>응원이 새로 왔나요?</strong> 전체를 다시 만들지 마시고 응원 부분만 만들어 뒤에 이으세요 —{' '}
                  <strong>{formatLength(seconds)}</strong> 면 됩니다.
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  className="w-fit"
                  disabled={recording || playing || !!joining || !recordType}
                  onClick={() => {
                    setRange(cheer)
                    void record(cheer)
                  }}
                >
                  <MessageSquareHeart className="mr-1 h-4 w-4" />
                  응원 부분만 만들기
                </Button>
              </div>
            )
          })()}
          <div className="flex flex-wrap items-center gap-2">
            <label className="inline-flex h-9 cursor-pointer items-center rounded-md border border-input px-3 text-sm hover:bg-secondary">
              <Film className="mr-1 h-4 w-4" />
              전에 만든 파일 더하기
              <input
                type="file"
                accept="video/*"
                multiple
                className="sr-only"
                onChange={(native) => {
                  if (native.target.files?.length) addParts(native.target.files)
                  native.target.value = ''
                }}
              />
            </label>
            <Button
              size="sm"
              variant="outline"
              onClick={() => (joining ? stopRecording() : void joinParts())}
              disabled={!recordType || recording || playing || (!joining && !canJoin(parts))}
            >
              {joining ? <Square className="mr-1 h-4 w-4" /> : <Merge className="mr-1 h-4 w-4" />}
              {joining ? '멈추기' : '한 편으로 잇기'}
            </Button>
            {joining && <span className="text-xs tabular-nums text-muted-foreground">{joining}</span>}
          </div>
          <p className="text-xs text-muted-foreground">
            {joinBlocker(parts) ??
              `이 컴퓨터에 빠른 잇기 도구가 있으면 몇 초, 없으면 ${formatLength(partsSeconds(parts))} 걸립니다.`}
          </p>
          <p className="text-xs text-muted-foreground">
            영상 파일은 <strong>그냥 이어 붙일 수 없습니다.</strong> 앞머리에 전체 길이와 자리표가 들어 있어
            바이트로 붙이면 재생기마다 다르게 굽니다. 그래서 도구가 없으면 <strong>다시 한 번 담습니다</strong> —
            시간이 걸리는 대신 나오는 것은 진짜 한 편입니다. <strong>고르실 것은 없습니다</strong> —
            빠른 길이 있으면 알아서 그쪽으로 갑니다.
          </p>
        </section>

        <div className={cn(!advanced && 'hidden')}>
          <PrefsBar
            eventId={event.id}
            field="video_prefs"
            label="영상 설정"
            prefs={currentPrefs}
            saved={savedPrefs}
            past={pastPrefs}
            onLoad={applyPrefs}
          />
        </div>

        <div className={cn(!advanced && 'hidden')}>
          <InviteVideoLink eventId={event.id} initialUrl={event.video_url} />
        </div>
      </div>
    </div>
  )
}

/**
 * 만든 영상을 초대장에 붙인다.
 *
 * 영상 파일은 원장님 컴퓨터에 있다 — 아이들 얼굴을 우리 서버로 올리지 않겠다는
 * 약속이 그 뿌리다. 그래서 **원장님이 올려 두신 곳의 주소**만 받는다.
 * 유튜브 일부공개면 검색에도 안 걸리고, 링크를 아는 학부모만 본다.
 */
function InviteVideoLink({ eventId, initialUrl }: { eventId: string; initialUrl: string | null }) {
  const [url, setUrl] = useState(initialUrl ?? '')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const embed = videoEmbed(url)

  async function save() {
    setBusy(true)
    setMessage(null)
    try {
      const res = await fetch(`/api/events/${eventId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_url: url }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '저장하지 못했습니다.')
      setMessage(url.trim() ? '초대장에 영상이 붙었습니다.' : '초대장에서 영상을 뺐습니다.')
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '저장하지 못했습니다.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="grid gap-2 rounded-lg border border-border p-3" data-testid="invite-video">
      <p className="text-sm font-medium">
        7 · 초대장에 영상 붙이기
        <span className="ml-1.5 text-xs font-normal text-muted-foreground">단톡방에 링크 하나만</span>
      </p>
      <p className="text-xs text-muted-foreground">
        만든 영상을 <strong>유튜브 일부공개(미등록)</strong> 나 구글 드라이브에 올리고 그 주소를 붙여넣으세요.
        초대장 안에서 바로 재생됩니다. 학부모는 순서표와 영상을 링크 하나로 봅니다.
      </p>
      <div className="flex flex-wrap gap-2">
        <Input
          value={url}
          onChange={(native) => setUrl(native.target.value)}
          placeholder="https://youtu.be/…"
          aria-label="영상 주소"
          className="min-w-[200px] flex-1"
        />
        <Button size="sm" variant="outline" onClick={() => void save()} disabled={busy}>
          <Link2 className="mr-1 h-4 w-4" />
          붙이기
        </Button>
      </div>
      {url.trim() && (
        <p className="text-xs text-muted-foreground">
          {embed ? embedHint(embed) : '주소를 알아볼 수 없습니다. http:// 또는 https:// 로 시작하는 주소인지 확인해 주세요.'}
        </p>
      )}
      {message && <p className="text-xs text-muted-foreground">{message}</p>}
      <p className="text-xs text-muted-foreground">
        <strong>영상 파일은 이 프로그램이 보관하지 않습니다.</strong> 어디에 올릴지는 원장님이 정하십시오 —
        아이들 얼굴이 우리 서버로 올라가지 않게 하려는 것입니다.
      </p>
    </section>
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
  template,
  logo,
}: {
  timeline: ReturnType<typeof buildTimeline>
  sources: FrameSource
  theme: DesignTheme
  academyName: string
  template: VideoTemplate
  logo: LogoMark | null
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
        { width: canvas.width, height: canvas.height, theme, academyName, template, logo },
        true,
      )
      made.push(canvas.toDataURL('image/jpeg', 0.72))
    }
    setShots(made)
  }, [timeline, sources, theme, academyName, template, logo])

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
