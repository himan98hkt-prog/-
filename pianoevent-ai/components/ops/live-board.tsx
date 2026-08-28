'use client'

import { Check, ChevronLeft, ChevronRight, Loader2, Play, RadioTower, RotateCcw, Users } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { formatDuration, formatWallClock } from '@/lib/format'
import {
  actualRows,
  buildLiveList,
  driftLabel,
  driftLevel,
  durationUpdates,
  elapsedAtIndex,
  elapsedTotal,
  EMPTY_LIVE_STATE,
  formatElapsed,
  liveStorageKey,
  moveLive,
  namedDurations,
  newerLiveState,
  normalizeLiveState,
  parseLiveState,
  progressLabel,
  startLive,
  type LiveState,
} from '@/lib/ops/live'
import type { EventRecord, EventStudent, ProgramPlan } from '@/lib/types'
import { cn } from '@/lib/utils'

/** 함께 보기에서 몇 초마다 서버를 들여다볼지 */
const FOLLOW_POLL_MS = 3000

/**
 * 당일 진행 화면.
 *
 * 무대 옆에 선 사람이 휴대폰으로 본다. 손에 들고 한 손으로 넘긴다.
 * 그래서 글자가 크고, 누를 곳이 크고, 화면이 꺼지지 않는다.
 *
 * **함께 보기**를 켜면 한 사람이 넘길 때 나머지 화면도 따라 넘어간다.
 * 그 통신이 끊겨도 각자 화면은 그대로 돈다 — 당일에 서버 때문에 순서를
 * 놓치는 일은 없어야 한다.
 */
