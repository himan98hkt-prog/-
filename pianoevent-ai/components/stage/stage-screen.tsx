'use client'

import { ChevronLeft, ChevronRight, Maximize2, Moon, Printer, Sun } from 'lucide-react'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { StageSlideView } from '@/components/stage/slide'
import { Button } from '@/components/ui/button'
import type { DesignTheme } from '@/lib/design/themes'
import { STAGE_SLIDE_H, STAGE_SLIDE_W, type StageSlide } from '@/lib/stage/deck'

/**
 * 연주회 당일 스크린.
 *
 * 노트북을 빔프로젝터에 연결하고 [전체화면] 을 누르면 끝이다.
 * 넘기기는 화살표·스페이스·클릭 — 리모컨(프레젠터)도 화살표 키를 보내므로 그대로 쓸 수 있다.
 * 인터넷이 끊겨도 동작한다. 이미 받아 온 화면이고, 서버에 다시 묻지 않는다.
 */
export function StageScreen({
  slides,
  theme,
  academyName,
  logoUrl,
}: {
  slides: StageSlide[]
  theme: DesignTheme
  academyName: string
  logoUrl: string | null
}) {
  const [index, setIndex] = useState(0)
  const [dark, setDark] = useState(true)
  const [full, setFull] = useState(false)
  const shellRef = useRef<HTMLDivElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)

  const last = slides.length - 1
  const go = useCallback((next: number) => setIndex(Math.min(last, Math.max(0, next))), [last])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'ArrowRight' || event.key === 'PageDown' || event.key === ' ' || event.key === 'Enter') {
        event.preventDefault()
        setIndex((prev) => Math.min(last, prev + 1))
      } else if (event.key === 'ArrowLeft' || event.key === 'PageUp' || event.key === 'Backspace') {
        event.preventDefault()
        setIndex((prev) => Math.max(0, prev - 1))
      } else if (event.key === 'Home') {
        setIndex(0)
      } else if (event.key === 'End') {
        setIndex(last)
      } else if (event.key === 'f' || event.key === 'F') {
        void toggleFull()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [last])

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

  async function toggleFull() {
    const shell = shellRef.current
    if (!shell) return
    try {
      if (document.fullscreenElement) await document.exitFullscreen()
      else await shell.requestFullscreen()
    } catch {
      /* 브라우저가 막으면 그냥 창 모드로 쓴다 */
    }
  }

  const slide = slides[index]

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
          onKeyDown={(event) => {
            if (event.key === 'Enter') setIndex((prev) => Math.min(last, prev + 1))
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
            <StageSlideView slide={slide} theme={theme} academyName={academyName} dark={dark} logoUrl={logoUrl} />
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
        <Button size="sm" onClick={() => go(index + 1)} disabled={index === last}>
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
          <Button variant="outline" size="sm" onClick={() => window.print()}>
            <Printer className="mr-1 h-4 w-4" />
            PDF로 저장
          </Button>
        </div>
      </div>

      <p className="no-print text-sm text-muted-foreground" data-testid="stage-next">
        다음 화면 — <strong className="text-foreground">{slide.next || '없음 (마지막)'}</strong>
        {slide.at ? ` · 예정 ${slide.at}` : ''}
      </p>

      {/* 인쇄(=PDF 저장)용 — 화면에는 보이지 않고 종이에만 전부 깔린다 */}
      <div className="stage-print-deck" aria-hidden>
        {slides.map((item) => (
          <div key={item.id} className="stage-print-page">
            <StageSlideView slide={item} theme={theme} academyName={academyName} dark={false} logoUrl={logoUrl} />
          </div>
        ))}
      </div>
    </div>
  )
}
