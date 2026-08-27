'use client'

import { Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import {
  DESIGN_THEMES,
  FAMILY_LABEL,
  FAMILY_ORDER,
  getTheme,
  searchThemes,
  seasonalThemeIds,
  themesByFamily,
  type ThemeFamily,
} from '@/lib/design/themes'
import { eventMonth } from '@/lib/format'
import { cn } from '@/lib/utils'

/** 테마 색 세 점 — 이름만으로는 감이 오지 않는다 */
export function ThemeSwatch({ id, size = 4 }: { id: string; size?: number }) {
  const theme = getTheme(id)
  return (
    <span className="flex gap-1" aria-hidden>
      {[theme.palette.paper, theme.palette.band, theme.palette.accent].map((color, index) => (
        <span
          key={index}
          className="rounded-full border border-black/10"
          style={{ background: color, width: size * 4, height: size * 4 }}
        />
      ))}
    </span>
  )
}

/**
 * 테마 100종 고르기.
 *
 * 인쇄물 화면과 무대 화면이 같은 것을 쓴다 — 두 곳에서 고르는 방법이 다르면
 * 원장님은 "왜 여기선 안 되지" 하고 멈춘다.
 */
export function ThemePicker({
  value,
  onChange,
  eventAt,
  compact = false,
}: {
  value: string
  onChange: (id: string) => void
  /** 행사 날짜 — 그 달에 어울리는 테마를 먼저 보여 준다 */
  eventAt: string
  /** 무대 화면처럼 자리가 좁을 때 목록 높이를 제한한다 */
  compact?: boolean
}) {
  const [family, setFamily] = useState<ThemeFamily>(getTheme(value).family)
  const [query, setQuery] = useState('')

  const suggested = useMemo(() => {
    const ids = seasonalThemeIds(eventMonth(eventAt))
    return ids.map((id) => DESIGN_THEMES.find((t) => t.id === id)).filter(Boolean) as typeof DESIGN_THEMES
  }, [eventAt])

  const pick = (id: string, nextFamily: ThemeFamily) => {
    onChange(id)
    setFamily(nextFamily)
  }

  const found = query.trim() ? searchThemes(query) : []

  return (
    <div className="grid gap-3">
      <div className="rounded-md border border-accent/30 bg-accent/5 p-3">
        <p className="mb-2 flex items-center gap-1.5 text-xs font-medium">
          <Sparkles className="h-3.5 w-3.5 text-accent" aria-hidden />이 시기에 어울리는 테마
        </p>
        <div className="flex flex-wrap gap-1.5">
          {suggested.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => pick(item.id, item.family)}
              aria-pressed={item.id === value}
              className={cn(
                'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors',
                item.id === value
                  ? 'border-accent bg-accent/10 font-medium'
                  : 'border-border bg-background hover:bg-secondary',
              )}
            >
              <span
                className="h-3 w-3 rounded-full border border-black/10"
                style={{ background: item.palette.accent }}
                aria-hidden
              />
              {item.name}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {FAMILY_ORDER.map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => setFamily(id)}
            aria-pressed={id === family}
            className={cn(
              'rounded-full border px-3 py-1 text-xs transition-colors',
              id === family
                ? 'border-accent bg-accent/10 font-medium text-foreground'
                : 'border-border text-muted-foreground hover:bg-secondary',
            )}
          >
            {FAMILY_LABEL[id]} {DESIGN_THEMES.filter((t) => t.family === id).length}
          </button>
        ))}
      </div>

      <input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="테마 찾기 — 봄, 금색, 아이, 격식…"
        aria-label="테마 찾기"
        className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
      />

      <div className={cn('grid gap-1.5', compact && 'max-h-72 overflow-y-auto pr-1')}>
        {query.trim() ? (
          <>
            <p className="text-[11px] text-muted-foreground">
              &ldquo;{query.trim()}&rdquo; — {found.length}종
            </p>
            {found.map((item) => (
              <ThemeRow key={item.id} item={item} active={item.id === value} onPick={pick} note={item.tagline} />
            ))}
            {found.length === 0 && (
              <p className="rounded-md border border-dashed border-border px-3 py-4 text-center text-sm text-muted-foreground">
                맞는 테마가 없습니다. 다른 말로 찾아 보세요.
              </p>
            )}
          </>
        ) : (
          themesByFamily()
            .filter((group) => group.family === family)
            .map((group) => (
              <div key={group.family} className="grid gap-1.5">
                <p className="text-[11px] leading-relaxed text-muted-foreground">{group.hint}</p>
                {group.items.map((item) => (
                  <ThemeRow
                    key={item.id}
                    item={item}
                    active={item.id === value}
                    onPick={pick}
                    note={item.mood.join(' · ')}
                  />
                ))}
              </div>
            ))
        )}
      </div>
    </div>
  )
}

function ThemeRow({
  item,
  active,
  onPick,
  note,
}: {
  item: (typeof DESIGN_THEMES)[number]
  active: boolean
  onPick: (id: string, family: ThemeFamily) => void
  note: string
}) {
  return (
    <button
      type="button"
      onClick={() => onPick(item.id, item.family)}
      aria-pressed={active}
      className={cn(
        'flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-left text-sm transition-colors',
        active ? 'border-accent bg-accent/8 font-medium' : 'border-border hover:bg-secondary',
      )}
    >
      <span className="min-w-0">
        <span className="block truncate">{item.name}</span>
        <span className="block truncate text-[11px] text-muted-foreground">{note}</span>
      </span>
      <ThemeSwatch id={item.id} />
    </button>
  )
}
