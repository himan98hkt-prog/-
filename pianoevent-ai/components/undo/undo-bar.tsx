'use client'

import { RotateCcw } from 'lucide-react'
import { usePathname, useRouter } from 'next/navigation'
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { UNDO_KEY, keepable, popUndo, pushUndo, undoLine, usable, type UndoAction } from '@/lib/undo/stack'

/**
 * 되돌리기 한 자리.
 *
 * 화면마다 되돌리기가 따로 있으면 그 자리마다 새로 배우셔야 한다. 하나로 모은다.
 * 무엇을 하시든 화면 위 같은 자리에 "방금 하신 것" 이 뜨고, 단추도 하나뿐이다.
 *
 * 화면을 옮기시면 쌓인 것을 비운다 — 명단 화면에서 하신 일을 인쇄물 화면에서
 * 되돌릴 수 있으면 그게 더 무섭다.
 */
interface UndoBox {
  remember: (action: UndoAction) => void
  /** 되돌릴 수 없게 된 것을 치운다 (예: 그 학생을 지우셨을 때) */
  forget: (id: string) => void
}

const Ctx = createContext<UndoBox>({ remember: () => {}, forget: () => {} })

export function useUndo(): UndoBox {
  return useContext(Ctx)
}

export function UndoProvider({ children, eventId }: { children: React.ReactNode; eventId?: string }) {
  const [stack, setStack] = useState<UndoAction[]>([])
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<string | null>(null)
  const path = usePathname()
  const router = useRouter()

  /**
   * 화면을 옮겨도 되돌릴 것이 살아남는다.
   *
   * 원장님은 명단을 고치고 인쇄물을 보러 가셨다가 "아까 그거 잘못 고쳤는데" 하고
   * 돌아오신다. 그때 되돌릴 수 있어야 한다.
   *
   * 함수는 화면을 옮기면 사라지므로, **요청으로 적어 둔 것**만 브라우저에 남긴다.
   * 남는 곳은 이 브라우저 안(sessionStorage)이고, 창을 닫으면 함께 사라진다.
   */
  useEffect(() => {
    try {
      const raw = window.sessionStorage.getItem(UNDO_KEY)
      const saved: UndoAction[] = raw ? JSON.parse(raw) : []
      setStack(usable(Array.isArray(saved) ? saved : [], eventId ?? ''))
    } catch {
      /* 못 읽어도 이번 화면에서 하신 것은 그대로 쌓인다 */
    }
    setDone(null)
    // 행사가 바뀌면 다시 읽는다. 화면만 옮긴 것으로는 지우지 않는다.
  }, [eventId])

  useEffect(() => {
    setDone(null)
  }, [path])

  function keep(next: UndoAction[]) {
    setStack(next)
    try {
      window.sessionStorage.setItem(UNDO_KEY, JSON.stringify(keepable(next)))
    } catch {
      /* 못 적어도 이 화면에서는 되돌릴 수 있다 */
    }
  }

  const remember = useCallback(
    (action: UndoAction) => {
      setDone(null)
      setStack((prev) => {
        const next = pushUndo(prev, { ...action, eventId: action.eventId ?? eventId, at: Date.now() })
        try {
          window.sessionStorage.setItem(UNDO_KEY, JSON.stringify(keepable(next)))
        } catch {
          /* 위와 같다 */
        }
        return next
      })
    },
    [eventId],
  )

  const forget = useCallback((id: string) => {
    setStack((prev) => {
      const next = prev.filter((a) => a.id !== id)
      try {
        window.sessionStorage.setItem(UNDO_KEY, JSON.stringify(keepable(next)))
      } catch {
        /* 위와 같다 */
      }
      return next
    })
  }, [])

  const box = useMemo(() => ({ remember, forget }), [remember, forget])
  const top = stack[0] ?? null

  async function undo() {
    const { action, rest } = popUndo(stack)
    if (!action) return
    setBusy(true)
    try {
      if (action.run) {
        // 이 화면에서 하신 것 — 그 화면이 아는 방법으로 되돌린다
        await action.run()
      } else if (action.request) {
        // 화면을 옮긴 뒤 — 적어 둔 요청을 그대로 다시 보낸다
        const res = await fetch(action.request.url, {
          method: action.request.method,
          headers: { 'Content-Type': 'application/json' },
          body: action.request.body === undefined ? undefined : JSON.stringify(action.request.body),
        })
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error ?? '되돌리지 못했습니다.')
      } else {
        throw new Error('되돌리는 방법을 잃었습니다.')
      }
      keep(rest)
      setDone(`${action.what} 을(를) 되돌렸습니다.`)
      router.refresh()
    } catch (error) {
      setDone(error instanceof Error ? error.message : '되돌리지 못했습니다.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Ctx.Provider value={box}>
      {(top || done) && (
        <div className="sticky top-14 z-10 -mt-2 mb-4 no-print" data-testid="undo-bar">
          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-accent/40 bg-accent/5 px-3 py-2 shadow-sm backdrop-blur">
            {top ? (
              <>
                <p className="mr-auto text-sm">
                  방금 하신 것 — <strong>{undoLine(top)}</strong>
                </p>
                <Button variant="outline" size="sm" onClick={undo} disabled={busy} data-testid="undo-now">
                  <RotateCcw className="h-4 w-4" aria-hidden />
                  되돌리기
                  {stack.length > 1 && (
                    <span className="ml-1 text-xs text-muted-foreground">{stack.length}</span>
                  )}
                </Button>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">{done}</p>
            )}
          </div>
        </div>
      )}
      {children}
    </Ctx.Provider>
  )
}
