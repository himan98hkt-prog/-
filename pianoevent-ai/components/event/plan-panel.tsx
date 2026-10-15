'use client'

import { AlertTriangle, Armchair, CalendarClock, Info, ShieldCheck, Wallet } from 'lucide-react'
import { useMemo, useState } from 'react'
import { CopyButton } from '@/components/copy-button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldHint, Input, Label } from '@/components/ui/field'
import { formatWallClock } from '@/lib/format'
import {
  BASIS_LABEL,
  DEFAULT_BUDGET_ITEMS,
  applyVendorFees,
  buildBudget,
  feeNoticeMessage,
  formatWon,
} from '@/lib/ops/budget'
import { DEFAULT_REHEARSAL_OPTIONS, buildRehearsal, rehearsalCallMessage } from '@/lib/ops/rehearsal'
import { DEFAULT_SEATING_OPTIONS, buildSeating, seatLabel } from '@/lib/ops/seating'
import { ISSUE_LEVEL_LABEL, diagnoseProgram, issueSummary, type IssueLevel } from '@/lib/program/diagnose'
import type { Academy, EventRecord, ProgramPlan, Rsvp } from '@/lib/types'
import { normalizeBookings } from '@/lib/vendors'
import { cn } from '@/lib/utils'

const LEVEL_STYLE: Record<IssueLevel, string> = {
  high: 'border-red-300 bg-red-50 text-red-900',
  medium: 'border-amber-300 bg-amber-50 text-amber-900',
  low: 'border-border bg-secondary text-foreground',
}

/** 숫자 하나짜리 설정 — 원장이 손으로 만지는 값 */
function NumberField({
  id,
  label,
  value,
  onChange,
  suffix,
  step = 1,
  min = 0,
}: {
  id: string
  label: string
  value: number
  onChange: (next: number) => void
  suffix?: string
  step?: number
  min?: number
}) {
  return (
    <div>
      <Label htmlFor={id}>{label}</Label>
      <div className="flex items-center gap-2">
        <Input
          id={id}
          type="number"
          inputMode="numeric"
          min={min}
          step={step}
          value={value}
          onChange={(e) => onChange(Math.max(min, Number(e.target.value) || 0))}
        />
        {suffix && <span className="shrink-0 text-sm text-muted-foreground">{suffix}</span>}
      </div>
    </div>
  )
}

