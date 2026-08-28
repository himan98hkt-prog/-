'use client'

import { ChevronLeft, ChevronRight, Download, Maximize2, Moon, Palette, Printer, Sun } from 'lucide-react'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { PrefsBar, type PastPrefs } from '@/components/design/prefs-bar'
import { ThemePicker } from '@/components/design/theme-picker'
import { StageSlideView } from '@/components/stage/slide'
import { Button, buttonVariants } from '@/components/ui/button'
import { getTheme } from '@/lib/design/themes'
import { prefBool, prefString, type Prefs } from '@/lib/prefs'
import { buildStageDeck, STAGE_SLIDE_H, STAGE_SLIDE_W, type StageDeckOptions } from '@/lib/stage/deck'
import {
  DEFAULT_STAGE_BACKDROP,
  getStageBackdrop,
  STAGE_BACKDROPS,
  stageBackdropInfo,
  type StageBackdrop,
} from '@/lib/stage/backdrops'
import {
  DEFAULT_PHOTO_SHAPE,
  DEFAULT_STAGE_LAYOUT,
  getPhotoShape,
  getStageLayout,
  PHOTO_SHAPES,
  STAGE_LAYOUTS,
  stageLayoutInfo,
  type LayoutSketch,
  type PhotoShape,
  type StageLayout,
} from '@/lib/stage/layouts'
import type { EventRecord, ProgramPlan } from '@/lib/types'
import { cn } from '@/lib/utils'

/**
 * 연주회 당일 스크린.
 *
 * 노트북을 빔프로젝터에 연결하고 [전체화면] 을 누르면 끝이다.
 * 넘기기는 화살표·스페이스·클릭 — 리모컨(프레젠터)도 화살표 키를 보내므로 그대로 쓸 수 있다.
 *
 * 슬라이드는 이 화면에서 만든다. 그래서 테마를 바꾸거나 곡 해설을 끄면
 * 서버에 다시 묻지 않고 그 자리에서 바뀐다. 인터넷이 끊겨도 그대로 동작한다.
 */
