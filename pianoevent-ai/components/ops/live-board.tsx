'use client'

import { ChevronLeft, ChevronRight, Play, RotateCcw } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { formatWallClock } from '@/lib/format'
import {
  buildLiveList,
  driftLabel,
  driftLevel,
  EMPTY_LIVE_STATE,
  formatElapsed,
  liveStorageKey,
  parseLiveState,
  type LiveState,
} from '@/lib/ops/live'
import type { EventRecord, ProgramPlan } from '@/lib/types'
import { cn } from '@/lib/utils'

/**
 * 당일 진행 화면.
 *
 * 무대 옆에 선 사람이 휴대폰으로 본다. 손에 들고 한 손으로 넘긴다.
 * 그래서 글자가 크고, 누를 곳이 크고, 화면이 꺼지지 않는다.
 *
 * 인터넷과는 상관이 없다 — 계산은 전부 이 화면 안에서 한다.
 * 어디까지 진행했는지는 이 휴대폰에만 담긴다(새로고침해도 남는다).
 */
export function LiveBoard({ event, plan }: { event: EventRecord; plan: ProgramPlan }) {
  const list = useMemo(() => buildLiveList(plan), [plan])
  const [state, setState] = useState<LiveState>(EMPTY_LIVE_STATE)
  /** 지금 시각(ms) — 1초마다 다시 그린다 */
  const [now, setNow] = useState(0)
  const wakeRef = useRef<{ release: () => Promise<void> } | null>(null)

  // 담아 둔 진행 상태를 되읽는다. 서버에는 없는 값이라 화면이 붙은 뒤에 읽는다
  useEffect(() => {
    try {
      setState(parseLiveState(window.localStorage.getItem(liveStorageKey(event.id)), list.length))
    } catch {
      /* 저장이 막힌 브라우저라면 그냥 처음부터 쓴다 */
    }
  }, [event.id, list.length])

  const save = useCallback(
    (next: LiveState) => {
      setState(next)
      try {
        window.localStorage.setItem(liveStorageKey(event.id), JSON.stringify(next))
      } catch {
        /* 저장이 막혀도 진행은 계속돼야 한다 */
      }
    },
    [event.id],
  )

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    setNow(Date.now())
    return () => window.clearInterval(timer)
  }, [])

  /** 연주회 도중 화면이 꺼지면 곤란하다 — 브라우저가 허락하면 켜 둔다 */
  useEffect(() => {
    if (!state.started_at) return
    let cancelled = false
    const nav = navigator as Navigator & {
      wakeLock?: { request: (type: 'screen') => Promise<{ release: () => Promise<void> }> }
    }
    void nav.wakeLock
      ?.request('screen')
      .then((lock) => {
        if (cancelled) void lock.release()
        else wakeRef.current = lock
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
      void wakeRef.current?.release().catch(() => undefined)
      wakeRef.current = null
    }
  }, [state.started_at])

  const current = list[Math.min(state.index, Math.max(0, list.length - 1))] ?? null
  const next = list[state.index + 1] ?? null
  const after = list[state.index + 2] ?? null

  const elapsedSec = state.started_at && now ? Math.max(0, (now - state.started_at) / 1000) : 0
  const planned = current?.planned_offset_sec ?? 0
  const level = state.started_at ? driftLevel(elapsedSec, planned) : 'ok'

  if (list.length === 0) {
    return (
      <p className="rounded-lg border border-border px-4 py-10 text-center text-sm text-muted-foreground">
        순서표가 아직 없습니다. 순서표를 먼저 만들어 주세요.
      </p>
    )
  }

  return (
    <div className="grid gap-3" data-testid="live-board">
      {/* 지금 */}
      <section
        className={cn(
          'rounded-xl border p-5',
          level === 'late'
            ? 'border-destructive/50 bg-destructive/5'
            : level === 'warn'
              ? 'border-accent/60 bg-accent/8'
              : 'border-accent/40 bg-accent/5',
        )}
      >
        <p className="text-xs font-medium tracking-widest text-accent">지금</p>
        <p className="mt-1 flex flex-wrap items-baseline gap-2">
          {current?.order_no ? (
            <span className="text-3xl font-bold tabular-nums text-accent">{current.order_no}</span>
          ) : null}
          <span className="text-3xl font-bold leading-tight" data-testid="live-now">
            {current?.title ?? '—'}
          </span>
        </p>
        {current?.detail && <p className="mt-1 text-base text-muted-foreground">{current.detail}</p>}
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          <span className="tabular-nums">예정 {formatWallClock(event.event_at, planned)}</span>
          {state.started_at ? (
            <>
              <span className="tabular-nums text-muted-foreground">경과 {formatElapsed(elapsedSec)}</span>
              <span
                className={cn(
                  'font-medium tabular-nums',
                  level === 'late' ? 'text-destructive' : level === 'warn' ? 'text-accent' : 'text-muted-foreground',
                )}
                data-testid="live-drift"
              >
                {driftLabel(elapsedSec, planned)}
              </span>
            </>
          ) : (
            <span className="text-muted-foreground">아직 시작 전입니다</span>
          )}
        </div>
      </section>

      {/* 다음 · 그다음 */}
      <section className="grid gap-2 sm:grid-cols-2">
        <div className="rounded-lg border border-border p-4">
          <p className="text-xs font-medium tracking-widest text-muted-foreground">다음</p>
          <p className="mt-1 text-xl font-semibold" data-testid="live-next">
            {next ? `${next.order_no ? `${next.order_no}. ` : ''}${next.title}` : '없음 (마지막)'}
          </p>
          {next?.detail && <p className="mt-0.5 text-sm text-muted-foreground">{next.detail}</p>}
          {next && (
            <p className="mt-1 text-xs text-muted-foreground">
              대기실에서 <strong className="text-foreground">{next.title}</strong> 을(를) 무대 옆으로
            </p>
          )}
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-xs font-medium tracking-widest text-muted-foreground">그다음</p>
          <p className="mt-1 text-xl font-semibold">
            {after ? `${after.order_no ? `${after.order_no}. ` : ''}${after.title}` : '없음'}
          </p>
          {after?.detail && <p className="mt-0.5 text-sm text-muted-foreground">{after.detail}</p>}
        </div>
      </section>

      {/* 넘기기 — 한 손으로 누를 수 있는 크기 */}
      <div className="grid grid-cols-[auto_1fr_auto] gap-2">
        <Button
          variant="outline"
          className="h-14 px-5"
          onClick={() => save({ ...state, index: Math.max(0, state.index - 1) })}
          disabled={state.index === 0}
          aria-label="이전 순서"
        >
          <ChevronLeft className="h-6 w-6" />
        </Button>
        {state.started_at ? (
          <Button
            className="h-14 text-base"
            onClick={() => save({ ...state, index: Math.min(list.length - 1, state.index + 1) })}
            disabled={state.index >= list.length - 1}
          >
            다음 순서로
            <ChevronRight className="ml-1 h-6 w-6" />
          </Button>
        ) : (
          <Button className="h-14 text-base" onClick={() => save({ index: 0, started_at: Date.now() })}>
            <Play className="mr-1 h-5 w-5" />
            개회 · 시작
          </Button>
        )}
        <Button
          variant="outline"
          className="h-14 px-4"
          onClick={() => {
            if (window.confirm('진행 상태를 처음으로 되돌립니다. 계속할까요?')) save(EMPTY_LIVE_STATE)
          }}
          aria-label="처음으로 되돌리기"
        >
          <RotateCcw className="h-5 w-5" />
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">
        진행 상태는 <strong>이 휴대폰에만</strong> 담깁니다. 새로고침해도 그대로이고, 인터넷이 끊겨도 넘어갑니다.
        여러 사람이 함께 보시려면 각자 이 화면을 열고 각자 넘기시면 됩니다.
      </p>

      {/* 전체 순서 — 눌러서 건너뛰기 */}
      <section className="rounded-lg border border-border">
        <p className="border-b border-border px-4 py-2 text-sm font-medium">
          전체 순서 {list.length}개
          <span className="ml-1.5 text-xs font-normal text-muted-foreground">누르면 그 자리로 옮깁니다</span>
        </p>
        <ol className="max-h-[420px] overflow-y-auto">
          {list.map((entry, index) => (
            <li key={entry.id}>
              <button
                type="button"
                onClick={() => save({ ...state, index })}
                className={cn(
                  'flex w-full items-baseline gap-3 border-b border-border/60 px-4 py-3 text-left last:border-0',
                  index === state.index
                    ? 'bg-accent/10 font-medium'
                    : index < state.index
                      ? 'text-muted-foreground line-through decoration-border'
                      : 'hover:bg-secondary',
                )}
              >
                <span className="w-7 shrink-0 text-sm tabular-nums text-muted-foreground">
                  {entry.order_no ?? '휴'}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{entry.title}</span>
                  {entry.detail && <span className="block truncate text-xs text-muted-foreground">{entry.detail}</span>}
                </span>
                <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                  {formatWallClock(event.event_at, entry.planned_offset_sec)}
                </span>
              </button>
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}
