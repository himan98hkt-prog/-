'use client'

import { useEffect } from 'react'

const ERROR_KEY = 'pianoevent.errors'
const KEEP = 10

/**
 * 화면에서 난 오류를 조용히 모아 둔다.
 *
 * 원장님은 오류 글을 받아 적지 못하신다. 창이 닫히면 사라지고, 사진 찍어 보내시면
 * 화면에 아이 이름이 함께 나온다. 그래서 이 브라우저 안(sessionStorage)에만 남긴다.
 * 창을 닫으면 함께 사라지고, 어디로도 저절로 보내지지 않는다 —
 * [막히면 여기] 에서 원장님이 보실 때 비로소 쪽지에 담긴다.
 */
export function ErrorLog() {
  useEffect(() => {
    function remember(line: string) {
      try {
        const raw = window.sessionStorage.getItem(ERROR_KEY)
        const list: string[] = raw ? JSON.parse(raw) : []
        list.unshift(`${new Date().toISOString().slice(11, 19)} ${line}`)
        window.sessionStorage.setItem(ERROR_KEY, JSON.stringify(list.slice(0, KEEP)))
      } catch {
        /* 저장이 막힌 브라우저 — 오류를 못 모을 뿐, 프로그램은 그대로 돈다 */
      }
    }

    const onError = (e: ErrorEvent) => remember(e.message || '알 수 없는 오류')
    const onRejection = (e: PromiseRejectionEvent) =>
      remember(e.reason instanceof Error ? e.reason.message : String(e.reason ?? '알 수 없는 오류'))

    window.addEventListener('error', onError)
    window.addEventListener('unhandledrejection', onRejection)
    return () => {
      window.removeEventListener('error', onError)
      window.removeEventListener('unhandledrejection', onRejection)
    }
  }, [])

  return null
}
