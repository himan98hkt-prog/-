'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { DESIGN_THEMES, getTheme } from '@/lib/design/themes'
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
          logo_url: formData.get('logo_url'),
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
            <div>
              <Label htmlFor="logo_url">로고 이미지 주소 (선택)</Label>
              <Input id="logo_url" name="logo_url" defaultValue={academy.logo_url ?? ''} placeholder="https://..." />
              <FieldHint>Supabase Storage 등에 올린 이미지 URL 을 넣으세요.</FieldHint>
            </div>
          </div>

          <div>
            <Label>인쇄물 기본 테마</Label>
            <FieldHint className="mb-2 mt-0">
              포스터·순서지·입장권·상장에 공통으로 쓰입니다. 행사마다 다르게 고를 수도 있습니다.
            </FieldHint>
            <div className="grid gap-1.5 sm:grid-cols-2">
              {DESIGN_THEMES.map((theme) => {
                const active = theme.id === designTheme
                return (
                  <button
                    key={theme.id}
                    type="button"
                    onClick={() => setDesignTheme(theme.id)}
                    aria-pressed={active}
                    className={cn(
                      'flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-left text-sm transition-colors',
                      active ? 'border-accent bg-accent/8 font-medium' : 'border-border hover:bg-secondary',
                    )}
                  >
                    <span className="min-w-0">
                      <span className="block truncate">{theme.name}</span>
                      <span className="block truncate text-[11px] text-muted-foreground">{theme.mood.join(' · ')}</span>
                    </span>
                    <span className="flex shrink-0 gap-1" aria-hidden>
                      {[theme.palette.paper, theme.palette.band, theme.palette.accent].map((color, index) => (
                        <span
                          key={index}
                          className="h-4 w-4 rounded-full border border-black/10"
                          style={{ background: color }}
                        />
                      ))}
                    </span>
                  </button>
                )
              })}
            </div>
            <FieldHint>선택: {getTheme(designTheme).tagline}</FieldHint>
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