export function StageScreen({
  event,
  plan,
  academyName,
  initialThemeId,
  logoUrl,
  photos = {},
  savedPrefs = null,
  pastPrefs = [],
}: {
  event: EventRecord
  plan: ProgramPlan
  academyName: string
  initialThemeId: string
  logoUrl: string | null
  /** 학생 id → 사진 주소 */
  photos?: Record<string, string>
  /** 이 행사에 저장해 둔 무대 화면 설정 */
  savedPrefs?: Prefs | null
  /** 설정을 저장해 둔 지난 행사들 */
  pastPrefs?: PastPrefs[]
}) {
  const [themeId, setThemeId] = useState(() => prefString(savedPrefs, 'theme', initialThemeId))
  const [layout, setLayout] = useState<StageLayout>(() =>
    getStageLayout(prefString(savedPrefs, 'layout', DEFAULT_STAGE_LAYOUT)),
  )
  const [shape, setShape] = useState<PhotoShape>(() =>
    getPhotoShape(prefString(savedPrefs, 'shape', DEFAULT_PHOTO_SHAPE)),
  )
  const [backdrop, setBackdrop] = useState<StageBackdrop>(() =>
    getStageBackdrop(prefString(savedPrefs, 'backdrop', DEFAULT_STAGE_BACKDROP)),
  )
  const [options, setOptions] = useState<StageDeckOptions>(() => ({
    show_commentary: prefBool(savedPrefs, 'show_commentary', true),
    show_sections: prefBool(savedPrefs, 'show_sections', true),
    show_agenda: prefBool(savedPrefs, 'show_agenda', true),
    show_photos: prefBool(savedPrefs, 'show_photos', true),
  }))
  const [index, setIndex] = useState(0)
  const [dark, setDark] = useState(() => prefBool(savedPrefs, 'dark', true))
  const [full, setFull] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const shellRef = useRef<HTMLDivElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)

  const theme = useMemo(() => getTheme(themeId), [themeId])
  const photoCount = Object.keys(photos).length
  /**
   * 모양 그림에 넣을 아이 사진 한 장.
   *
   * 회색 네모만 보여 드리면 "여기에 뭐가 들어가나" 를 머리로 그리셔야 한다.
   * 실제로 넣어 두신 얼굴이 들어가면 고르는 일이 훨씬 쉬워진다.
   * 사진이 아직 없으면 회색 네모 그대로 둔다 — 없는 것을 지어내지 않는다.
   */
  const sampleFace = Object.values(photos)[0] ?? null
  const slides = useMemo(
    () => buildStageDeck(event, plan, academyName, options, photos),
    [event, plan, academyName, options, photos],
  )
  const last = slides.length - 1

  // 화면을 끄면 보고 있던 장이 사라질 수 있다
  useEffect(() => {
    setIndex((prev) => Math.min(prev, slides.length - 1))
  }, [slides.length])

  const go = useCallback((next: number) => setIndex(Math.min(last, Math.max(0, next))), [last])

  const toggleFull = useCallback(async () => {
    const shell = shellRef.current
    if (!shell) return
    try {
      if (document.fullscreenElement) await document.exitFullscreen()
      else await shell.requestFullscreen()
    } catch {
      /* 브라우저가 막으면 그냥 창 모드로 쓴다 */
    }
  }, [])

  useEffect(() => {
    const onKey = (native: KeyboardEvent) => {
      // 테마 검색칸에 글자를 치는 중이면 화면을 넘기지 않는다
      const target = native.target as HTMLElement | null
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return

      if (native.key === 'ArrowRight' || native.key === 'PageDown' || native.key === ' ' || native.key === 'Enter') {
        native.preventDefault()
        setIndex((prev) => Math.min(last, prev + 1))
      } else if (native.key === 'ArrowLeft' || native.key === 'PageUp' || native.key === 'Backspace') {
        native.preventDefault()
        setIndex((prev) => Math.max(0, prev - 1))
      } else if (native.key === 'Home') {
        setIndex(0)
      } else if (native.key === 'End') {
        setIndex(last)
      } else if (native.key === 'f' || native.key === 'F') {
        void toggleFull()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [last, toggleFull])

  useEffect(() => {
    const onChange = () => setFull(Boolean(document.fullscreenElement))
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  /** 화면 폭에 맞춰 1280×720 을 통째로 줄인다 — 글자 크기가 서로 어긋나지 않는다 */
  useLayoutEffect(() => {
    const box = stageRef.current
    if (!box) return
    const fit = () => {
      const rect = box.getBoundingClientRect()
      const next = Math.min(rect.width / STAGE_SLIDE_W, rect.height / STAGE_SLIDE_H)
      setScale(next > 0 ? next : 1)
    }
    fit()
    const observer = new ResizeObserver(fit)
    observer.observe(box)
    window.addEventListener('resize', fit)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', fit)
    }
  }, [])

  const query = new URLSearchParams({ theme: themeId })
  if (!options.show_commentary) query.set('commentary', '0')
  if (!options.show_sections) query.set('sections', '0')
  if (!options.show_agenda) query.set('agenda', '0')
  if (!options.show_photos) query.set('photos', '0')
  if (dark) query.set('dark', '1')
  query.set('layout', layout)
  query.set('shape', shape)
  query.set('backdrop', backdrop)
  const pptxUrl = `/api/events/${event.id}/pptx?${query.toString()}`

  const slide = slides[Math.min(index, last)]

  /** 지금 고른 값 — 이대로 행사에 저장한다 */
  const currentPrefs: Prefs = {
    theme: themeId,
    layout,
    shape,
    backdrop,
    dark,
    show_commentary: options.show_commentary,
    show_sections: options.show_sections,
    show_agenda: options.show_agenda,
    show_photos: options.show_photos,
  }

  /** 저장해 둔 설정을 화면에 얹는다. 빠진 값은 지금 것을 그대로 둔다 */
  function applyPrefs(prefs: Prefs) {
    setThemeId((prev) => prefString(prefs, 'theme', prev))
    setLayout((prev) => getStageLayout(prefString(prefs, 'layout', prev)))
    setShape((prev) => getPhotoShape(prefString(prefs, 'shape', prev)))
    setBackdrop((prev) => getStageBackdrop(prefString(prefs, 'backdrop', prev)))
    setDark((prev) => prefBool(prefs, 'dark', prev))
    setOptions((prev) => ({
      show_commentary: prefBool(prefs, 'show_commentary', prev.show_commentary),
      show_sections: prefBool(prefs, 'show_sections', prev.show_sections),
      show_agenda: prefBool(prefs, 'show_agenda', prev.show_agenda),
      show_photos: prefBool(prefs, 'show_photos', prev.show_photos),
    }))
  }

  return (
    <div className="grid gap-3">
      <div
        ref={shellRef}
        className="relative bg-black no-print"
        style={{ display: 'flex', flexDirection: 'column', height: full ? '100vh' : undefined }}
      >
        <div
          ref={stageRef}
          onClick={() => setIndex((prev) => Math.min(last, prev + 1))}
          className="relative flex items-center justify-center overflow-hidden"
          style={{ flex: full ? 1 : undefined, aspectRatio: full ? undefined : '16 / 9', cursor: 'pointer' }}
          role="button"
          tabIndex={0}
          aria-label="다음 화면"
          onKeyDown={(pressed) => {
            if (pressed.key === 'Enter') setIndex((prev) => Math.min(last, prev + 1))
          }}
        >
          <div
            style={{
              width: STAGE_SLIDE_W,
              height: STAGE_SLIDE_H,
              transform: `scale(${scale})`,
              transformOrigin: 'center center',
              flexShrink: 0,
            }}
          >
            <StageSlideView
              slide={slide}
              theme={theme}
              academyName={academyName}
              dark={dark}
              logoUrl={logoUrl}
              layout={layout}
              shape={shape}
              backdrop={backdrop}
            />
          </div>
        </div>

        {/* 전체화면일 때만 뜨는 최소 조작 — 마우스를 아래로 내리면 보인다 */}
        {full ? (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-center p-4 opacity-0 transition-opacity hover:opacity-100 focus-within:opacity-100">
            <div className="pointer-events-auto flex items-center gap-2 rounded-full bg-black/70 px-3 py-1.5 text-white">
              <button type="button" onClick={() => go(index - 1)} aria-label="이전" className="px-2">
                <ChevronLeft className="h-5 w-5" />
              </button>
              <span className="text-sm tabular-nums">
                {index + 1} / {slides.length}
              </span>
              <button type="button" onClick={() => go(index + 1)} aria-label="다음" className="px-2">
                <ChevronRight className="h-5 w-5" />
              </button>
              <button type="button" onClick={() => void toggleFull()} aria-label="전체화면 끄기" className="px-2">
                <Maximize2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ) : null}
      </div>

      {/* 사회자 손에 들리는 조작줄 — 전체화면에서는 스크린에 나가지 않는다 */}
      <div className="no-print flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => go(index - 1)} disabled={index === 0}>
          <ChevronLeft className="mr-1 h-4 w-4" />
          이전
        </Button>
        <Button size="sm" onClick={() => go(index + 1)} disabled={index >= last}>
          다음
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
        <span className="text-sm tabular-nums text-muted-foreground" data-testid="stage-counter">
          {index + 1} / {slides.length}
        </span>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setDark((prev) => !prev)}>
            {dark ? <Sun className="mr-1 h-4 w-4" /> : <Moon className="mr-1 h-4 w-4" />}
            {dark ? '밝은 화면' : '어두운 화면'}
          </Button>
          <Button variant="outline" size="sm" onClick={() => void toggleFull()}>
            <Maximize2 className="mr-1 h-4 w-4" />
            전체화면
          </Button>
        </div>
      </div>

      <p className="no-print text-sm text-muted-foreground" data-testid="stage-next">
        다음 화면 — <strong className="text-foreground">{slide.next || '없음 (마지막)'}</strong>
        {slide.at ? ` · 예정 ${slide.at}` : ''}
      </p>

      {/* 테마 · 내용 · 내려받기 */}
      <div className="no-print grid gap-3 rounded-lg border border-border p-3 sm:grid-cols-[1fr_1fr]">
        <div className="grid gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setPickerOpen((prev) => !prev)} aria-expanded={pickerOpen}>
              <Palette className="mr-1 h-4 w-4" />
              테마 바꾸기
            </Button>
            <span className="text-sm">
              <strong>{theme.name}</strong>
              <span className="ml-1.5 text-xs text-muted-foreground">{theme.tagline}</span>
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            인쇄물과 같은 테마 100종입니다. 여기서 바꾸면 이 화면과 내려받는 파워포인트가 함께 바뀝니다.
          </p>
          {pickerOpen && (
            <div className="mt-1">
              <ThemePicker value={themeId} onChange={setThemeId} eventAt={event.event_at} compact />
            </div>
          )}
        </div>

        <div className="grid content-start gap-2">
          <p className="text-sm font-medium">
            연주자 화면 모양 · {STAGE_LAYOUTS.length}종
            <span className="ml-1.5 text-xs font-normal text-muted-foreground">
              이름은 위·오른쪽에만 — 아래는 피아노에 가립니다
            </span>
          </p>
          {/* 이름만 늘어놓으면 열네 가지를 못 고르신다 — 어디에 사진이 오고 글이 오는지 그려 준다 */}
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4" data-testid="layout-grid">
            {STAGE_LAYOUTS.map((item) => {
              const active = item.id === layout
              const blocked = item.needsPhoto && photoCount === 0
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setLayout(item.id)}
                  aria-pressed={active}
                  title={item.hint}
                  className={cn(
                    'grid gap-1 rounded-lg border p-1.5 text-left transition-colors',
                    active ? 'border-accent bg-accent/10' : 'border-border hover:bg-secondary',
                  )}
                >
                  <LayoutThumb sketch={item.sketch} active={active} face={sampleFace} />
                  <span className="px-0.5 text-[11px] leading-tight">
                    <span className={cn('block truncate', active && 'font-medium')}>{item.name}</span>
                    {blocked && <span className="block text-[10px] text-muted-foreground">사진 필요</span>}
                  </span>
                </button>
              )
            })}
          </div>
          <p className="text-xs text-muted-foreground">{stageLayoutInfo(layout).hint}</p>

          {layout === 'photo-frame' && (
            <div className="mt-1">
              <p className="mb-1 text-sm font-medium">
                사진 창 모양 · {PHOTO_SHAPES.length}종
              </p>
              <div className="flex flex-wrap gap-1.5">
                {PHOTO_SHAPES.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setShape(item.id)}
                    aria-pressed={item.id === shape}
                    className={cn(
                      'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors',
                      item.id === shape
                        ? 'border-accent bg-accent/10 font-medium text-foreground'
                        : 'border-border text-muted-foreground hover:bg-secondary',
                    )}
                  >
                    <span
                      aria-hidden
                      className="h-3.5 w-3.5 bg-accent"
                      style={item.css as React.CSSProperties}
                    />
                    {item.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          <p className="mt-2 text-sm font-medium">
            무대 배경 · {STAGE_BACKDROPS.length}종
            <span className="ml-1.5 text-xs font-normal text-muted-foreground">
              단색 말고도 건반 · 커튼 · 조명
            </span>
          </p>
          <div className="flex flex-wrap gap-1.5">
            {STAGE_BACKDROPS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setBackdrop(item.id)}
                aria-pressed={item.id === backdrop}
                title={item.hint}
                className={cn(
                  'rounded-full border px-2.5 py-1 text-xs transition-colors',
                  item.id === backdrop
                    ? 'border-accent bg-accent/10 font-medium text-foreground'
                    : 'border-border text-muted-foreground hover:bg-secondary',
                )}
              >
                {item.name}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">{stageBackdropInfo(backdrop).hint}</p>

          <p className="mt-1 text-sm font-medium">화면에 넣을 것</p>
          <div className="grid gap-1.5">
            <Toggle
              label="곡 해설"
              hint="연주자 화면 아래 한 줄"
              checked={options.show_commentary}
              onChange={(v) => setOptions((prev) => ({ ...prev, show_commentary: v }))}
            />
            <Toggle
              label="오늘의 순서"
              hint="전원의 번호 · 이름 · 곡"
              checked={options.show_agenda}
              onChange={(v) => setOptions((prev) => ({ ...prev, show_agenda: v }))}
            />
            <Toggle
              label="부 전환 화면"
              hint="첫 무대 · 한 뼘 더 · 마지막 무대"
              checked={options.show_sections}
              onChange={(v) => setOptions((prev) => ({ ...prev, show_sections: v }))}
            />
            <Toggle
              label="아이 사진"
              hint={photoCount > 0 ? `${photoCount}명 사진이 들어 있습니다` : '명단에서 사진을 먼저 넣으세요'}
              checked={options.show_photos}
              onChange={(v) => setOptions((prev) => ({ ...prev, show_photos: v }))}
            />
          </div>
          <div className="mt-1 flex flex-wrap gap-2">
            <a href={pptxUrl} download className={cn(buttonVariants({ size: 'sm' }))}>
              <Download className="mr-1 h-4 w-4" />
              파워포인트로 받기
            </a>
            <Button variant="outline" size="sm" onClick={() => window.print()}>
              <Printer className="mr-1 h-4 w-4" />
              PDF로 저장
            </Button>
          </div>
        </div>
      </div>

      <div className="no-print">
        <PrefsBar
          eventId={event.id}
          field="stage_prefs"
          label="무대 화면 설정"
          prefs={currentPrefs}
          saved={savedPrefs}
          past={pastPrefs}
          onLoad={applyPrefs}
        />
      </div>

      {/* 인쇄(=PDF 저장)용 — 화면에는 보이지 않고 종이에만 전부 깔린다 */}
      <div className="stage-print-deck" aria-hidden>
        {slides.map((item) => (
          <div key={item.id} className="stage-print-page">
            <StageSlideView
              slide={item}
              theme={theme}
              academyName={academyName}
              dark={false}
              logoUrl={logoUrl}
              layout={layout}
              shape={shape}
              backdrop={backdrop}
            />
          </div>
        ))}
      </div>
    </div>
  )
}

function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string
  hint: string
  checked: boolean
  onChange: (value: boolean) => void
}) {
  return (
    <label
      className={cn(
        'flex cursor-pointer items-center gap-2 rounded-md border px-2.5 py-1.5 text-sm transition-colors',
        checked ? 'border-accent bg-accent/8' : 'border-border',
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(pressed) => onChange(pressed.target.checked)}
        className="h-4 w-4 accent-current"
      />
      <span className="min-w-0">
        {label}
        <span className="ml-1.5 text-xs text-muted-foreground">{hint}</span>
      </span>
    </label>
  )
}

/**
 * 모양 고르는 자리에 뜨는 작은 그림.
 *
 * 실제 슬라이드를 열네 개 그리면 화면이 무거워지고, 무엇보다 아이 사진이 없으면
 * 다 똑같아 보인다. **어디에 사진이 오고 어디에 글이 오는지**만 네모로 보여 주면
 * 고르는 데는 그것으로 충분하다.
 */
function LayoutThumb({
  sketch,
  active,
  face,
}: {
  sketch: LayoutSketch
  active: boolean
  /** 실제로 넣어 두신 아이 사진 한 장. 없으면 회색 네모로 둔다 */
  face?: string | null
}) {
  const pct = (box: { x: number; y: number; w: number; h: number }) => ({
    left: `${box.x * 100}%`,
    top: `${box.y * 100}%`,
    width: `${box.w * 100}%`,
    height: `${box.h * 100}%`,
  })

  return (
    <span
      className={cn(
        'relative block w-full overflow-hidden rounded border',
        active ? 'border-accent/50 bg-background' : 'border-border bg-muted/50',
      )}
      style={{ aspectRatio: '16 / 9' }}
      aria-hidden
    >
      {sketch.photo &&
        (face ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={face}
            alt=""
            className="absolute rounded-[2px] object-cover"
            style={pct(sketch.photo)}
          />
        ) : (
          <span className="absolute rounded-[2px] bg-foreground/25" style={pct(sketch.photo)} />
        ))}
      <span
        className={cn('absolute rounded-[2px]', active ? 'bg-accent' : 'bg-foreground/55')}
        style={pct(sketch.text)}
      />
    </span>
  )
}
