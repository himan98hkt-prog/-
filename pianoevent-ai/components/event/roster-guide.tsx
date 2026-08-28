'use client'

import { ChevronDown, Download, FileSpreadsheet } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  LEVEL_WORDS,
  ROSTER_FIELDS,
  ROSTER_HEADERS,
  ROSTER_PITFALLS,
  ROSTER_SAMPLE,
} from '@/lib/program/template'
import { LEVEL_LABEL, type Level } from '@/lib/types'
import { cn } from '@/lib/utils'

/**
 * 명단 넣는 법 안내.
 *
 * 원장님이 가장 자주 멈추는 자리다. "붙여넣으세요" 만으로는 무엇을 어떤 차례로
 * 적어야 하는지 알 수 없다. 그래서 세 가지를 한자리에 둔다.
 *   · **양식 파일**을 내려받아 엑셀에서 이름만 바꾸기 (가장 쉬운 길)
 *   · 칸마다 무엇을 적는지, 비우면 어떻게 되는지
 *   · 자주 하는 실수
 *
 * 자세한 설명은 접어 둔다 — 처음 보는 화면에 글이 가득하면 그것대로 막힌다.
 */
export function RosterGuide() {
  const [open, setOpen] = useState(false)

  return (
    <div className="grid gap-3 rounded-lg border border-accent/40 bg-accent/5 p-4" data-testid="roster-guide">
      <div className="flex flex-wrap items-start gap-3">
        <FileSpreadsheet className="mt-0.5 h-5 w-5 shrink-0 text-accent" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">가장 쉬운 길 — 양식 파일에 이름만 바꿔 넣으세요</p>
          <p className="mt-1 text-sm text-muted-foreground">
            아래 단추를 누르면 <strong>예시가 채워진 엑셀 파일</strong>이 내려옵니다. 그 파일을 열어 예시 줄을
            지우고 우리 아이들 이름으로 바꾸신 뒤 <strong>저장</strong>하세요. 그 파일을 아래 상자에{' '}
            <strong>끌어다 놓으시면</strong> 끝입니다 — 복사·붙여넣기를 하지 않으셔도 됩니다.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <a
          href="/api/roster-template"
          download="학생명단 양식.csv"
          className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Download className="mr-1 h-4 w-4" />
          명단 양식 내려받기
        </a>
        <Button variant="ghost" size="sm" onClick={() => setOpen((prev) => !prev)} aria-expanded={open}>
          <ChevronDown className={cn('mr-1 h-4 w-4 transition-transform', open && 'rotate-180')} />
          {open ? '자세한 설명 접기' : '칸마다 무엇을 적나요?'}
        </Button>
      </div>

      {/* 표 모양 미리 보여 주기 — 글로 열 줄 적는 것보다 한 번 보는 편이 빠르다 */}
      <div className="overflow-x-auto rounded-md border border-border bg-background">
        <table className="w-full min-w-[560px] text-xs">
          <thead>
            <tr className="border-b border-border bg-secondary/60">
              {ROSTER_HEADERS.map((head) => (
                <th key={head} className="px-2.5 py-1.5 text-left font-medium">
                  {head}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROSTER_SAMPLE.map((row, index) => (
              <tr key={index} className="border-b border-border/60 last:border-0">
                {row.map((cell, at) => (
                  <td key={at} className={cn('px-2.5 py-1.5', !cell && 'text-muted-foreground')}>
                    {cell || '(비워도 됨)'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        <strong>이름 한 칸</strong>만 있으면 나머지는 나중에 채우셔도 됩니다. 머리글(이름·연주곡…)이 없어도
        이 차례대로 읽습니다.
      </p>

      {open && (
        <div className="grid gap-3 border-t border-border pt-3" data-testid="roster-guide-detail">
          <div className="grid gap-2">
            {ROSTER_FIELDS.map((field) => (
              <div key={field.name} className="grid gap-0.5 rounded-md bg-background px-3 py-2">
                <p className="text-sm font-medium">
                  {field.name}
                  {field.required ? (
                    <span className="ml-1.5 rounded bg-accent px-1.5 py-0.5 text-[10px] text-accent-foreground">
                      꼭 필요
                    </span>
                  ) : (
                    <span className="ml-1.5 text-xs font-normal text-muted-foreground">비워도 됨</span>
                  )}
                  <span className="ml-2 text-xs font-normal text-muted-foreground">예: {field.example}</span>
                </p>
                <p className="text-xs text-muted-foreground">{field.what}</p>
                <p className="text-xs text-muted-foreground">
                  <span className="text-foreground">비우면</span> — {field.blank}
                </p>
              </div>
            ))}
          </div>

          <div className="rounded-md bg-background px-3 py-2">
            <p className="text-sm font-medium">난이도 칸에 적을 수 있는 말</p>
            <ul className="mt-1 grid gap-0.5 text-xs text-muted-foreground">
              {(Object.keys(LEVEL_LABEL) as Level[]).map((level) => (
                <li key={level}>
                  <strong className="text-foreground">{LEVEL_LABEL[level]}</strong> —{' '}
                  {LEVEL_WORDS[level].map((word) => `"${word}"`).join(', ')}
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-md bg-background px-3 py-2">
            <p className="text-sm font-medium">자주 하는 실수</p>
            <ul className="mt-1 grid gap-1 text-xs">
              {ROSTER_PITFALLS.map((row) => (
                <li key={row.wrong}>
                  <span className="text-destructive">✕ {row.wrong}</span>
                  <span
                    className="ml-1.5 text-muted-foreground"
                    dangerouslySetInnerHTML={{
                      __html: row.why.replace(
                        /\*\*([^*]+)\*\*/g,
                        '<strong class="text-foreground">$1</strong>',
                      ).replace(/`([^`]+)`/g, '<code class="rounded bg-secondary px-1">$1</code>'),
                    }}
                  />
                </li>
              ))}
            </ul>
          </div>

          <p className="text-xs text-muted-foreground">
            더 자세한 것은{' '}
            <a href="/help" className="underline underline-offset-4">
              사용설명서
            </a>
            에 있습니다.
          </p>
        </div>
      )}
    </div>
  )
}
