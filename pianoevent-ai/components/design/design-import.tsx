'use client'

import { Check, History, Loader2 } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { Button } from '@/components/ui/button'

/** 디자인을 저장해 둔 지난 행사 */
export interface PastDesign {
  id: string
  title: string
  /** 무엇이 들어 있는지 한 줄로 — 고르기 전에 보인다 */
  summary: string
}

/**
 * 지난 행사의 인쇄물 설정을 그대로 가져온다.
 *
 * 명단에는 "지난 행사에서 가져오기" 가 있었는데 디자인만 매번 처음부터였다.
 * 학원은 해마다 같은 얼굴이다 — 작년에 맞춰 둔 테마·양식·문구를 다시 고를 이유가 없다.
 */
export function DesignImport({ eventId, past }: { eventId: string; past: PastDesign[] }) {
  const router = useRouter()
  const [source, setSource] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [copy, setCopy] = useState(true)
  const [images, setImages] = useState(true)

  if (past.length === 0) return null

  async function load() {
    if (!source) return
    setBusy(true)
    setMessage(null)
    try {
      const res = await fetch(`/api/events/${eventId}/design-import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from_event_id: source, copy, images }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '가져오지 못했습니다.')
      setMessage('가져왔습니다. 아래 미리보기가 그 디자인으로 바뀝니다.')
      router.refresh()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '가져오지 못했습니다.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="grid gap-2 rounded-lg border border-border p-3" data-testid="design-import">
      <p className="flex items-center gap-2 text-sm font-medium">
        <History className="h-4 w-4 text-accent" aria-hidden />
        지난 행사에서 디자인 가져오기
      </p>
      <p className="text-xs text-muted-foreground">
        작년에 맞춰 두신 <strong>테마 · 양식 · 문구 · 사진 지정</strong>을 그대로 가져옵니다. 무대 화면과 영상
        설정도 저장해 두셨다면 함께 따라옵니다.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={source}
          onChange={(native) => setSource(native.target.value)}
          className="h-9 min-w-[200px] flex-1 rounded-md border border-border bg-background px-2 text-sm"
          aria-label="디자인을 가져올 행사"
        >
          <option value="">행사를 고르세요</option>
          {past.map((item) => (
            <option key={item.id} value={item.id}>
              {item.title} · {item.summary}
            </option>
          ))}
        </select>
        <Button size="sm" variant="outline" onClick={() => void load()} disabled={busy || !source}>
          {busy ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Check className="mr-1 h-4 w-4" />}
          가져오기
        </Button>
      </div>
      <div className="flex flex-wrap gap-4 text-xs">
        <label className="flex cursor-pointer items-center gap-1.5">
          <input type="checkbox" checked={copy} onChange={(e) => setCopy(e.target.checked)} className="h-3.5 w-3.5" />
          문구까지 (부제 · 주최 · 문의 · 안내)
        </label>
        <label className="flex cursor-pointer items-center gap-1.5">
          <input
            type="checkbox"
            checked={images}
            onChange={(e) => setImages(e.target.checked)}
            className="h-3.5 w-3.5"
          />
          사진 지정까지 (보관함에 남아 있는 것만)
        </label>
      </div>
      {message && <p className="text-xs text-muted-foreground">{message}</p>}
    </section>
  )
}
