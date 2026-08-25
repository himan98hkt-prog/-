'use client'

import { AlertTriangle, Printer, Sparkles } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useMemo, useState } from 'react'
import { PlanSummary, PlanTable } from '@/components/event/plan-table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldHint, Input, Label } from '@/components/ui/field'
import { applyOrder, buildProgram } from '@/lib/program/order'
import { DEFAULT_PROGRAM_OPTIONS, type EventRecord, type EventStudent, type ProgramPlan } from '@/lib/types'

interface GenerateResult {
  source: 'ai' | 'rule'
  model: string | null
  fallbackReason: string | null
  plan: ProgramPlan
  script: { opening: string; closing: string; byStudentId: Record<string, string> }
}

export function ProgramPanel({ event, students }: { event: EventRecord; students: EventStudent[] }) {
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

  return (
    <div className="grid gap-5">
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
              <Link href={`/events/${event.id}/program/print`} target="_blank">
                <Button variant="outline" size="sm">
                  <Printer className="h-4 w-4" aria-hidden />
                  인쇄 · PDF
                </Button>
              </Link>
            </CardHeader>
            <CardContent className="grid gap-5">
              <PlanSummary plan={plan} startISO={event.event_at} />
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
