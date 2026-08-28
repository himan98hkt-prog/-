'use client'

import { Download, Upload } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { bundleSummary, parseBundle } from '@/lib/events/transfer'
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

  async function take(file: File) {
    setPending(true)
    setMessage(null)
    try {
      const text = await file.text()
      // 서버에 보내기 전에 여기서 먼저 읽어 본다 — 엉뚱한 파일이면 그 자리에서 말씀드린다
      const bundle = parseBundle(text)
      const res = await fetch('/api/events/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '가져오지 못했습니다.')
      const skipped =
        data.skipped_photos > 0 ? ` 보관함이 꽉 차서 사진 ${data.skipped_photos}장은 넣지 못했습니다.` : ''
      setMessage(`${bundleSummary(bundle)} — 새 행사로 들여왔습니다.${skipped}`)
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
      {message && <p className="text-sm text-muted-foreground">{message}</p>}
    </div>
  )
}
