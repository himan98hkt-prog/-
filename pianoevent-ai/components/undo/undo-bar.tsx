'use client'

import { RotateCcw } from 'lucide-react'
import { usePathname } from 'next/navigation'
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { popUndo, pushUndo, undoLine, type UndoAction } from '@/lib/undo/stack'

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

export function UndoProvider({ children }: { children: React.ReactNode }) {
  const [stack, setStack] = useState<UndoAction[]>([])
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<string | null>(null)
  const path = usePathname()

  // 화면을 옮기시면 비운다
  useEffect(() => {
    setStack([])
    setDone(null)
  }, [path])

  const remember = useCallback((action: UndoAction) => {
    setDone(null)
    setStack((prev) => pushUndo(prev, action))
  }, [])

  const forget = useCallback((id: string) => {
    setStack((prev) => prev.filter((a) => a.id !== id))
  }, [])

  const box = useMemo(() => ({ remember, forget }), [remember, forget])
  const top = stack[0] ?? null

  async function undo() {
    const { action, rest } = popUndo(stack)
    if (!action) return
    setBusy(true)
    try {
      await action.run()
      setStack(rest)
      setDone(`${action.what} 을(를) 되돌렸습니다.`)
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
