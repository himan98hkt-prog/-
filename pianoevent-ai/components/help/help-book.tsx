'use client'

import { Printer, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import type { HelpSection } from '@/lib/help/markdown'
import { cn } from '@/lib/utils'

/**
 * 설명서 보기.
 *
 * 왼쪽에 차례, 오른쪽에 본문. 찾는 칸에 한 낱말만 치면 그 낱말이 든 절만 남는다 —
 * 800줄짜리 설명서를 처음부터 읽으시게 할 수는 없다.
 * 인쇄하면 **전부** 나온다 (골라 둔 절만이 아니라).
 */
export function HelpBook({ sections }: { sections: HelpSection[] }) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(sections[0]?.id ?? '')

  const found = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return sections
    return sections.filter(
      (row) => row.title.toLowerCase().includes(needle) || row.html.toLowerCase().includes(needle),
    )
  }, [sections, query])

  const current = found.find((row) => row.id === active) ?? found[0] ?? null

  return (
    <div className="grid gap-5 lg:grid-cols-[260px_1fr]">
      <aside className="no-print lg:sticky lg:top-20 lg:self-start">
        <div className="relative mb-2">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(native) => setQuery(native.target.value)}
            placeholder="찾기 — 예: 명단, 인쇄, 영상"
            aria-label="설명서에서 찾기"
            className="h-9 w-full rounded-md border border-border bg-background pl-8 pr-2 text-sm"
          />
        </div>
        <nav className="max-h-[60vh] overflow-y-auto rounded-lg border border-border" data-testid="help-toc">
          {found.length === 0 ? (
            <p className="px-3 py-6 text-center text-xs text-muted-foreground">그런 말이 든 곳이 없습니다.</p>
          ) : (
            <ol>
              {found.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    onClick={() => setActive(row.id)}
                    className={cn(
                      'block w-full border-b border-border/60 px-3 py-2 text-left text-sm last:border-0',
                      row.id === current?.id ? 'bg-accent/10 font-medium' : 'hover:bg-secondary',
                    )}
                  >
                    {row.title}
                  </button>
                </li>
              ))}
            </ol>
          )}
        </nav>
        <Button variant="outline" size="sm" className="mt-2 w-full" onClick={() => window.print()}>
          <Printer className="mr-1 h-4 w-4" />
          설명서 전체 인쇄
        </Button>
        <p className="mt-1.5 text-xs text-muted-foreground">
          인쇄하면 <strong>전부</strong> 나옵니다. 한 부 뽑아 두시면 컴퓨터를 켜지 않고도 보실 수 있습니다.
        </p>
      </aside>

      {/* 화면에서는 고른 절만, 인쇄할 때는 전부 */}
      <article data-testid="help-body">
        <div className="help-prose no-print">
          {current && (
            <>
              <h2>{current.title}</h2>
              <div dangerouslySetInnerHTML={{ __html: current.html }} />
            </>
          )}
        </div>
        <div className="help-prose hidden print:block">
          {sections.map((row) => (
            <section key={row.id}>
              <h2>{row.title}</h2>
              <div dangerouslySetInnerHTML={{ __html: row.html }} />
            </section>
          ))}
        </div>
      </article>
    </div>
  )
}