export function PlanPanel({
  academy,
  event,
  plan,
  rsvps,
}: {
  academy: Academy
  event: EventRecord
  plan: ProgramPlan
  rsvps: Rsvp[]
}) {
  const issues = useMemo(() => diagnoseProgram(plan), [plan])

  // ── 리허설 ────────────────────────────────────────────────
  const [startBefore, setStartBefore] = useState(DEFAULT_REHEARSAL_OPTIONS.start_before_min)
  const [perStudentMin, setPerStudentMin] = useState(DEFAULT_REHEARSAL_OPTIONS.per_student_sec / 60)
  const [groupSize, setGroupSize] = useState(DEFAULT_REHEARSAL_OPTIONS.group_size)
  const rehearsal = useMemo(
    () =>
      buildRehearsal(plan, {
        start_before_min: startBefore,
        per_student_sec: Math.max(30, Math.round(perStudentMin * 60)),
        group_size: Math.max(1, groupSize),
      }),
    [plan, startBefore, perStudentMin, groupSize],
  )

  // ── 예산 ──────────────────────────────────────────────────
  const [off, setOff] = useState<Record<string, boolean>>({})
  const [share, setShare] = useState(0)
  const attending = useMemo(() => rsvps.filter((r) => r.attending), [rsvps])
  /**
   * 「함께할 분들」에 적어 두신 **실제 금액**을 어림값 위에 얹는다.
   * 같은 숫자를 두 번 적으시게 하지 않는다.
   */
  const priced = useMemo(
    () => applyVendorFees(DEFAULT_BUDGET_ITEMS, normalizeBookings(event.vendor_bookings)),
    [event.vendor_bookings],
  )
  const budget = useMemo(
    () =>
      buildBudget({
        students: plan.items.length,
        families: Math.max(attending.length, plan.items.length),
        guests: attending.reduce((s, r) => s + r.headcount, 0) || plan.items.length * 3,
        items: priced.items.filter((item) => !off[item.id]),
        academy_share: share,
      }),
    [plan.items.length, attending, off, share, priced],
  )

  // ── 좌석 ──────────────────────────────────────────────────
  const [seatsPerRow, setSeatsPerRow] = useState(DEFAULT_SEATING_OPTIONS.seats_per_row)
  const [rows, setRows] = useState(DEFAULT_SEATING_OPTIONS.rows)
  const seating = useMemo(
    () => buildSeating(rsvps, { seats_per_row: Math.max(2, seatsPerRow), rows: Math.max(1, rows) }),
    [rsvps, seatsPerRow, rows],
  )

  if (plan.items.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center">
          <p className="text-sm text-muted-foreground">
            순서표가 있어야 리허설·예산·좌석을 계산할 수 있습니다.
            <br />
            먼저 <strong>순서표 · 대본</strong> 탭에서 순서표를 만들어 주세요.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="grid gap-5">
      {/* ── 순서표 정밀 진단 ────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-accent" aria-hidden />
            순서표 점검
          </CardTitle>
          <CardDescription>
            {issueSummary(issues)} — 당일 학부모 전화를 부르는 것들을 미리 봅니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2">
          {issues.length === 0 ? (
            <p className="rounded-md border border-border bg-secondary px-3 py-4 text-center text-sm text-muted-foreground">
              걸리는 곳이 없습니다. 이대로 인쇄하셔도 됩니다.
            </p>
          ) : (
            issues.map((issue) => (
              <div key={issue.id} className={cn('rounded-md border px-3 py-2.5 text-sm', LEVEL_STYLE[issue.level])}>
                <div className="flex flex-wrap items-center gap-2">
                  {issue.level === 'high' ? (
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
                  ) : (
                    <Info className="h-3.5 w-3.5 shrink-0" aria-hidden />
                  )}
                  <span className="font-medium">{issue.title}</span>
                  <Badge variant="outline" className="text-xs">
                    {ISSUE_LEVEL_LABEL[issue.level]}
                  </Badge>
                </div>
                <p className="mt-1.5 text-sm opacity-90">{issue.detail}</p>
                <p className="mt-1 text-sm font-medium opacity-80">→ {issue.fix}</p>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {/* ── 리허설 시간표 ──────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarClock className="h-4 w-4 text-accent" aria-hidden />
            리허설 시간표
          </CardTitle>
          <CardDescription>
            전원을 한 번에 부르면 대기실이 터집니다. 조 단위로 시각을 나눠 계산합니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <NumberField
              id="reh-start"
              label="개회 몇 분 전 시작"
              value={startBefore}
              onChange={setStartBefore}
              suffix="분"
              step={10}
            />
            <NumberField
              id="reh-per"
              label="1인당"
              value={perStudentMin}
              onChange={setPerStudentMin}
              suffix="분"
              step={0.5}
            />
            <NumberField id="reh-group" label="한 조 인원" value={groupSize} onChange={setGroupSize} suffix="명" min={1} />
          </div>

          <div className="rounded-md border border-border bg-secondary px-3 py-2.5 text-sm">
            리허설 {formatWallClock(event.event_at, rehearsal.start_offset_sec)} ~{' '}
            {formatWallClock(event.event_at, rehearsal.end_offset_sec)} ·{' '}
            {rehearsal.slack_sec >= 0 ? (
              <span className="text-muted-foreground">개회까지 {Math.floor(rehearsal.slack_sec / 60)}분 여유</span>
            ) : (
              <span className="font-medium text-red-700">{Math.ceil(-rehearsal.slack_sec / 60)}분 모자람</span>
            )}
          </div>

          {rehearsal.warnings.map((warning) => (
            <p key={warning} className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              {warning}
            </p>
          ))}

          <div className="grid gap-2">
            {rehearsal.groups.map((group) => {
              const message = rehearsalCallMessage(event, group, academy.name)
              return (
                <div key={group.group} className="rounded-md border border-border px-3 py-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium">
                        {group.group}조 · {formatWallClock(event.event_at, group.call_offset_sec)} 도착
                        <span className="ml-2 text-xs font-normal text-muted-foreground">
                          무대 {formatWallClock(event.event_at, group.members[0].stage_offset_sec)}부터
                        </span>
                      </p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {group.members.map((m) => m.student_name).join(', ')}
                      </p>
                    </div>
                    <CopyButton text={message} label="소집 문자 복사" />
                  </div>
                </div>
              )
            })}
          </div>
          <FieldHint>
            문자를 복사해 조별 단톡방이나 개별 메시지로 그대로 보내시면 됩니다. 인쇄는 디자인 화면의{' '}
            <strong>리허설 시간표</strong> 양식에서 하세요.
          </FieldHint>
        </CardContent>
      </Card>

      {/* ── 예산·참가비 ────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wallet className="h-4 w-4 text-accent" aria-hidden />
            예산 · 참가비
          </CardTitle>
          <CardDescription>
            대관료가 확정되기 전에도 참가비 안내는 나가야 합니다. 항목을 켜고 끄며 맞춰 보세요.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-2">
            {priced.items.map((item) => {
              const line = budget.lines.find((l) => l.item.id === item.id)
              const enabled = !off[item.id]
              return (
                <label
                  key={item.id}
                  className={cn(
                    'flex cursor-pointer items-start gap-3 rounded-md border px-3 py-2 text-sm transition-colors',
                    enabled ? 'border-border' : 'border-dashed border-border opacity-55',
                  )}
                >
                  <input
                    type="checkbox"
                    checked={enabled}
                    disabled={!item.optional}
                    onChange={() => setOff((prev) => ({ ...prev, [item.id]: enabled }))}
                    className="mt-1 h-4 w-4 shrink-0 accent-[var(--accent)]"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-baseline gap-2">
                      <span className="font-medium">{item.label}</span>
                      <span className="text-xs text-muted-foreground">
                        {BASIS_LABEL[item.basis]} {item.unit_cost.toLocaleString('ko-KR')}원
                      </span>
                      {!item.optional && <Badge variant="outline" className="text-xs">필수</Badge>}
                      {priced.fromVendor[item.id] && (
                        <Badge variant="accent" className="text-xs">
                          {priced.fromVendor[item.id]} · 적어 두신 금액
                        </Badge>
                      )}
                    </span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">{item.note}</span>
                  </span>
                  <span className="shrink-0 text-sm font-medium tabular-nums">
                    {line ? line.amount.toLocaleString('ko-KR') : '—'}
                  </span>
                </label>
              )
            })}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <NumberField id="bud-share" label="학원 부담" value={share} onChange={setShare} suffix="원" step={50000} />
            <div className="rounded-md border border-border bg-secondary px-3 py-2 text-sm">
              <p className="flex justify-between">
                <span className="text-muted-foreground">합계</span>
                <b className="tabular-nums">{formatWon(budget.total)}</b>
              </p>
              <p className="mt-1 flex justify-between">
                <span className="text-muted-foreground">1인당 원가</span>
                <b className="tabular-nums">{formatWon(budget.per_student)}</b>
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-accent/40 bg-accent/8 px-4 py-3">
            <div>
              <p className="text-xs text-muted-foreground">권장 참가비 (학생 1인)</p>
              <p className="text-xl font-bold tabular-nums">{formatWon(budget.suggested_fee)}</p>
            </div>
            <CopyButton text={feeNoticeMessage(event, budget, academy.name)} label="안내 문구 복사" />
          </div>

          {budget.warnings.map((warning) => (
            <p key={warning} className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              {warning}
            </p>
          ))}
        </CardContent>
      </Card>

      {/* ── 좌석 ──────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Armchair className="h-4 w-4 text-accent" aria-hidden />
            객석 배치
          </CardTitle>
          <CardDescription>
            참석 회신 {attending.length}가정 {attending.reduce((s, r) => s + r.headcount, 0)}명을 가정 단위로 앉힙니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <NumberField id="seat-per-row" label="한 줄 좌석" value={seatsPerRow} onChange={setSeatsPerRow} suffix="석" min={2} />
            <NumberField id="seat-rows" label="줄 수" value={rows} onChange={setRows} suffix="줄" min={1} />
          </div>

          <div className="rounded-md border border-border bg-secondary px-3 py-2.5 text-sm">
            배정 {seating.assigned_seats}석 · 여유 {seating.free_seats}석 · 연주자석{' '}
            {seating.performer_rows.length}줄
          </div>

          {seating.warnings.map((warning) => (
            <p key={warning} className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              {warning}
            </p>
          ))}

          {seating.blocks.length > 0 && (
            <div className="grid gap-1.5">
              {seating.blocks.map((block) => (
                <div
                  key={`${block.row}-${block.from}`}
                  className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-sm"
                >
                  <span className="min-w-0 truncate">
                    {block.student_name} <span className="text-muted-foreground">가족 {block.headcount}명</span>
                  </span>
                  <span className="shrink-0 font-medium tabular-nums text-accent">{seatLabel(block)}</span>
                </div>
              ))}
            </div>
          )}
          <FieldHint>
            좌석 배치도는 디자인 화면의 <strong>좌석 배치도</strong> 양식으로 인쇄해 접수처에 붙이세요.
          </FieldHint>
        </CardContent>
      </Card>
    </div>
  )
}
