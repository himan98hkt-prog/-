'use client'

import { Type } from 'lucide-react'
import { useEffect, useState } from 'react'
import { TEXT_SIZE_KEY, getTextSize, nextTextSize, rootFontPx, type TextSize } from '@/lib/text-size'

/**
 * 글씨 크기 단추.
 *
 * 고르는 창을 띄우지 않는다. **누를 때마다 한 단계씩** 커지고, 끝에서 누르면
 * 처음으로 돌아온다. 단추 하나에 지금 크기가 적혀 있어 무엇이 될지 미리 아신다.
 *
 * 고른 크기는 이 브라우저에 남는다 — 다음에 여실 때 그 크기로 열린다.
 */
export function TextSizeToggle() {
  const [size, setSize] = useState<TextSize>('normal')
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let saved: TextSize = 'normal'
    try {
      saved = getTextSize(window.localStorage.getItem(TEXT_SIZE_KEY)).id
    } catch {
      /* 저장을 못 읽는 브라우저 — 보통 크기로 연다 */
    }
    setSize(saved)
    setReady(true)
  }, [])

  useEffect(() => {
    if (!ready) return
    document.documentElement.style.fontSize = `${rootFontPx(size)}px`
    try {
      window.localStorage.setItem(TEXT_SIZE_KEY, size)
    } catch {
      /* 못 적어도 이번 화면에서는 커진 채로 쓰신다 */
    }
  }, [size, ready])

  return (
    <button
      type="button"
      onClick={() => setSize(nextTextSize(size))}
      className="flex items-center gap-1 rounded-md px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
      title="글씨 크기를 바꿉니다"
      data-testid="text-size"
      data-size={size}
    >
      <Type className="h-4 w-4" aria-hidden />
      <span className="hidden sm:inline">글씨 {getTextSize(size).label}</span>
      <span className="sm:hidden">가</span>
    </button>
  )
}
