'use client'

import { Sparkles } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import { Input } from '@/components/ui/field'
import { formatDuration } from '@/lib/format'
import { searchPieces, type CatalogEntry } from '@/lib/program/catalog'
import { LEVEL_LABEL } from '@/lib/types'
import { cn } from '@/lib/utils'

/**
 * 곡 제목 입력칸 — 곡 사전 자동완성.
 *
 * 원장이 곡 제목 몇 글자만 치면 작곡가·난이도·연주시간까지 함께 들어간다.
 * 사전에 없는 곡도 그냥 적으면 된다. 방해하지 않는 것이 이 입력칸의 첫째 규칙이다.
 */
export function PieceInput({
  name,
  value,
  onChange,
  onPick,
  placeholder = '엘리제를 위하여',
  className,
  id,
}: {
  name?: string
  value: string
  onChange: (next: string) => void
  /** 사전에서 고른 경우 — 나머지 칸을 함께 채우라는 뜻 */
  onPick: (entry: CatalogEntry) => void
  placeholder?: string
  className?: string
  id?: string
}) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const matches = useMemo(() => (open ? searchPieces(value) : []), [open, value])
  const visible = open && matches.length > 0

  function pick(entry: CatalogEntry) {
    onChange(entry.title)
    onPick(entry)
    setOpen(false)
  }

  return (
    <div className="relative">
      <Input
        id={id}
        name={name}
        value={value}
        autoComplete="off"
        placeholder={placeholder}
        className={className}
        onChange={(e) => {
          onChange(e.target.value)
          setOpen(true)
          setActive(0)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => {
          // 목록을 누르는 중에 닫히지 않게 한 박자 늦춘다
          blurTimer.current = setTimeout(() => setOpen(false), 140)
        }}
        onKeyDown={(e) => {
          if (!visible) return
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setActive((i) => (i + 1) % matches.length)
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setActive((i) => (i - 1 + matches.length) % matches.length)
          } else if (e.key === 'Enter') {
            e.preventDefault()
            pick(matches[active])
          } else if (e.key === 'Escape') {
            setOpen(false)
          }
        }}
        aria-expanded={visible}
        aria-autocomplete="list"
        role="combobox"
      />

      {visible && (
        <ul
          role="listbox"
          className="absolute left-0 right-0 top-full z-30 mt-1 max-h-64 overflow-y-auto rounded-md border border-border bg-background shadow-lg"
        >
          <li className="flex items-center gap-1.5 border-b border-border px-3 py-1.5 text-xs text-muted-foreground">
            <Sparkles className="h-3 w-3 text-accent" aria-hidden />
            곡을 고르면 작곡가 · 난이도 · 연주시간이 함께 들어갑니다
          </li>
          {matches.map((entry, index) => (
            <li key={entry.title} role="option" aria-selected={index === active}>
              <button
                type="button"
                onMouseEnter={() => setActive(index)}
                onMouseDown={(e) => {
                  // blur 보다 먼저 처리해 목록이 닫히기 전에 고른다
                  e.preventDefault()
                  if (blurTimer.current) clearTimeout(blurTimer.current)
                  pick(entry)
                }}
                className={cn(
                  'flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left text-sm transition-colors',
                  index === active ? 'bg-accent/10' : 'hover:bg-secondary',
                )}
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium">{entry.title}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {entry.composer} · {LEVEL_LABEL[entry.level]}
                  </span>
                </span>
                <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
                  {formatDuration(entry.duration_sec)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
