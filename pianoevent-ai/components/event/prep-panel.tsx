'use client'

import { CheckCircle2, ClipboardList, MessageSquareText, Printer, Smartphone, Timer } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { CopyButton } from '@/components/copy-button'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EventExport } from '@/components/event/event-transfer'
import { VendorPanel } from '@/components/event/vendor-panel'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatWallClock } from '@/lib/format'
import { buildChecklist, checklistTaskCount, currentGroup } from '@/lib/ops/checklist'
import { buildCueSheet } from '@/lib/ops/cuesheet'
import { buildMessages, messageBytes } from '@/lib/ops/messages'
import type { Academy, EventRecord, ProgramPlan } from '@/lib/types'
import { cn } from '@/lib/utils'

/** 체크 상태는 이 브라우저에만 남긴다 — 서버에 저장할 만큼 중요한 정보는 아니다 */
function useChecked(eventId: string) {
  const key = `pe_check_${eventId}`
  const [checked, setChecked] = useState<Record<string, boolean>>({})

  useEffect(() => {
    try {
      const raw = localStorage.getItem(key)
      if (raw) setChecked(JSON.parse(raw) as Record<string, boolean>)
    } catch {
      // 저장소를 못 쓰는 브라우저면 체크만 안 남는다
    }
  }, [key])

  function toggle(id: string) {
    setChecked((prev) => {
      const next = { ...prev, [id]: !prev[id] }
      try {
        localStorage.setItem(key, JSON.stringify(next))
      } catch {
        // 무시
      }
      return next
    })
  }

  return { checked, toggle }
}

