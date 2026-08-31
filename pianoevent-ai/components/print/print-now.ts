'use client'

import { FIRST_ONLY_CLASS } from '@/lib/print/paper'

/**
 * 인쇄 창을 연다.
 *
 * `firstOnly` 면 첫 장만 나오게 표시를 붙였다가 뗀다 — 인쇄 설정을 맞게 하셨는지는
 * 결국 한 장 뽑아 봐야 아신다. 종이 한 장이 100장을 살린다.
 *
 * 표시를 떼는 일은 반드시 해야 한다. 남아 있으면 그다음 인쇄가 통째로 첫 장만 나온다.
 * afterprint 를 주지 않는 브라우저가 있어 시간을 재는 쪽도 함께 건다.
 */
export function printNow(firstOnly = false) {
  const root = document.documentElement
  if (!firstOnly) {
    window.print()
    return
  }

  root.classList.add(FIRST_ONLY_CLASS)
  let cleaned = false
  const clean = () => {
    if (cleaned) return
    cleaned = true
    root.classList.remove(FIRST_ONLY_CLASS)
  }
  window.addEventListener('afterprint', clean, { once: true })
  window.setTimeout(clean, 3000)
  window.print()
}
