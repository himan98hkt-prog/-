'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter } from '@/components/ui/card'
import { FieldHint, Input, Label, Select, Textarea } from '@/components/ui/field'
import { SEASON_LABEL, type EventType, type SeasonTheme } from '@/lib/types'

function defaultDateTime() {
  const d = new Date()
  d.setDate(d.getDate() + 21)
  d.setHours(15, 0, 0, 0)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function NewEventForm() {
  const router = useRouter()
  const [type, setType] = useState<EventType>('recital')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(formData: FormData) {
    setPending(true)
    setError(null)
    try {
      const res = await fetch('/api/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: formData.get('title'),
          type,
          event_at: formData.get('event_at'),
          venue: formData.get('venue'),
          theme: type === 'season' ? formData.get('theme') : null,
          greeting: formData.get('greeting'),
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '행사를 만들지 못했습니다.')
      router.push(`/events/${data.event.id}`)
      router.refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : '행사를 만들지 못했습니다.')
      setPending(false)
    }
  }

  return (
    <form action={onSubmit}>
      <Card>
        <CardContent className="grid gap-4 py-5">
          <div>
            <Label htmlFor="type">행사 종류</Label>
            <Select id="type" name="type" value={type} onChange={(e) => setType(e.target.value as EventType)}>
              <option value="recital">정기 연주회</option>
              <option value="season">시즌 특강</option>
            </Select>
          </div>

          {type === 'season' && (
            <div>
              <Label htmlFor="theme">테마</Label>
              <Select id="theme" name="theme" defaultValue="christmas">
                {(Object.keys(SEASON_LABEL) as SeasonTheme[]).map((theme) => (
                  <option key={theme} value={theme}>
                    {SEASON_LABEL[theme]}
                  </option>
                ))}
              </Select>
            </div>
          )}

          <div>
            <Label htmlFor="title">행사명</Label>
            <Input
              id="title"
              name="title"
              required
              maxLength={120}
              placeholder={type === 'recital' ? '제12회 정기 연주회' : '크리스마스 캐럴 특강'}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="event_at">일시</Label>
              <Input id="event_at" name="event_at" type="datetime-local" required defaultValue={defaultDateTime()} />
            </div>
            <div>
              <Label htmlFor="venue">장소</Label>
              <Input id="venue" name="venue" maxLength={160} placeholder="구민회관 소공연장" />
            </div>
          </div>

          <div>
            <Label htmlFor="greeting">원장 인사말 (선택)</Label>
            <Textarea
              id="greeting"
              name="greeting"
              maxLength={800}
              placeholder="한 해 동안 아이들이 쌓아 온 시간을 부모님께 들려드리는 자리입니다."
            />
            <FieldHint>초대장과 순서표 표지에 그대로 실립니다.</FieldHint>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
        <CardFooter className="justify-end">
          <Button type="submit" disabled={pending}>
            {pending ? '만드는 중…' : '행사 만들기'}
          </Button>
        </CardFooter>
      </Card>
    </form>
  )
}