export function LiveBoard({
  event,
  plan,
  students = [],
  initialState = null,
  canLead = true,
}: {
  event: EventRecord
  plan: ProgramPlan
  /** 실제 시간을 명단에 되돌릴 때 쓴다 */
  students?: EventStudent[]
  /** 서버에 올라와 있던 진행 상태 */
  initialState?: LiveState | null
  /** 넘길 수 있는 화면인가 (학부모용 따라보기 화면은 false) */
  canLead?: boolean
}) {
  const list = useMemo(() => buildLiveList(plan), [plan])
  const [state, setState] = useState<LiveState>(() => normalizeLiveState(initialState, list.length))
  /** 지금 시각(ms) — 1초마다 다시 그린다 */
  const [now, setNow] = useState(0)
  /** 함께 보기 — 켜면 넘긴 것을 서버에 올리고, 남이 넘긴 것을 받아 온다 */
  const [shared, setShared] = useState(canLead ? false : true)
  const [sharedError, setSharedError] = useState<string | null>(null)
  const [applying, setApplying] = useState(false)
  const [applied, setApplied] = useState<number | null>(null)
  const wakeRef = useRef<{ release: () => Promise<void> } | null>(null)
  const stateRef = useRef(state)
  stateRef.current = state

  // 담아 둔 진행 상태를 되읽는다. 서버에는 없는 값이라 화면이 붙은 뒤에 읽는다
  useEffect(() => {
    if (!canLead) return
    try {
      const mine = parseLiveState(window.localStorage.getItem(liveStorageKey(event.id)), list.length)
      // 서버 것이 더 나중이면 그쪽을 따른다 (다른 스태프가 이미 시작해 두었을 수 있다)
      setState((prev) => newerLiveState(mine, prev))
    } catch {
      /* 저장이 막힌 브라우저라면 그냥 처음부터 쓴다 */
    }
  }, [event.id, list.length, canLead])

  /** 서버에 올린다. 실패해도 화면은 그대로 — 인터넷은 있으면 좋은 것이지 있어야 하는 것이 아니다 */
  const push = useCallback(
    async (next: LiveState) => {
      try {
        const res = await fetch(`/api/events/${event.id}/live`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ live: next }),
        })
        if (!res.ok) throw new Error('보내지 못했습니다.')
        setSharedError(null)
      } catch {
        setSharedError('함께 보기 연결이 끊겼습니다. 이 화면은 그대로 넘어갑니다.')
      }
    },
    [event.id],
  )

  const save = useCallback(
    (next: LiveState) => {
      setState(next)
      try {
        window.localStorage.setItem(liveStorageKey(event.id), JSON.stringify(next))
      } catch {
        /* 저장이 막혀도 진행은 계속돼야 한다 */
      }
      if (shared) void push(next)
    },
    [event.id, shared, push],
  )

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    setNow(Date.now())
    return () => window.clearInterval(timer)
  }, [])

  /** 함께 보기 — 남이 넘긴 것을 받아 온다 */
  useEffect(() => {
    if (!shared) return
    let alive = true
    const pull = async () => {
      try {
        const res = await fetch(`/api/events/${event.id}/live`, { cache: 'no-store' })
        if (!res.ok) throw new Error('읽지 못했습니다.')
        const body = await res.json()
        if (!alive) return
        const theirs = normalizeLiveState(body.live, list.length)
        setSharedError(null)
        setState((prev) => {
          const next = newerLiveState(prev, theirs)
          if (next === prev) return prev
          try {
            window.localStorage.setItem(liveStorageKey(event.id), JSON.stringify(next))
          } catch {
            /* 담아 두지 못해도 화면은 따라간다 */
          }
          return next
        })
      } catch {
        if (alive) setSharedError('함께 보기 연결이 끊겼습니다. 이 화면은 그대로 넘어갑니다.')
      }
    }
    void pull()
    const timer = window.setInterval(pull, FOLLOW_POLL_MS)
    return () => {
      alive = false
      window.clearInterval(timer)
    }
  }, [shared, event.id, list.length])

  /** 함께 보기를 켠 순간, 내 화면이 더 나중이면 서버에 한 번 올려 둔다 */
  useEffect(() => {
    if (!shared || !canLead) return
    if (stateRef.current.updated_at > 0) void push(stateRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shared])

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

  const elapsedSec = state.started_at && now ? elapsedTotal(state, now) : 0
  const onStageSec = state.started_at && now ? elapsedAtIndex(state, state.index, now) : 0
  const planned = current?.planned_offset_sec ?? 0
  const level = state.started_at ? driftLevel(elapsedSec, planned) : 'ok'

  const rows = useMemo(() => actualRows(list, state), [list, state])
  const suggestions = useMemo(() => namedDurations(rows, students), [rows, students])

  async function applyDurations() {
    setApplying(true)
    try {
      const res = await fetch(`/api/events/${event.id}/durations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates: durationUpdates(rows) }),
      })
      const body = await res.json()
      if (!res.ok) throw new Error(body.error ?? '반영하지 못했습니다.')
      setApplied(body.updated ?? 0)
    } catch {
      setApplied(-1)
    } finally {
      setApplying(false)
    }
  }

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
              <span className="tabular-nums text-muted-foreground" data-testid="live-stage-clock">
                이 순서 {formatElapsed(onStageSec)}
              </span>
              <span className="tabular-nums text-muted-foreground">전체 {formatElapsed(elapsedSec)}</span>
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
      {canLead && (
        <div className="grid grid-cols-[auto_1fr_auto] gap-2">
          <Button
            variant="outline"
            className="h-14 px-5"
            onClick={() => save(moveLive(state, state.index - 1, Date.now(), list.length))}
            disabled={state.index === 0}
            aria-label="이전 순서"
          >
            <ChevronLeft className="h-6 w-6" />
          </Button>
          {state.started_at ? (
            <Button
              className="h-14 text-base"
              onClick={() => save(moveLive(state, state.index + 1, Date.now(), list.length))}
              disabled={state.index >= list.length - 1}
            >
              다음 순서로
              <ChevronRight className="ml-1 h-6 w-6" />
            </Button>
          ) : (
            <Button className="h-14 text-base" onClick={() => save(startLive(Date.now()))}>
              <Play className="mr-1 h-5 w-5" />
              개회 · 시작
            </Button>
          )}
          <Button
            variant="outline"
            className="h-14 px-4"
            onClick={() => {
              if (window.confirm('진행 상태를 처음으로 되돌립니다. 계속할까요?')) {
                save({ ...EMPTY_LIVE_STATE, updated_at: Date.now() })
              }
            }}
            aria-label="처음으로 되돌리기"
          >
            <RotateCcw className="h-5 w-5" />
          </Button>
        </div>
      )}

      {/* 함께 보기 */}
      {canLead && (
        <section className="rounded-lg border border-border p-3" data-testid="live-share">
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={shared}
              onChange={(native) => setShared(native.target.checked)}
              className="h-4 w-4"
            />
            <RadioTower className="h-4 w-4 text-accent" aria-hidden />
            <span>
              <strong>함께 보기</strong>
              <span className="ml-1.5 text-xs text-muted-foreground">
                한 사람이 넘기면 나머지 화면도 따라 넘어갑니다
              </span>
            </span>
          </label>
          {shared && (
            <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Users className="h-3.5 w-3.5" aria-hidden />
              대기실·접수처 스태프는 이 주소를 열어 두시면 됩니다 —{' '}
              <code className="rounded bg-secondary px-1.5 py-0.5">/e/{event.id}/live</code>
              <span>로그인 없이 보기만 하는 화면입니다.</span>
            </p>
          )}
          {sharedError && <p className="mt-1 text-xs text-destructive">{sharedError}</p>}
        </section>
      )}

      <p className="text-xs text-muted-foreground">
        {canLead ? (
          <>
            진행 상태는 <strong>이 휴대폰에</strong> 담깁니다. 새로고침해도 그대로이고, 인터넷이 끊겨도 넘어갑니다.
            함께 보기를 켜면 같은 상태를 다른 화면과 나눕니다.
          </>
        ) : (
          <>보기만 하는 화면입니다. 무대 옆에서 넘기면 몇 초 안에 따라 바뀝니다.</>
        )}
      </p>

      {/* 실제로 걸린 시간 — 다음 해 순서표가 이 학원 아이들에 맞게 된다 */}
      {canLead && rows.length > 0 && (
        <section className="grid gap-2 rounded-lg border border-border p-3" data-testid="live-actuals">
          <p className="text-sm font-medium">
            실제로 걸린 시간
            <span className="ml-1.5 text-xs font-normal text-muted-foreground">{progressLabel(list, state)}</span>
          </p>
          <ul className="grid max-h-56 gap-1 overflow-y-auto text-xs">
            {rows.map((row) => (
              <li key={row.entry.id} className="flex items-baseline gap-2">
                <span className="w-6 shrink-0 tabular-nums text-muted-foreground">{row.entry.order_no ?? '휴'}</span>
                <span className="min-w-0 flex-1 truncate">{row.entry.title}</span>
                <span className="shrink-0 tabular-nums text-muted-foreground">
                  예정 {formatDuration(row.planned_sec)}
                </span>
                <span
                  className={cn(
                    'shrink-0 tabular-nums font-medium',
                    row.actual_sec > row.planned_sec + 10 ? 'text-destructive' : 'text-foreground',
                  )}
                >
                  실제 {formatDuration(row.actual_sec)}
                </span>
              </li>
            ))}
          </ul>
          {suggestions.length > 0 && (
            <div className="grid gap-1.5 border-t border-border pt-2">
              <p className="text-xs text-muted-foreground">
                <strong className="text-foreground">{suggestions.length}명</strong>의 연주 시간이 명단과 다릅니다.
                실제 시간으로 바꿔 두면 <strong>다음 연주회 종료 시각</strong>이 이 학원 아이들에 맞게 계산됩니다.
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" variant="outline" onClick={() => void applyDurations()} disabled={applying}>
                  {applying ? (
                    <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                  ) : applied !== null && applied >= 0 ? (
                    <Check className="mr-1 h-4 w-4 text-accent" />
                  ) : null}
                  실제 시간을 명단에 반영
                </Button>
                {applied !== null && (
                  <span className="text-xs text-muted-foreground">
                    {applied >= 0 ? `${applied}명 반영했습니다.` : '반영하지 못했습니다.'}
                  </span>
                )}
              </div>
            </div>
          )}
        </section>
      )}

      {/* 전체 순서 — 눌러서 건너뛰기 */}
      <section className="rounded-lg border border-border">
        <p className="border-b border-border px-4 py-2 text-sm font-medium">
          전체 순서 {list.length}개
          {canLead && (
            <span className="ml-1.5 text-xs font-normal text-muted-foreground">누르면 그 자리로 옮깁니다</span>
          )}
        </p>
        <ol className="max-h-[420px] overflow-y-auto">
          {list.map((entry, index) => (
            <li key={entry.id}>
              <button
                type="button"
                onClick={() => canLead && save(moveLive(state, index, Date.now(), list.length))}
                disabled={!canLead}
                className={cn(
                  'flex w-full items-baseline gap-3 border-b border-border/60 px-4 py-3 text-left last:border-0',
                  index === state.index
                    ? 'bg-accent/10 font-medium'
                    : index < state.index
                      ? 'text-muted-foreground line-through decoration-border'
                      : canLead
                        ? 'hover:bg-secondary'
                        : '',
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
