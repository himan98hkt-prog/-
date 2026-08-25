'use client'

import { RefreshCw, Trash2, Users } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { Rsvp } from '@/lib/types'
import type { RsvpSummary } from '@/lib/store/types'

/** 참석 집계 — 30초마다 새로고침하고, 버튼으로 즉시 갱신할 수 있다 */
export function RsvpDashboard({
  eventId,
  initialRsvps,
  initialSummary,
}: {
  eventId: string
  initialRsvps: Rsvp[]
  initialSummary: RsvpSummary
}) {
  const [rsvps, setRsvps] = useState(initialRsvps)
  const [summary, setSummary] = useState(initialSummary)
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch(`/api/events/${eventId}/rsvps`, { cache: 'no-store' })
      if (res.ok) {
        const data = await res.json()
        setRsvps(data.rsvps)
        setSummary(data.summary)
      }
    } finally {
      setLoading(false)
    }
  }, [eventId])

  useEffect(() => {
    const timer = setInterval(refresh, 30_000)
    return () => clearInterval(timer)
  }, [refresh])

  async function remove(id: string) {
    await fetch(`/api/rsvp/${id}`, { method: 'DELETE' }).catch(() => undefined)
    refresh()
  }

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-4 w-4 text-accent" aria-hidden />
            참석 집계
          </CardTitle>
          <CardDescription>학부모가 초대장에서 회신하면 여기에 바로 쌓입니다.</CardDescription>
        </div>
        <Button variant="ghost" size="sm" onClick={refresh} disabled={loading}>
          <RefreshCw className={loading ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} aria-hidden />
          새로고침
        </Button>
      </CardHeader>
      <CardContent className="grid gap-5">
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: '회신', value: `${summary.responses}건` },
            { label: '참석', value: `${summary.attending}가정` },
            { label: '불참', value: `${summary.declined}가정` },
            { label: '총 인원', value: `${summary.headcount}명` },
          ].map((stat) => (
            <div key={stat.label} className="rounded-md border border-border bg-muted/30 px-3 py-2">
              <dt className="text-xs text-muted-foreground">{stat.label}</dt>
              <dd className="mt-0.5 text-lg font-semibold tabular-nums">{stat.value}</dd>
            </div>
          ))}
        </dl>

        {rsvps.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">아직 회신이 없습니다.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="py-2 font-medium">학생</th>
                  <th className="py-2 font-medium">보호자</th>
                  <th className="py-2 font-medium">참석</th>
                  <th className="py-2 font-medium">인원</th>
                  <th className="py-2 font-medium">응원 메시지</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody>
                {rsvps.map((r) => (
                  <tr key={r.id} className="border-b border-border/60 last:border-0 align-top">
                    <td className="py-2.5 font-medium">{r.student_name}</td>
                    <td className="py-2.5 text-muted-foreground">{r.parent_name}</td>
                    <td className="py-2.5">{r.attending ? '참석' : '불참'}</td>
                    <td className="py-2.5 tabular-nums">{r.attending ? `${r.headcount}명` : '-'}</td>
                    <td className="py-2.5 text-muted-foreground">{r.message ?? ''}</td>
                    <td className="py-2.5 text-right">
                      <Button variant="ghost" size="icon" onClick={() => remove(r.id)} aria-label="회신 삭제">
                        <Trash2 className="h-4 w-4 text-destructive" aria-hidden />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
