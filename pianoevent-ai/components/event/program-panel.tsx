'use client'

import { AlertTriangle, ArrowUpDown, ChevronDown, ChevronUp, Printer, Sparkles } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'
import { PlanSummary, PlanTable } from '@/components/event/plan-table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldHint, Input, Label } from '@/components/ui/field'
import { DESIGN_TEMPLATES } from '@/lib/design/templates'
import { formatWallClock } from '@/lib/format'
import { NextHere } from '@/components/flow/next-here'
import { useUndo } from '@/components/undo/undo-bar'
import { applyOrder, buildProgram } from '@/lib/program/order'
import { DEFAULT_PROGRAM_OPTIONS, type EventRecord, type EventStudent, type ProgramPlan } from '@/lib/types'

interface GenerateResult {
  source: 'ai' | 'rule'
  model: string | null
  fallbackReason: string | null
  plan: ProgramPlan
  script: { opening: string; closing: string; byStudentId: Record<string, string> }
}

export function ProgramPanel({
  event,
  students,
  hasPrint = false,
}: {
  event: EventRecord
  students: EventStudent[]
  /** 인쇄물을 이미 고르셨는가 */
  hasPrint?: boolean
}) {
  const router = useRouter()
  const [pending, setPending] = useState(false)
  const [result, setResult] = useState<GenerateResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [turnover, setTurnover] = useState(DEFAULT_PROGRAM_OPTIONS.turnover_sec)
  const [intermission, setIntermission] = useState(DEFAULT_PROGRAM_OPTIONS.intermission_sec / 60)

  const options = useMemo(
    () => ({
      ...DEFAULT_PROGRAM_OPTIONS,
      turnover_sec: turnover,
      intermission_sec: Math.round(intermission * 60),
    }),
    [turnover, intermission],
  )

  /** 저장된 순서가 있으면 그대로, 없으면 규칙 엔진 미리보기 */
  const preview = useMemo(() => {
    if (students.length === 0) return null
    const ordered = students.filter((s) => s.order_no !== null)
    if (ordered.length === students.length) {
      const ids = [...students].sort((a, b) => (a.order_no ?? 0) - (b.order_no ?? 0)).map((s) => s.id)
      return applyOrder(students, ids, options)
    }
    return buildProgram(students, options)
  }, [students, options])

  const plan = result?.plan ?? preview
  const scripts = useMemo(() => {
    if (result) return result.script.byStudentId
    return Object.fromEntries(students.map((s) => [s.id, s.mc_script ?? '']))
  }, [result, students])

  async function generate() {
    setPending(true)
    setError(null)
    try {
      const res = await fetch(`/api/events/${event.id}/program`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ turnover_sec: options.turnover_sec, intermission_sec: options.intermission_sec }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '순서표를 만들지 못했습니다.')
      setResult(data as GenerateResult)
      router.refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : '순서표를 만들지 못했습니다.')
    } finally {
      setPending(false)
    }
  }

  if (students.length === 0) {
    return (
      <Card>
        <CardContent className="py-14 text-center text-sm text-muted-foreground">
          학생 명단을 먼저 등록하면 순서표를 만들 수 있습니다.
        </CardContent>
      </Card>
    )
  }

  const source = result?.source ?? event.program_source

  const madeProgram = event.program_source !== null || result !== null

  return (
    <div className="grid gap-5">
      {/* 순서표가 나왔으면 다음은 인쇄물이다 — 여기서 바로 넘어가시게 한다 */}
      {madeProgram && !hasPrint && (
        <NextHere
          step="print"
          eventId={event.id}
          label="인쇄물 만들러 가기"
          hint="순서가 나왔습니다. 포스터와 순서지는 이 순서 그대로 이미 만들어져 있습니다 — 테마만 고르시면 됩니다."
          run={async () => {
            /* 인쇄물은 만들어 둘 것이 없다. 고르시는 화면으로 모셔다 드리기만 하면 된다 */
          }}
        />
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-accent" aria-hidden />
            연주 순서 · 사회자 대본 생성
          </CardTitle>
          <CardDescription>
            난이도와 소요시간을 분석해 오프닝 → 초급 → 중급 → 앙상블 → 피날레 흐름으로 배치하고, 곡마다 사회자 멘트를
            만듭니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <Label htmlFor="turnover">곡 사이 전환 시간(초)</Label>
              <Input
                id="turnover"
                type="number"
                min={0}
                max={300}
                step={5}
                value={turnover}
                onChange={(e) => setTurnover(Number(e.target.value))}
              />
              <FieldHint>인사·착석·박수에 걸리는 시간</FieldHint>
            </div>
            <div>
              <Label htmlFor="intermission">중간 휴식(분)</Label>
              <Input
                id="intermission"
                type="number"
                min={0}
                max={30}
                value={intermission}
                onChange={(e) => setIntermission(Number(e.target.value))}
              />
              <FieldHint>0 이면 휴식 없이 진행합니다.</FieldHint>
            </div>
            <div className="flex items-end">
              <Button onClick={generate} disabled={pending} className="w-full">
                {pending ? '생성 중…' : 'AI 순서표 만들기'}
              </Button>
            </div>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          {source && (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge variant={source === 'ai' ? 'accent' : 'outline'}>
                {source === 'ai' ? `AI 생성${result?.model ? ` · ${result.model}` : ''}` : '내장 규칙 엔진'}
              </Badge>
              {result?.fallbackReason && <span className="text-muted-foreground">{result.fallbackReason}</span>}
            </div>
          )}
        </CardContent>
      </Card>

      {plan && (
        <>
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>순서표</CardTitle>
              <Link href={`/events/${event.id}/design/print?template=program-inner`} target="_blank">
                <Button variant="outline" size="sm">
                  <Printer className="h-4 w-4" aria-hidden />
                  인쇄 · PDF
                </Button>
              </Link>
            </CardHeader>
            <CardContent className="grid gap-5">
              <PlanSummary plan={plan} startISO={event.event_at} />
              <OrderEditor
                eventId={event.id}
                plan={plan}
                startISO={event.event_at}
                onSaved={() => router.refresh()}
              />
              <PlanTable plan={plan} startISO={event.event_at} showScript scripts={scripts} />
            </CardContent>
          </Card>

          {plan.warnings.length > 0 && (
            <Card className="border-destructive/30">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-destructive">
                  <AlertTriangle className="h-4 w-4" aria-hidden />
                  확인이 필요한 부분
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                  {plan.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}


/**
 * 순서 직접 조정.
 *
 * 자동 배치는 출발점이다. "이 아이는 앞쪽에 두고 싶다", "형제는 붙여야 한다" 같은
 * 원장만 아는 사정을 손으로 반영할 수 없으면 자동 배치는 신뢰를 얻지 못한다.
 * 위·아래 한 칸씩 옮기는 방식이라 마우스를 끌 줄 몰라도 쓸 수 있다.
 */
function OrderEditor({
  eventId,
  plan,
  startISO,
  onSaved,
}: {
  eventId: string
  plan: ProgramPlan
  startISO: string
  onSaved: () => void
}) {
  const undo = useUndo()
  const [open, setOpen] = useState(false)
  const [order, setOrder] = useState<string[]>(() => plan.items.map((i) => i.student.id))
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const byId = useMemo(() => new Map(plan.items.map((i) => [i.student.id, i])), [plan])
  const current = plan.items.map((i) => i.student.id)
  const dirty = order.join(',') !== current.join(',')

  // 순서표가 다시 생성되면 편집 중이던 순서도 새것으로 맞춘다
  useEffect(() => {
    setOrder(plan.items.map((i) => i.student.id))
    setSaved(false)
  }, [plan])

  function move(index: number, by: -1 | 1) {
    const next = [...order]
    const to = index + by
    if (to < 0 || to >= next.length) return
    ;[next[index], next[to]] = [next[to], next[index]]
    setOrder(next)
    setSaved(false)
  }

  async function send(next: string[]) {
    const res = await fetch(`/api/events/${eventId}/program`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ order: next }),
    })
    if (!res.ok) throw new Error((await res.json()).error ?? '저장하지 못했습니다.')
    onSaved()
  }

  async function save() {
    setSaving(true)
    // 저장 **전**의 순서를 담아 둔다. 저장하고 나서 담으면 되돌릴 곳이 없다.
    const before = current
    try {
      await send(order)
      setSaved(true)
      undo.remember({
        id: 'program:order',
        what: '연주 순서 바꾸기',
        detail: '저장 전 순서로 돌아갑니다',
        run: () => send(before),
      })
    } finally {
      setSaving(false)
    }
  }

  if (plan.items.length < 2) return null

  return (
    <div className="rounded-md border border-border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm hover:bg-secondary"
      >
        <span className="flex items-center gap-2 font-medium">
          <ArrowUpDown className="h-4 w-4 text-accent" aria-hidden />
          순서 직접 바꾸기
        </span>
        <span className="text-xs text-muted-foreground">
          {open ? '접기' : '자동 배치가 마음에 안 드는 곳만 옮기세요'}
        </span>
      </button>

      {open && (
        <div className="border-t border-border p-3">
          <ul className="grid gap-1">
            {order.map((id, index) => {
              const item = byId.get(id)
              if (!item) return null
              return (
                <li
                  key={id}
                  className="flex items-center gap-2 rounded-md border border-border px-2.5 py-1.5 text-sm"
                >
                  <span className="w-6 shrink-0 text-center font-mono text-xs tabular-nums text-accent">
                    {index + 1}
                  </span>
                  <span className="min-w-0 flex-1 truncate">
                    <b className="font-medium">{item.student.student_name}</b>
                    <span className="ml-2 text-xs text-muted-foreground">{item.student.piece_title}</span>
                  </span>
                  <span className="flex shrink-0 gap-0.5">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={index === 0}
                      aria-label={`${item.student.student_name} 위로`}
                      onClick={() => move(index, -1)}
                    >
                      <ChevronUp className="h-4 w-4" aria-hidden />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={index === order.length - 1}
                      aria-label={`${item.student.student_name} 아래로`}
                      onClick={() => move(index, 1)}
                    >
                      <ChevronDown className="h-4 w-4" aria-hidden />
                    </Button>
                  </span>
                </li>
              )
            })}
          </ul>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" disabled={!dirty || saving} onClick={save}>
              {saving ? '저장 중…' : '이 순서로 저장'}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!dirty || saving}
              onClick={() => setOrder(current)}
            >
              고치던 것 취소
            </Button>
            {saved && !dirty && <span className="text-xs text-accent">저장했습니다. 시각이 다시 계산됩니다.</span>}
            {dirty && (
              <span className="text-xs text-muted-foreground">
                저장하면 연주 시각과 인쇄물 {DESIGN_TEMPLATES.length}종이 함께 바뀝니다.
              </span>
            )}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            사회자 멘트는 그대로 남습니다. 순서만 바뀝니다. — 시각은 {formatWallClock(startISO, 0)} 개회 기준
          </p>
        </div>
      )}
    </div>
  )
}
