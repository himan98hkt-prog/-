'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input, Label, Select, Textarea } from '@/components/ui/field'

export function RsvpForm({ eventId }: { eventId: string }) {
  const [attending, setAttending] = useState(true)
  const [pending, setPending] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(formData: FormData) {
    setPending(true)
    setError(null)
    try {
      const res = await fetch('/api/rsvp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_id: eventId,
          parent_name: formData.get('parent_name'),
          student_name: formData.get('student_name'),
          attending,
          headcount: Number(formData.get('headcount') ?? 1),
          message: formData.get('message'),
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '회신을 보내지 못했습니다.')
      setDone(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : '회신을 보내지 못했습니다.')
    } finally {
      setPending(false)
    }
  }

  if (done) {
    return (
      <div className="rounded-lg border border-accent/30 bg-accent/5 p-6 text-center">
        <p className="text-base font-semibold">회신이 전달되었습니다.</p>
        <p className="mt-1.5 text-sm text-muted-foreground">
          {attending ? '공연장에서 뵙겠습니다. 아이의 무대를 함께 응원해 주세요.' : '알려 주셔서 감사합니다.'}
        </p>
        <Button variant="ghost" size="sm" className="mt-4" onClick={() => setDone(false)}>
          다시 입력하기
        </Button>
      </div>
    )
  }

  return (
    <form action={submit} className="grid gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="student_name">학생 이름</Label>
          <Input id="student_name" name="student_name" required maxLength={40} placeholder="김서연" />
        </div>
        <div>
          <Label htmlFor="parent_name">보호자 성함</Label>
          <Input id="parent_name" name="parent_name" required maxLength={40} placeholder="김○○" />
        </div>
      </div>

      <div>
        <Label htmlFor="attending">참석 여부</Label>
        <div className="flex gap-2">
          <Button
            type="button"
            variant={attending ? 'default' : 'outline'}
            className="flex-1"
            onClick={() => setAttending(true)}
            aria-pressed={attending}
          >
            참석합니다
          </Button>
          <Button
            type="button"
            variant={!attending ? 'default' : 'outline'}
            className="flex-1"
            onClick={() => setAttending(false)}
            aria-pressed={!attending}
          >
            참석이 어렵습니다
          </Button>
        </div>
      </div>

      {attending && (
        <div>
          <Label htmlFor="headcount">참석 인원 (학생 포함)</Label>
          <Select id="headcount" name="headcount" defaultValue="2">
            {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>
                {n}명
              </option>
            ))}
          </Select>
        </div>
      )}

      <div>
        <Label htmlFor="message">아이에게 남기는 응원 메시지 (선택)</Label>
        <Textarea id="message" name="message" maxLength={300} placeholder="연습한 만큼만 하고 오면 돼. 우리 딸 최고!" />
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Button type="submit" size="lg" disabled={pending}>
        {pending ? '보내는 중…' : '참석 여부 보내기'}
      </Button>

      <p className="text-center text-xs text-muted-foreground">
        입력하신 정보는 이 행사의 참석 집계 목적으로만 쓰이며, 행사 종료 후 학원 정책에 따라 삭제됩니다.
      </p>
    </form>
  )
}
