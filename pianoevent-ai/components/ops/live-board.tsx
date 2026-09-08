'use client'

import { Bell, BellOff, Check, ChevronLeft, ChevronRight, Copy, KeyRound, Loader2, Play, RadioTower, RotateCcw, Vibrate, Volume2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { formatDuration, formatWallClock } from '@/lib/format'
import {
  CHIME_LEAD_SEC,
  CHIME_SOUNDS,
  DEFAULT_CHIME_PREFS,
  chimeDue,
  chimeStorageKey,
  getChimeSound,
  parseChimePrefs,
  canSpeak,
  nextCallText,
  playChime,
  serializeChimePrefs,
  speak,
  vibrate,
  type ChimePrefs,
} from '@/lib/ops/chime'
import { paceAdvice } from '@/lib/ops/pace'
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
  photos = {},
  initialState = null,
  canLead = true,
  followCode = null,
}: {
  event: EventRecord
  plan: ProgramPlan
  /** 실제 시간을 명단에 되돌릴 때 쓴다 */
  students?: EventStudent[]
  /** 학생 id → 사진 — 대기실에서 아이를 잘못 짚지 않게 */
  photos?: Record<string, string>
  /** 서버에 올라와 있던 진행 상태 */
  initialState?: LiveState | null
  /** 넘길 수 있는 화면인가 (따라보기 화면은 false) */
  canLead?: boolean
  /** 따라보기 열쇠 — 서버에 물어볼 때 함께 보낸다 */
  followCode?: string | null
}) {
  const list = useMemo(() => buildLiveList(plan, photos), [plan, photos])
  const [state, setState] = useState<LiveState>(() => normalizeLiveState(initialState, list.length))
  /** 지금 시각(ms) — 1초마다 다시 그린다 */
  const [now, setNow] = useState(0)
  /** 함께 보기 — 켜면 넘긴 것을 서버에 올리고, 남이 넘긴 것을 받아 온다 */
  const [shared, setShared] = useState(canLead ? false : true)
  const [sharedError, setSharedError] = useState<string | null>(null)
  const [applying, setApplying] = useState(false)
  const [applied, setApplied] = useState<number | null>(null)
  /** 다음 차례 알림 — 소리와 진동. 이 휴대폰에만 담긴다 */
  const [chimePrefs, setChimePrefs] = useState<ChimePrefs>(DEFAULT_CHIME_PREFS)
  const chime = chimePrefs.on || chimePrefs.buzz || chimePrefs.speak
  const audioCtxRef = useRef<AudioContext | null>(null)
  /** 몇 번째 순서에서 이미 울렸는지 — 1초마다 다시 울리면 안 된다 */
  const chimedRef = useRef<number | null>(null)
  /** 이 브라우저가 말을 할 수 있는가 — 서버에서는 알 수 없어 화면이 붙은 뒤에 본다 */
  const [speakable, setSpeakable] = useState(false)
  /**
   * **대기실 모드.**
   *
   * 대기실 선생님이 보시는 화면은 무대 옆 화면과 필요한 것이 다르다.
   * 밀린 시간도, 사회자 멘트도 필요 없다 — **다음에 누구를 데려오나** 하나뿐이다.
   * 아이를 챙기면서 흘깃 보시는 자리라 글씨는 크고 그 밖의 것은 없어야 한다.
   */
  const [waiting, setWaiting] = useState(false)
  /** 방금 읽어 드린 이름 — 같은 이름을 두 번 읽지 않는다 */
  const spokenRef = useRef<string | null>(null)
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

  useEffect(() => {
    setSpeakable(canSpeak())
  }, [])

  // 알림을 어떻게 켜 두셨는지 되읽는다 (화면이 붙은 뒤에)
  useEffect(() => {
    try {
      setChimePrefs(parseChimePrefs(window.localStorage.getItem(chimeStorageKey(event.id))))
    } catch {
      /* 저장이 막힌 브라우저면 꺼진 채로 */
    }
  }, [event.id])

  /**
   * 알림 설정 바꾸기.
   *
   * 브라우저는 **원장님이 누르신 순간**에만 소리를 열어 준다. 그래서 켜시거나 소리를
   * 바꾸실 때 소리 통로를 만들어 두고, 그 자리에서 한 번 들려 드린다 —
   * "이런 소리가 납니다" 를 미리 아셔야 당일에 놀라지 않으신다.
   */
  function changeChime(patch: Partial<ChimePrefs>, taste = true) {
    const next = { ...chimePrefs, ...patch }
    setChimePrefs(next)
    try {
      window.localStorage.setItem(chimeStorageKey(event.id), serializeChimePrefs(next))
    } catch {
      /* 담아 두지 못해도 이번 연주회 동안은 켜져 있다 */
    }
    if (!taste) return
    if (next.on) {
      try {
        const Ctor =
          window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
        if (Ctor) {
          const ctx = audioCtxRef.current ?? new Ctor()
          audioCtxRef.current = ctx
          void ctx.resume().catch(() => undefined)
          playChime(ctx, next.soundId)
        }
      } catch {
        /* 소리를 못 내는 기계여도 화면은 그대로 돈다 */
      }
    }
    if (next.buzz) vibrate()
    if (next.speak) speak(nextCallText('김서연', 3))
  }

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
        const res = await fetch(
          `/api/events/${event.id}/live${followCode ? `?k=${encodeURIComponent(followCode)}` : ''}`,
          { cache: 'no-store' },
        )
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
  }, [shared, event.id, list.length, followCode])

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

  /**
   * 곧 다음 차례 — 소리로도, 글로도.
   *
   * 소리는 못 듣는 자리(객석 옆, 무음 모드)가 있으니 화면에도 함께 띄운다.
   * 판단은 `lib/ops/chime.ts` 가 하고, 여기서는 **한 순서에 한 번만** 울리게 지킨다.
   */
  const nextSoon = Boolean(
    state.started_at && next && current && chimeDue(onStageSec, current.planned_sec),
  )

  /**
   * **이 아이가 끝나기까지 남은 시간.**
   *
   * 무대 옆에서 가장 궁금한 숫자다. 지금까지는 "밀린 시간" 만 있었는데, 그건 연주회
   * 전체 이야기지 지금 이 순간의 이야기가 아니다. 다음 아이를 언제 데려올지는
   * 이 숫자로 정하신다. 넘겼으면 넘겼다고 그대로 적는다 — 0으로 멈추면 거짓말이 된다.
   */
  const leftSec = current && state.started_at ? Math.round(current.planned_sec - onStageSec) : null

  /**
   * 밀렸으면 **어쩌라는 말까지.**
   *
   * "12분 늦음" 은 원장님이 이미 아신다. 필요한 것은 무엇을 줄이면 되는가다.
   * 연주회에서 줄일 수 있는 것은 사실상 사회자 멘트뿐이므로 그 길이로 말씀드린다.
   */
  const pace = state.started_at ? paceAdvice(elapsedSec - planned, Math.max(0, list.length - 1 - state.index)) : null

  useEffect(() => {
    if (!chime || !nextSoon) return
    if (chimedRef.current === state.index) return
    chimedRef.current = state.index
    if (chimePrefs.buzz) vibrate()
    if (chimePrefs.on) {
      const ctx = audioCtxRef.current
      if (ctx) {
        try {
          void ctx.resume().catch(() => undefined)
          playChime(ctx, chimePrefs.soundId)
        } catch {
          /* 못 울려도 화면 표시는 남는다 */
        }
      }
    }
    // 소리는 "무슨 일이 났다" 만 알려 준다. 이름까지 들으시면 화면을 아예 안 보셔도 된다
    if (chimePrefs.speak && next) {
      // 종소리와 겹치지 않게 조금 뒤에 읽는다
      const said = nextCallText(next.title, next.order_no)
      window.setTimeout(() => speak(said), chimePrefs.on ? 800 : 0)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chime, nextSoon, state.index])

  // 순서를 되돌리시면 그 순서에서 다시 울려야 한다
  useEffect(() => {
    if (chimedRef.current !== null && chimedRef.current !== state.index) chimedRef.current = null
  }, [state.index])

  /**
   * 대기실 모드에서는 **다음 아이가 바뀌는 순간** 읽어 드린다.
   *
   * 무대 옆 화면은 "1분 전" 이 신호지만, 대기실에서는 "다음이 누구로 바뀌었나" 가 신호다.
   * 그때 아이를 찾아 무대 옆으로 데려가시기 시작해야 한다.
   */
  useEffect(() => {
    if (!waiting || !chimePrefs.speak || !next) return
    const say = nextCallText(next.title, next.order_no)
    if (spokenRef.current === say) return
    spokenRef.current = say
    speak(say)
    if (chimePrefs.buzz) vibrate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [waiting, chimePrefs.speak, next?.title, next?.order_no])

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

  /**
   * 대기실 화면 — 필요한 것 하나뿐이다.
   *
   * 밀린 시간도, 사회자 멘트도, 전체 순서도 없앤다. 대기실 선생님이 아이를 챙기면서
   * 흘깃 보시는 자리라, 있는 것이 적을수록 잘 보인다.
   */
  if (waiting) {
    return (
      <div className="grid gap-3" data-testid="waiting-room">
        <section className="rounded-xl border-2 border-accent bg-accent/10 p-5">
          <p className="text-sm font-medium tracking-widest text-accent">지금 데려오실 아이</p>
          <div className="mt-2 flex items-center gap-4">
            {next?.photo && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={next.photo}
                alt=""
                className="h-24 w-24 shrink-0 rounded-full border-2 border-accent object-cover"
                data-testid="waiting-photo"
              />
            )}
            <p className="min-w-0 text-4xl font-bold leading-tight" data-testid="waiting-next">
              {next ? `${next.order_no ? `${next.order_no}. ` : ''}${next.title}` : '없음 (마지막)'}
            </p>
          </div>
          {next?.detail && <p className="mt-2 text-lg text-muted-foreground">{next.detail}</p>}
        </section>

        <section className="rounded-lg border border-border p-4">
          <p className="text-xs font-medium tracking-widest text-muted-foreground">그다음 준비</p>
          <p className="mt-1 text-2xl font-semibold" data-testid="waiting-after">
            {after ? `${after.order_no ? `${after.order_no}. ` : ''}${after.title}` : '없음'}
          </p>
        </section>

        <p className="text-sm text-muted-foreground">
          지금 무대는 <strong className="text-foreground">{current?.title ?? '—'}</strong> 입니다.
        </p>

        <button
          type="button"
          onClick={() => setWaiting(false)}
          className="justify-self-start rounded-md border border-border px-3 py-1.5 text-sm hover:bg-secondary"
          data-testid="waiting-off"
        >
          보통 화면으로
        </button>

        {chimePrefs.speak ? (
          <p className="text-xs text-muted-foreground">
            다음 아이가 바뀌면 <strong>이름을 읽어 드립니다.</strong> 화면을 안 보고 계셔도 됩니다.
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">
            [보통 화면으로] 에서 <strong>이름까지 말로</strong> 를 켜 두시면, 다음 아이가 바뀔 때 이름을 읽어
            드립니다.
          </p>
        )}
      </div>
    )
  }

  return (
    /**
     * 당일 진행 화면은 **기본으로 한 단계 크게** 그린다.
     *
     * 무대 옆에서 휴대폰을 들고 보시는 화면이다. 객석은 어둡고 원장님은 급하시다.
     * 이 화면만은 머리띠에서 키우실 것을 기다리지 않고 처음부터 크게 둔다.
     * (머리띠에서 더 키우시면 그 위에 얹혀 더 커진다.)
     */
    <div className="grid gap-3 text-[1.12em]" data-testid="live-board">
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
        <div className="mt-1 flex items-start gap-3">
          {current?.photo && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={current.photo}
              alt=""
              className="h-16 w-16 shrink-0 rounded-full border border-accent/50 object-cover"
              data-testid="live-now-photo"
            />
          )}
          <div className="min-w-0">
            <p className="flex flex-wrap items-baseline gap-2">
              {current?.order_no ? (
                <span className="text-3xl font-bold tabular-nums text-accent">{current.order_no}</span>
              ) : null}
              <span className="text-3xl font-bold leading-tight" data-testid="live-now">
                {current?.title ?? '—'}
              </span>
            </p>
            {current?.detail && <p className="mt-1 text-base text-muted-foreground">{current.detail}</p>}
          </div>
        </div>
        {leftSec !== null && (
          <p
            className={cn(
              'mt-3 flex flex-wrap items-baseline gap-2 leading-none',
              leftSec < 0 ? 'text-destructive' : nextSoon ? 'text-accent' : '',
            )}
            data-testid="live-left"
          >
            <span className="text-4xl font-bold tabular-nums">{formatElapsed(Math.abs(leftSec))}</span>
            <span className="text-base font-medium">
              {leftSec < 0 ? '넘겼습니다' : '남았습니다'}
              <span className="ml-1.5 text-sm font-normal text-muted-foreground">
                {leftSec < 0 ? '이 아이 예정 시간을' : '이 아이 연주가 끝나기까지'}
              </span>
            </span>
          </p>
        )}

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

      {/* 밀렸으면 무엇을 줄이면 되는지 — 늦었다는 사실만으로는 하실 일이 없다 */}
      {pace && (
        <section
          className={cn(
            'rounded-lg border px-4 py-3',
            pace.level === 'late'
              ? 'border-destructive/50 bg-destructive/5'
              : pace.level === 'warn'
                ? 'border-accent/60 bg-accent/8'
                : 'border-border',
          )}
          data-testid="live-pace"
          data-level={pace.level}
        >
          <p className="text-xs font-medium tracking-widest text-muted-foreground">{pace.what} · 사회자에게</p>
          <p className="mt-1 text-lg font-semibold leading-snug" data-testid="pace-say">
            {pace.say}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">{pace.why}</p>
        </section>
      )}

      {/* 다음 · 그다음 */}
      <section className="grid gap-2 sm:grid-cols-2">
        <div
          className={cn(
            'flex items-start gap-3 rounded-lg border p-4 transition-colors',
            nextSoon ? 'border-accent bg-accent/10' : 'border-border',
          )}
          data-testid="live-next-card"
          data-soon={nextSoon ? 'yes' : 'no'}
        >
          {next?.photo && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={next.photo}
              alt=""
              className="h-12 w-12 shrink-0 rounded-full border border-border object-cover"
              data-testid="live-next-photo"
            />
          )}
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium tracking-widest text-muted-foreground">다음</p>
            <p className="mt-1 text-xl font-semibold" data-testid="live-next">
              {next ? `${next.order_no ? `${next.order_no}. ` : ''}${next.title}` : '없음 (마지막)'}
            </p>
            {next?.detail && <p className="mt-0.5 text-sm text-muted-foreground">{next.detail}</p>}
            {next && (
              <p className={cn('mt-1 text-xs', nextSoon ? 'font-medium text-accent' : 'text-muted-foreground')}>
                {nextSoon ? (
                  <>
                    <Bell className="mr-1 inline h-3.5 w-3.5" aria-hidden />곧 다음 차례입니다 —{' '}
                    <strong>{next.title}</strong> 을(를) 무대 옆으로
                  </>
                ) : (
                  <>
                    대기실에서 <strong className="text-foreground">{next.title}</strong> 을(를) 무대 옆으로
                  </>
                )}
              </p>
            )}
          </div>
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

      {/* 대기실 선생님께는 "다음에 누구" 하나뿐이다 — 나머지를 다 걷어 낸 화면 */}
      {!canLead && (
        <button
          type="button"
          onClick={() => setWaiting(true)}
          className="rounded-lg border border-accent bg-accent/5 px-4 py-3 text-left"
          data-testid="waiting-on"
        >
          <span className="block font-medium">대기실 모드로 보기</span>
          <span className="mt-0.5 block text-xs text-muted-foreground">
            다음에 데려올 아이만 아주 크게. 밀린 시간·전체 순서는 감춥니다.
          </span>
        </button>
      )}

      {/* 다음 차례 알림 — 화면을 계속 안 보셔도 되게. 이 기계에만 담기므로 따라보기 화면에도 둔다 */}
      <section className="grid gap-2 rounded-lg border border-border p-3" data-testid="live-chime">
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={chimePrefs.on}
              onChange={(native) => changeChime({ on: native.target.checked })}
              className="h-4 w-4"
            />
            {chimePrefs.on ? (
              <Bell className="h-4 w-4 text-accent" aria-hidden />
            ) : (
              <BellOff className="h-4 w-4 text-muted-foreground" aria-hidden />
            )}
            <span>
              <strong>다음 차례 알림음</strong>
              <span className="ml-1.5 text-xs text-muted-foreground">
                다음 아이 차례 {CHIME_LEAD_SEC}초 전에 짧게 한 번 울립니다
                {!canLead && ' — 대기실에서 아이를 부르실 때입니다'}
              </span>
            </span>
          </label>

          {/* 홀마다 다르다. 로비가 시끄러우면 맑은 종은 묻히고, 무대 옆에서는 높은 소리가 튄다 */}
          {chimePrefs.on && (
            <div className="grid gap-1 pl-6" data-testid="chime-sounds">
              {CHIME_SOUNDS.map((sound) => (
                <label key={sound.id} className="flex cursor-pointer items-baseline gap-2 text-sm">
                  <input
                    type="radio"
                    name="chime-sound"
                    checked={chimePrefs.soundId === sound.id}
                    onChange={() => changeChime({ soundId: sound.id })}
                    className="h-3.5 w-3.5"
                  />
                  <span>
                    {sound.name}
                    <span className="ml-1.5 text-xs text-muted-foreground">{sound.hint}</span>
                  </span>
                </label>
              ))}
              <p className="text-xs text-muted-foreground">
                고르시면 그 자리에서 한 번 들려 드립니다. 지금 고르신 것은{' '}
                <strong className="text-foreground">{getChimeSound(chimePrefs.soundId).name}</strong> 입니다.
              </p>
            </div>
          )}

          {/* 소리는 "무슨 일이 났다" 만 알려 준다. 이름까지 들으면 화면을 안 봐도 된다 */}
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={chimePrefs.speak}
              onChange={(native) => changeChime({ speak: native.target.checked })}
              className="h-4 w-4"
              disabled={!speakable}
            />
            <Volume2
              className={cn('h-4 w-4', chimePrefs.speak ? 'text-accent' : 'text-muted-foreground')}
              aria-hidden
            />
            <span>
              <strong>이름까지 말로</strong>
              <span className="ml-1.5 text-xs text-muted-foreground">
                {speakable
                  ? '"다음, 3번 김서연" 처럼 읽어 드립니다 — 화면을 안 보셔도 됩니다'
                  : '이 브라우저는 읽어 주기를 지원하지 않습니다 (크롬·엣지에서 됩니다)'}
              </span>
            </span>
          </label>

          {/* 로비가 시끄러우면 어떤 소리도 묻힌다. 주머니 속 진동은 안 묻힌다 */}
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={chimePrefs.buzz}
              onChange={(native) => changeChime({ buzz: native.target.checked })}
              className="h-4 w-4"
            />
            <Vibrate
              className={cn('h-4 w-4', chimePrefs.buzz ? 'text-accent' : 'text-muted-foreground')}
              aria-hidden
            />
            <span>
              <strong>진동도 함께</strong>
              <span className="ml-1.5 text-xs text-muted-foreground">
                로비가 시끄러워도, 소리를 꺼 두셔도 주머니에서 느끼십니다 (휴대폰만)
              </span>
            </span>
          </label>

          <p className="text-xs text-muted-foreground">
            객석에는 안 들릴 만큼 작은 소리입니다 — 소리를 못 듣는 자리에서도 위 <strong>다음</strong> 칸이
            함께 켜집니다. 소리를 끄고 <strong>진동만</strong> 켜 두셔도 됩니다.
          </p>
        </section>

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
          {shared && <FollowLink event={event} />}
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

