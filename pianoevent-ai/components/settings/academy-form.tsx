'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { DESIGN_THEMES, FAMILY_LABEL, FAMILY_ORDER, getTheme, themesByFamily, type ThemeFamily } from '@/lib/design/themes'
import { ThemeSketch } from '@/components/design/theme-sketch'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldHint, Input, Label } from '@/components/ui/field'
import type { Academy } from '@/lib/types'

export function AcademyForm({ academy }: { academy: Academy }) {
  const router = useRouter()
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [designTheme, setDesignTheme] = useState(academy.design_theme ?? 'classic-navy')
  const [family, setFamily] = useState<ThemeFamily>(getTheme(academy.design_theme ?? 'classic-navy').family)
  /** 테마 서른두 개는 바꾸실 때만 편다 — 행사마다 따로 고를 수 있어 여기 것은 한 번이면 끝난다 */
  const [themeOpen, setThemeOpen] = useState(false)

  async function save(formData: FormData) {
    setPending(true)
    setMessage(null)
    try {
      const res = await fetch('/api/academy', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formData.get('name'),
          director_name: formData.get('director_name'),
          theme_color: formData.get('theme_color'),
          design_theme: designTheme,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '저장하지 못했습니다.')
      setMessage('저장했습니다.')
      router.refresh()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '저장하지 못했습니다.')
    } finally {
      setPending(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>학원 정보</CardTitle>
        <CardDescription>순서표·초대장·대본에 그대로 인쇄됩니다.</CardDescription>
      </CardHeader>
      <CardContent>
        <form action={save} className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="name">학원명</Label>
              <Input id="name" name="name" defaultValue={academy.name} required maxLength={60} />
            </div>
            <div>
              <Label htmlFor="director_name">원장 성함</Label>
              <Input id="director_name" name="director_name" defaultValue={academy.director_name} maxLength={40} />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="theme_color">테마 색상</Label>
              <Input
                id="theme_color"
                name="theme_color"
                type="color"
                defaultValue={academy.theme_color}
                className="h-10 w-24 p-1"
              />
            </div>
          </div>

          <div>
            <Label>인쇄물 기본 테마</Label>
            <FieldHint className="mb-2 mt-0">
              포스터·순서지·입장권·상장에 공통으로 쓰입니다. 행사마다 다르게 고를 수도 있습니다.
            </FieldHint>
            {/*
              학원 정보를 고치러 오신 분께 테마 서른두 개를 펼쳐 보일 이유가 없다.
              게다가 행사마다 따로 고르실 수 있어, 여기 것은 처음 한 번이면 끝난다.
            */}
            <button
              type="button"
              onClick={() => setThemeOpen((on) => !on)}
              aria-expanded={themeOpen}
              className="mb-3 flex w-full items-center justify-between gap-2 rounded-md border border-border px-3 py-2 text-left text-sm hover:bg-secondary"
              data-testid="settings-theme-toggle"
            >
              <span>
                지금은 <strong>{getTheme(designTheme).name}</strong>
                <span className="ml-1.5 text-xs text-muted-foreground">{getTheme(designTheme).tagline}</span>
              </span>
              <span className="shrink-0 text-xs text-muted-foreground">{themeOpen ? '닫기' : '바꾸기'}</span>
            </button>
            <div className={cn(!themeOpen && 'hidden')} data-testid="settings-themes">
            <div className="mb-3 flex flex-wrap gap-1.5">
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
            {/* 인쇄물 화면과 **같은 방식**으로 고르셔야 한다 — 두 곳이 다르면 "왜 여기선 안 되지" 하고 멈추신다 */}
            <div className="grid gap-4">
              {themesByFamily()
                .filter((group) => group.family === family)
                .map((group) => (
                  <div key={group.family}>
                    <p className="mb-1.5 text-xs leading-relaxed text-muted-foreground">{group.hint}</p>
                    <div className="grid grid-cols-3 gap-2 sm:grid-cols-4" data-testid="settings-theme-grid">
                      {group.items.map((theme) => {
                        const active = theme.id === designTheme
                        return (
                          <button
                            key={theme.id}
                            type="button"
                            onClick={() => setDesignTheme(theme.id)}
                            aria-pressed={active}
                            title={theme.tagline}
                            className={cn(
                              'grid justify-items-center gap-1 rounded-md border p-1.5 transition-colors',
                              active ? 'border-accent bg-accent/8' : 'border-border hover:bg-secondary',
                            )}
                          >
                            <ThemeSketch id={theme.id} width={82} />
                            <span className={cn('block w-full text-center text-xs leading-tight', active && 'font-medium')}>
                              {theme.name}
                            </span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                ))}
            </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button type="submit" disabled={pending}>
              {pending ? '저장 중…' : '저장'}
            </Button>
            {message && <span className="text-sm text-muted-foreground">{message}</span>}
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
