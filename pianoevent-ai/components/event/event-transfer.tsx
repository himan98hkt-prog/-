'use client'

import { CalendarPlus, Download, Upload } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input, Label } from '@/components/ui/field'
import {
  bundleSummary,
  freshenSummary,
  nextTitle,
  nextYear,
  parseBundle,
  type EventBundle,
} from '@/lib/events/transfer'
import { cn } from '@/lib/utils'

/**
 * 이 행사를 파일 한 개로 내보낸다.
 *
 * 학원 컴퓨터에서 명단을 넣으시고 집에서 문구를 다듬으시는 원장님이 계신다.
 * 컴퓨터를 바꾸시는 해도 있다. 지금까지는 그때 처음부터 다시 하셔야 했다.
 */
export function EventExport({ eventId, title }: { eventId: string; title: string }) {
  return (
    <div className="grid gap-2 rounded-lg border border-border bg-card p-4" data-testid="event-export">
      <p className="text-sm font-medium">이 행사를 파일로 내보내기</p>
      <p className="text-sm text-muted-foreground">
        <strong>{title}</strong> 의 명단 · 순서 · 멘트 · 인쇄물 설정 · 아이 사진을 파일 하나에 담습니다. 다른
        컴퓨터에서 <strong>행사 목록 → 행사 파일 가져오기</strong> 로 그대로 여실 수 있습니다.
      </p>
      <div>
        <a href={`/api/events/${eventId}/export`} download>
          <Button variant="outline" size="sm">
            <Download className="h-4 w-4" aria-hidden />
            행사 파일 내보내기
          </Button>
        </a>
      </div>
      <p className="text-xs text-muted-foreground">
        학부모 회신은 담기지 않습니다 — 옮길 물건이 아닙니다. 파일은 이 컴퓨터에서 나와 원장님이 정하신 곳으로만
        갑니다.
      </p>
    </div>
  )
}

/** 내보낸 파일을 다시 들여온다. 늘 새 행사로 만든다 — 있는 것을 덮어쓰지 않는다 */
export function EventImport() {
  const router = useRouter()
  const fileRef = useRef<HTMLInputElement>(null)
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [dropping, setDropping] = useState(false)
  /** 고르신 파일 — 어떻게 가져올지 정하실 때까지 여기 둔다 */
  const [picked, setPicked] = useState<{ text: string; bundle: EventBundle } | null>(null)
  const [title, setTitle] = useState('')
  const [when, setWhen] = useState('')

  /** 파일을 먼저 읽어만 둔다. 그대로 가져올지 올해 것으로 만들지는 그다음에 고르신다 */
  async function take(file: File) {
    setPending(true)
    setMessage(null)
    setPicked(null)
    try {
      const text = await file.text()
      // 서버에 보내기 전에 여기서 먼저 읽어 본다 — 엉뚱한 파일이면 그 자리에서 말씀드린다
      const bundle = parseBundle(text)
      setPicked({ text, bundle })
      setTitle(nextTitle(bundle.event.title))
      setWhen(nextYear(bundle.event.event_at).slice(0, 10))
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '가져오지 못했습니다.')
    } finally {
      setPending(false)
    }
  }

  async function bring(freshen: boolean) {
    if (!picked) return
    setPending(true)
    setMessage(null)
    try {
      const res = await fetch('/api/events/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          freshen
            ? { text: picked.text, freshen: true, title, event_at: new Date(`${when}T09:00:00`).toISOString() }
            : { text: picked.text },
        ),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '가져오지 못했습니다.')
      const skipped =
        data.skipped_photos > 0 ? ` 보관함이 꽉 차서 사진 ${data.skipped_photos}장은 넣지 못했습니다.` : ''
      setMessage(
        freshen
          ? `"${title}" 을(를) 새로 만들었습니다. 아이들은 그대로 있고 곡만 비어 있습니다.${skipped}`
          : `${bundleSummary(picked.bundle)} — 새 행사로 들여왔습니다.${skipped}`,
      )
      setPicked(null)
      router.refresh()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '가져오지 못했습니다.')
    } finally {
      setPending(false)
    }
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setDropping(true)
      }}
      onDragLeave={() => setDropping(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDropping(false)
        const file = e.dataTransfer.files?.[0]
        if (file) take(file)
      }}
      className={cn(
        'grid gap-2 rounded-lg border-2 border-dashed p-4 transition-colors',
        dropping ? 'border-accent bg-accent/10' : 'border-border bg-muted/30',
      )}
      data-testid="event-import"
    >
      <p className="text-sm font-medium">행사 파일 가져오기</p>
      <p className="text-sm text-muted-foreground">
        다른 컴퓨터에서 내보낸 <strong>.json</strong> 파일을 여기로 끌어다 놓으세요. 늘 <strong>새 행사</strong> 로
        들어옵니다 — 지금 있는 행사를 덮어쓰지 않습니다.
      </p>
      <div>
        <input
          ref={fileRef}
          type="file"
          accept=".json,application/json"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) take(file)
            e.target.value = ''
          }}
          aria-label="행사 파일 고르기"
        />
        <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={pending}>
          <Upload className="h-4 w-4" aria-hidden />
          파일 고르기
        </Button>
      </div>

      {/* 파일을 읽고 나면 — 그대로 가져올지, 올해 것으로 새로 만들지 */}
      {picked && (
        <div className="grid gap-3 rounded-md border border-border bg-card p-3" data-testid="import-choice">
          <p className="text-sm">
            읽었습니다 — <strong>{bundleSummary(picked.bundle)}</strong>
          </p>

          <div className="grid gap-2 rounded-md border border-accent/40 bg-accent/5 p-3">
            <p className="flex items-center gap-1.5 text-sm font-medium">
              <CalendarPlus className="h-4 w-4 text-accent" aria-hidden />
              작년 것으로 올해 새로 만들기
            </p>
            <p className="text-xs text-muted-foreground">
              {freshenSummary(picked.bundle)}. 아이 이름 · 난이도 · 사진 · 인쇄물 설정은 그대로 오고,{' '}
              <strong className="text-foreground">연주곡과 사회자 멘트는 비웁니다</strong> — 작년 멘트가 올해
              대본에 그대로 실리면 안 되니까요.
            </p>
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[200px] flex-1">
                <Label htmlFor="freshen-title">행사 이름</Label>
                <Input id="freshen-title" value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="freshen-when">날짜</Label>
                <Input id="freshen-when" type="date" value={when} onChange={(e) => setWhen(e.target.value)} />
              </div>
              <Button size="sm" onClick={() => bring(true)} disabled={pending} data-testid="import-freshen">
                올해 것으로 만들기
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <p className="mr-auto text-xs text-muted-foreground">
              작년 것을 <strong>그대로</strong> 보고 싶으실 때는 이쪽입니다 (곡과 멘트까지 전부).
            </p>
            <Button variant="outline" size="sm" onClick={() => bring(false)} disabled={pending} data-testid="import-asis">
              그대로 가져오기
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setPicked(null)} disabled={pending}>
              취소
            </Button>
          </div>
        </div>
      )}

      {message && <p className="text-sm text-muted-foreground">{message}</p>}
    </div>
  )
}