/**
 * 대기실·접수처가 열 주소.
 *
 * 이 주소는 초대장과 같은 자리에 있다. 뜨는 것은 초대장에 이미 있는 이름과 곡뿐이지만,
 * **누가 보는지는 원장님이 정하셔야 한다.** 코드를 켜 두면 그 코드를 아는 화면만 따라온다.
 */
function FollowLink({ event }: { event: EventRecord }) {
  const [code, setCode] = useState<string | null>(event.live_code)
  /**
   * 켬·끔은 **누른 즉시** 움직인다. 서버를 기다리는 동안 멈춰 있으면
   * 안 눌린 줄 알고 다시 누르시게 된다. 실패하면 되돌린다.
   */
  const [locked, setLocked] = useState(!!event.live_code)
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)

  const origin = typeof window === 'undefined' ? '' : window.location.origin
  const url = `${origin}/e/${event.id}/live${code ? `?k=${code}` : ''}`

  async function setLock(next: boolean) {
    setLocked(next)
    setBusy(true)
    try {
      const res = await fetch(`/api/events/${event.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ live_code: next }),
      })
      const body = await res.json()
      if (!res.ok) throw new Error(body.error ?? '바꾸지 못했습니다.')
      setCode(body.event?.live_code ?? null)
    } catch {
      // 못 바꿨으면 되돌린다 — 잠긴 줄 아셨는데 안 잠겨 있으면 안 된다
      setLocked(!next)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-2 grid gap-1.5" data-testid="follow-link">
      <p className="text-xs text-muted-foreground">
        대기실·접수처 스태프는 이 주소를 열어 두시면 됩니다. 로그인이 필요 없습니다.
      </p>
      <div className="flex items-center gap-1.5">
        <code className="min-w-0 flex-1 truncate rounded bg-secondary px-2 py-1.5 text-xs" data-testid="follow-url">
          {url}
        </code>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            void navigator.clipboard
              ?.writeText(url)
              .then(() => {
                setCopied(true)
                window.setTimeout(() => setCopied(false), 2200)
              })
              .catch(() => undefined)
          }}
        >
          {copied ? <Check className="h-4 w-4 text-accent" /> : <Copy className="h-4 w-4" />}
        </Button>
      </div>
      <label className="flex cursor-pointer items-start gap-2 text-xs">
        <input
          type="checkbox"
          checked={locked}
          disabled={busy}
          onChange={(native) => void setLock(native.target.checked)}
          className="mt-0.5 h-3.5 w-3.5"
        />
        <KeyRound className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" aria-hidden />
        <span className="text-muted-foreground">
          <strong className="text-foreground">코드를 아는 사람만 보게 하기</strong>
          {locked && code ? (
            <>
              {' '}— 코드 <strong className="tabular-nums tracking-widest text-foreground">{code}</strong>. 위 주소에
              이미 들어 있으니 그대로 보내시면 됩니다.
            </>
          ) : locked ? (
            <> — 코드를 만드는 중입니다…</>
          ) : (
            <> — 지금은 이 주소를 아는 누구나 볼 수 있습니다.</>
          )}
          <br />
          비밀번호가 아니라 문고리입니다. 여기 뜨는 것은 초대장에 이미 있는 이름과 곡뿐입니다.
        </span>
      </label>
    </div>
  )
}
