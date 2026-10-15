'use client'

import { Check, History, Loader2, Save } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { hasPrefs, type Prefs } from '@/lib/prefs'

/** 설정을 저장해 둔 지난 행사 */
export interface PastPrefs {
  id: string
  title: string
  prefs: Prefs
}

/**
 * 고른 설정을 행사에 저장하고, 지난 행사 것을 그대로 불러온다.
 *
 * 원장님은 테마를 고르고 배경을 맞추고 글자 자리를 잡는 데 한참을 쓰신다.
 * 그런데 창을 닫으면 전부 사라졌다 — 다음 해에 또 처음부터.
 * 사진은 이미 보관함에 남아 있으니, 설정만 붙들어 두면 작년 것이 그대로 열린다.
 */
export function PrefsBar({
  eventId,
  field,
  prefs,
  saved,
  past = [],
  onLoad,
  label,
}: {
  eventId: string
  /** 어느 칸에 저장할지 */
  field: 'stage_prefs' | 'video_prefs'
  /** 지금 화면에서 고른 값 */
  prefs: Prefs
  /** 이 행사에 이미 저장돼 있던 값 */
  saved: Prefs | null
  /** 같은 설정을 저장해 둔 지난 행사들 */
  past?: PastPrefs[]
  onLoad: (prefs: Prefs) => void
  /** "무대 화면 설정" 처럼 무엇을 저장하는지 */
  label: string
}) {
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [source, setSource] = useState('')

  async function save() {
    setBusy(true)
    setError(null)
    setDone(false)
    try {
      const res = await fetch(`/api/events/${eventId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: prefs }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '저장하지 못했습니다.')
      setDone(true)
      // 저장했다는 표시는 잠깐만 — 계속 붙어 있으면 방금 저장한 것인지 헷갈린다
      window.setTimeout(() => setDone(false), 2600)
    } catch (e) {
      setError(e instanceof Error ? e.message : '저장하지 못했습니다.')
    } finally {
      setBusy(false)
    }
  }

  const usable = past.filter((item) => hasPrefs(item.prefs))

  return (
    <section className="grid gap-2 rounded-lg border border-border p-3" data-testid={`prefs-${field}`}>
      <p className="text-sm font-medium">
        {label} 저장
        <span className="ml-1.5 text-xs font-normal text-muted-foreground">
          다음에 열면 이 설정 그대로 시작합니다
        </span>
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="outline" onClick={() => void save()} disabled={busy}>
          {busy ? (
            <Loader2 className="mr-1 h-4 w-4 animate-spin" />
          ) : done ? (
            <Check className="mr-1 h-4 w-4 text-accent" />
          ) : (
            <Save className="mr-1 h-4 w-4" />
          )}
          {done ? '저장했습니다' : '이 설정 저장'}
        </Button>
        {saved && Object.keys(saved).length > 0 && (
          <Button size="sm" variant="ghost" onClick={() => onLoad(saved)}>
            저장해 둔 값으로 되돌리기
          </Button>
        )}
      </div>

      {usable.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-2">
          <History className="h-4 w-4 text-accent" aria-hidden />
          <select
            value={source}
            onChange={(native) => setSource(native.target.value)}
            className="h-9 min-w-[180px] flex-1 rounded-md border border-border bg-background px-2 text-sm"
            aria-label="지난 행사 설정 고르기"
          >
            <option value="">지난 행사에서 불러오기</option>
            {usable.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            variant="outline"
            disabled={!source}
            onClick={() => {
              const found = usable.find((item) => item.id === source)
              if (found) onLoad(found.prefs)
            }}
          >
            불러오기
          </Button>
        </div>
      )}

      {error && <p className="text-xs text-destructive">{error}</p>}
      <p className="text-xs text-muted-foreground">
        저장되는 것은 <strong>고른 설정</strong>뿐입니다 — 테마·배경·길이·문구. 사진은 이미 보관함에 있습니다.
      </p>
    </section>
  )
}
