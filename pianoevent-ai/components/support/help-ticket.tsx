'use client'

import { Check, Copy, Download, LifeBuoy } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/field'
import { buildReport } from '@/lib/support/report'

/** 화면에서 난 오류를 이 자리에 모아 둔다 — 원장님이 받아 적으실 수는 없다 */
const ERROR_KEY = 'pianoevent.errors'

function recentErrors(): string[] {
  try {
    const raw = window.sessionStorage.getItem(ERROR_KEY)
    const list = raw ? JSON.parse(raw) : []
    return Array.isArray(list) ? list.filter((v): v is string => typeof v === 'string') : []
  } catch {
    return []
  }
}

/**
 * "막히면 여기".
 *
 * 막히셨을 때 오는 연락은 늘 "안 돼요" 한 줄이다. 그것만으로는 아무것도 못 한다.
 * 그렇다고 화면을 찍어 보내시라고 할 수도 없다 — 아이들 이름과 얼굴이 함께 나간다.
 *
 * 그래서 저희가 쪽지를 대신 써 드린다. 원장님은 "무엇을 하셨을 때" 한 줄만 적으시면
 * 되고, 나머지(판·브라우저·화면·오류·규모)는 프로그램이 채운다. 무엇이 담겼는지
 * 그대로 보여 드리고 — 보내실지는 원장님이 정하신다.
 */
export function HelpTicket() {
  const [note, setNote] = useState('')
  const [info, setInfo] = useState<{ version: string; driver: 'demo' | 'supabase'; counts: Record<string, number> }>({
    version: '—',
    driver: 'demo',
    counts: {},
  })
  const [errors, setErrors] = useState<string[]>([])
  const [copied, setCopied] = useState(false)
  // 브라우저 이름·화면 크기·주소는 서버에서 알 수 없다. 서버에서 한 번 그리고 브라우저에서
  // 다시 그릴 때 글이 달라지면 React 가 화면을 통째로 버린다(hydration). 그래서 붙고 난
  // 다음에만 쪽지를 만든다.
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    setErrors(recentErrors())
    fetch('/api/support/info')
      .then((res) => res.json())
      .then((data) => {
        if (data?.version) setInfo(data)
      })
      .catch(() => {
        /* 못 가져와도 쪽지는 만들어진다 */
      })
  }, [])

  const report = mounted
    ? buildReport({
        path: window.location.pathname,
        version: info.version,
        driver: info.driver,
        userAgent: navigator.userAgent,
        screen: `${window.screen?.width ?? 0}×${window.screen?.height ?? 0}`,
        online: navigator.onLine,
        note,
        errors,
        counts: info.counts,
      })
    : '쪽지를 준비하고 있습니다…'

  async function copy() {
    try {
      await navigator.clipboard.writeText(report)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      /* 복사가 막힌 브라우저 — 아래 글을 직접 긁어 복사하시면 된다 */
    }
  }

  function save() {
    const blob = new Blob([report], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '막힌자리.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className="grid gap-3 rounded-lg border border-border bg-card p-4" data-testid="help-ticket">
      <div>
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <LifeBuoy className="h-4 w-4 text-accent" aria-hidden />
          막히면 여기
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          무엇을 하셨을 때 막히셨는지 한 줄만 적어 주세요. 나머지는 저희가 채웁니다.{' '}
          <strong className="text-foreground">아이 이름과 사진은 담기지 않습니다</strong> — 담긴 것을 아래에서 그대로
          보실 수 있습니다.
        </p>
      </div>

      <div>
        <label htmlFor="ticket-note" className="text-sm font-medium">
          무엇을 하셨을 때 막히셨나요?
        </label>
        <Textarea
          id="ticket-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="예) 명단을 붙여넣고 [AI 순서표 만들기] 를 눌렀는데 아무 일도 일어나지 않습니다."
          className="mt-1.5 min-h-[80px]"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={copy} data-testid="ticket-copy">
          {copied ? <Check className="h-4 w-4" aria-hidden /> : <Copy className="h-4 w-4" aria-hidden />}
          {copied ? '복사했습니다' : '쪽지 복사하기'}
        </Button>
        <Button variant="outline" size="sm" onClick={save}>
          <Download className="h-4 w-4" aria-hidden />
          파일로 저장
        </Button>
      </div>

      <details className="rounded-md border border-border bg-muted/40 p-3">
        <summary className="cursor-pointer text-sm font-medium">무엇이 담겼는지 보기</summary>
        <pre
          className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs text-muted-foreground"
          data-testid="ticket-body"
        >
          {report}
        </pre>
      </details>
    </section>
  )
}