export function PrepPanel({
  academy,
  event,
  plan,
}: {
  academy: Academy
  event: EventRecord
  plan: ProgramPlan
}) {
  const { checked, toggle } = useChecked(event.id)
  const [origin, setOrigin] = useState('')

  useEffect(() => {
    setOrigin(window.location.origin)
  }, [])

  const groups = useMemo(() => buildChecklist(event), [event])
  const now = useMemo(() => currentGroup(groups, event), [groups, event])
  const cue = useMemo(() => buildCueSheet(event, plan), [event, plan])
  const messages = useMemo(
    () => buildMessages({ academy, event, plan, inviteUrl: origin ? `${origin}/e/${event.id}` : undefined }),
    [academy, event, plan, origin],
  )

  const total = checklistTaskCount(groups)
  const doneCount = Object.values(checked).filter(Boolean).length

  return (
    <div className="grid gap-5">
      {/* 종이는 프로그램이 만들어 드리지만 사람은 원장님이 부르셔야 한다.
          그 자리를 비워 두면 「알아서 하세요」가 되므로 체크리스트 바로 위에 둔다 */}
      <VendorPanel academy={academy} event={event} />

      {now && (
        <Card className="border-accent/40 bg-accent/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Timer className="h-4 w-4 text-accent" aria-hidden />
              지금 할 일 — {now.label}
            </CardTitle>
            <CardDescription>
              {now.date} 기준입니다. 전체 {total}개 중 {doneCount}개 완료.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="grid gap-2">
              {now.tasks.map((task) => (
                <li key={task.id}>
                  <button
                    type="button"
                    onClick={() => toggle(`${now.id}-${task.id}`)}
                    className="flex w-full items-start gap-2.5 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-secondary"
                  >
                    <CheckCircle2
                      className={cn(
                        'mt-0.5 h-4 w-4 shrink-0',
                        checked[`${now.id}-${task.id}`] ? 'text-accent' : 'text-muted-foreground/40',
                      )}
                      aria-hidden
                    />
                    <span className="min-w-0">
                      <span
                        className={cn(
                          'text-sm font-medium',
                          checked[`${now.id}-${task.id}`] && 'text-muted-foreground line-through',
                        )}
                      >
                        {task.title}
                        {task.critical && <span className="ml-1 text-accent">★</span>}
                      </span>
                      <span className="block text-xs text-muted-foreground">{task.detail}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex-row items-start justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ClipboardList className="h-4 w-4 text-accent" aria-hidden />
              준비 체크리스트
            </CardTitle>
            <CardDescription>
              행사 날짜에 맞춰 날짜가 계산됩니다. ★ 은 특히 자주 빠뜨리는 항목입니다.
            </CardDescription>
          </div>
          <Link href={`/events/${event.id}/design/print?template=checklist`} target="_blank">
            <Button variant="outline" size="sm">
              <Printer className="h-4 w-4" aria-hidden />
              인쇄
            </Button>
          </Link>
        </CardHeader>
        <CardContent className="grid gap-5 md:grid-cols-2">
          {groups.map((group) => (
            <section key={group.id}>
              <div className="flex items-baseline justify-between border-b border-border pb-1.5">
                <h3 className="text-sm font-semibold">{group.label}</h3>
                <span className="text-xs text-muted-foreground">{group.date}</span>
              </div>
              <ul className="mt-2 grid gap-1">
                {group.tasks.map((task) => {
                  const id = `${group.id}-${task.id}`
                  return (
                    <li key={task.id}>
                      <button
                        type="button"
                        onClick={() => toggle(id)}
                        className="flex w-full items-start gap-2 rounded px-1.5 py-1 text-left transition-colors hover:bg-secondary"
                      >
                        <span
                          className={cn(
                            'mt-1 h-3.5 w-3.5 shrink-0 rounded-sm border',
                            checked[id] ? 'border-accent bg-accent' : 'border-input',
                          )}
                          aria-hidden
                        />
                        <span className="min-w-0">
                          <span className={cn('text-sm', checked[id] && 'text-muted-foreground line-through')}>
                            {task.title}
                            {task.critical && <span className="ml-1 text-accent">★</span>}
                          </span>
                          <span className="block text-xs leading-snug text-muted-foreground">{task.detail}</span>
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </section>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-start justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <MessageSquareText className="h-4 w-4 text-accent" aria-hidden />
              학부모 안내 문구
            </CardTitle>
            <CardDescription>복사해서 문자·카카오톡에 그대로 붙여넣으세요. 초대장 링크가 들어갑니다.</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4">
          {messages.map((message) => (
            <div key={message.kind} className="rounded-lg border border-border">
              <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{message.title}</span>
                  <Badge variant="outline">{message.when}</Badge>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{messageBytes(message.body)}바이트</span>
                  <CopyButton text={message.body} label="복사" variant="ghost" />
                </div>
              </div>
              <pre className="whitespace-pre-wrap px-4 py-3 font-sans text-sm leading-relaxed text-muted-foreground">
                {message.body}
              </pre>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-start justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Timer className="h-4 w-4 text-accent" aria-hidden />
              당일 진행표
            </CardTitle>
            <CardDescription>
              도착·리허설·객석 개방·연주·시상·정리까지 시각과 담당이 자동으로 계산됩니다.
            </CardDescription>
          </div>
          <div className="flex shrink-0 gap-2">
            <Link href={`/events/${event.id}/live`}>
              <Button variant="outline" size="sm" disabled={plan.items.length === 0}>
                <Smartphone className="h-4 w-4" aria-hidden />
                휴대폰으로 진행
              </Button>
            </Link>
            <Link href={`/events/${event.id}/design/print?template=cue-sheet`} target="_blank">
              <Button variant="outline" size="sm" disabled={plan.items.length === 0}>
                <Printer className="h-4 w-4" aria-hidden />
                인쇄
              </Button>
            </Link>
          </div>
        </CardHeader>
        <CardContent>
          {plan.items.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              순서표를 먼저 만들면 연주 시각까지 채워진 진행표가 나옵니다.
            </p>
          ) : (
            <ol className="grid gap-1.5">
              {cue
                .filter((item) => item.kind !== 'stage' || item.title.startsWith('개회'))
                .map((item, index) => (
                  <li key={`${item.offset_min}-${index}`} className="flex gap-3 text-sm">
                    <span className="w-16 shrink-0 tabular-nums font-medium">
                      {formatWallClock(event.event_at, item.offset_min * 60)}
                    </span>
                    <span className="min-w-0">
                      <span className="font-medium">{item.title}</span>
                      <span className="ml-2 text-xs text-muted-foreground">{item.owner}</span>
                      <span className="block text-xs text-muted-foreground">{item.detail}</span>
                    </span>
                  </li>
                ))}
              <li className="mt-1 text-xs text-muted-foreground">
                연주 {plan.items.length}곡의 시각은 인쇄본에 모두 들어갑니다.
              </li>
            </ol>
          )}
        </CardContent>
      </Card>

      {/* 컴퓨터를 바꾸시거나 집에서 이어 하실 때 */}
      <EventExport eventId={event.id} title={event.title} />
    </div>
  )
}
