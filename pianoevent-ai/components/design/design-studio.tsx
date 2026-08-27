'use client'

import { Check, Printer, Save, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import { ImagePicker } from '@/components/design/image-picker'
import { renderTemplate } from '@/components/design/render'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldHint, Input, Label } from '@/components/ui/field'
import { resolveLogo, resolvePhoto, type ImageMap } from '@/lib/assets'
import type { DesignCopy } from '@/lib/design/context'
import {
  CATEGORY_LABEL,
  DESIGN_TEMPLATES,
  PAGE_PX,
  PRINT_PACKS,
  getTemplate,
  sheetCount,
  templatesByCategory,
  type TemplateCategory,
  type TemplateDef,
} from '@/lib/design/templates'
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
import type { Academy, EventRecord, ProgramPlan, Rsvp } from '@/lib/types'
import { cn } from '@/lib/utils'

const PREVIEW_WIDTH = 520
const DESIGN_TEMPLATE_COUNT = DESIGN_TEMPLATES.length

function ThemeSwatch({ id }: { id: string }) {
  const theme = getTheme(id)
  return (
    <span className="flex gap-1" aria-hidden>
      {[theme.palette.paper, theme.palette.band, theme.palette.accent].map((color, index) => (
        <span
          key={index}
          className="h-4 w-4 rounded-full border border-black/10"
          style={{ background: color }}
        />
      ))}
    </span>
  )
}

export function DesignStudio({
  academy,
  event,
  plan,
  rsvps,
  inviteUrl,
  initialCopy,
}: {
  academy: Academy
  event: EventRecord
  plan: ProgramPlan
  rsvps: Rsvp[]
  inviteUrl: string
  initialCopy: DesignCopy
}) {
  const [templateId, setTemplateId] = useState(event.design_template ?? 'poster-classic')
  const [themeId, setThemeId] = useState(event.design_theme ?? academy.design_theme ?? 'classic-navy')
  const [copy, setCopy] = useState<DesignCopy>(initialCopy)
  const [photoUrl, setPhotoUrl] = useState(event.photo_url ?? '')
  const [imageMap, setImageMap] = useState<ImageMap>(event.image_map ?? {})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  // 양식 40종·테마 100종을 한 목록에 늘어놓으면 고를 수가 없다. 묶음을 먼저 고른다.
  const [category, setCategory] = useState<TemplateCategory>(getTemplate(event.design_template ?? 'poster-classic').category)
  const [themeQuery, setThemeQuery] = useState('')
  const [family, setFamily] = useState<ThemeFamily>(
    getTheme(event.design_theme ?? academy.design_theme ?? 'classic-navy').family,
  )

  // 행사 달에 맞는 계절 테마 — 40종을 다 훑지 않아도 되게
  const suggested = useMemo(() => {
    const ids = seasonalThemeIds(eventMonth(event.event_at))
    return ids.map((id) => DESIGN_THEMES.find((t) => t.id === id)).filter(Boolean) as typeof DESIGN_THEMES
  }, [event.event_at])

  const template = getTemplate(templateId)
  const theme = useMemo(() => getTheme(themeId), [themeId])
  const ctx = useMemo(
    // 미리보기에서는 로고·사진이 없어도 자리를 표시해 어디에 들어가는지 보이게 한다
    () => ({
      theme,
      academy,
      event,
      plan,
      copy,
      inviteUrl,
      logoUrl: resolveLogo(academy.assets ?? [], imageMap, academy.logo_url),
      photoUrl: resolvePhoto(academy.assets ?? [], imageMap, template.category, [
        photoUrl,
        event.photo_url,
        academy.photo_url,
      ]),
      placeholder: true,
      rsvps,
    }),
    [theme, academy, event, plan, copy, inviteUrl, photoUrl, rsvps, imageMap, template.category],
  )

  const page = PAGE_PX[template.page]
  const scale = PREVIEW_WIDTH / page.w
  const sheets = sheetCount(templateId, plan.items.length)
  const blocked = template.needsProgram && plan.items.length === 0

  async function save() {
    setSaving(true)
    setSaved(false)
    try {
      await fetch(`/api/events/${event.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          design_theme: themeId,
          design_template: templateId,
          design_copy: copy,
          photo_url: photoUrl.trim(),
          image_map: imageMap,
        }),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2200)
    } finally {
      setSaving(false)
    }
  }

  const printUrl = `/events/${event.id}/design/print?template=${templateId}&theme=${themeId}`

  return (
    <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
      <div className="grid gap-5">
        <Card>
          <CardHeader>
            <CardTitle>양식 · {DESIGN_TEMPLATE_COUNT}종</CardTitle>
            <CardDescription>{template.description}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            <div className="flex flex-wrap gap-1.5">
              {templatesByCategory().map((group) => (
                <button
                  key={group.category}
                  type="button"
                  onClick={() => setCategory(group.category)}
                  aria-pressed={group.category === category}
                  className={cn(
                    'rounded-full border px-3 py-1 text-xs transition-colors',
                    group.category === category
                      ? 'border-accent bg-accent/10 font-medium text-foreground'
                      : 'border-border text-muted-foreground hover:bg-secondary',
                  )}
                >
                  {CATEGORY_LABEL[group.category]} {group.items.length}
                </button>
              ))}
            </div>

            <div className="grid gap-1.5">
              {(templatesByCategory().find((g) => g.category === category)?.items ?? []).map((item: TemplateDef) => {
                const active = item.id === templateId
                const needsProgram = item.needsProgram && plan.items.length === 0
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setTemplateId(item.id)}
                    aria-pressed={active}
                    className={cn(
                      'rounded-md border px-3 py-2 text-left text-sm transition-colors',
                      active ? 'border-accent bg-accent/8 font-medium' : 'border-border hover:bg-secondary',
                    )}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="min-w-0 truncate">{item.name}</span>
                      <span className="flex shrink-0 items-center gap-1.5">
                        {needsProgram && <span className="text-[10px] text-muted-foreground">순서표 필요</span>}
                        <span className="text-[10px] text-muted-foreground">{PAGE_PX[item.page].label}</span>
                      </span>
                    </span>
                    {active && (
                      <span className="mt-1 block text-[11px] leading-relaxed text-muted-foreground">
                        {item.description}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>테마 · {DESIGN_THEMES.length}종</CardTitle>
            <CardDescription>{getTheme(themeId).tagline}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            <div className="rounded-md border border-accent/30 bg-accent/5 p-3">
              <p className="mb-2 flex items-center gap-1.5 text-xs font-medium">
                <Sparkles className="h-3.5 w-3.5 text-accent" aria-hidden />이 시기에 어울리는 테마
              </p>
              <div className="flex flex-wrap gap-1.5">
                {suggested.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setThemeId(item.id)
                      setFamily(item.family)
                    }}
                    aria-pressed={item.id === themeId}
                    className={cn(
                      'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors',
                      item.id === themeId
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
              {FAMILY_ORDER.map((id) => {
                const count = DESIGN_THEMES.filter((t) => t.family === id).length
                return (
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
                    {FAMILY_LABEL[id]} {count}
                  </button>
                )
              })}
            </div>

            <div>
              <input
                type="search"
                value={themeQuery}
                onChange={(e) => setThemeQuery(e.target.value)}
                placeholder="테마 찾기 — 봄, 금색, 아이, 격식…"
                aria-label="테마 찾기"
                className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
              />
            </div>

            {themeQuery.trim() ? (
              <div className="grid gap-1.5">
                <p className="text-[11px] text-muted-foreground">
                  &ldquo;{themeQuery.trim()}&rdquo; — {searchThemes(themeQuery).length}종
                </p>
                {searchThemes(themeQuery).map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setThemeId(item.id)
                      setFamily(item.family)
                    }}
                    aria-pressed={item.id === themeId}
                    className={cn(
                      'flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-left text-sm transition-colors',
                      item.id === themeId ? 'border-accent bg-accent/8 font-medium' : 'border-border hover:bg-secondary',
                    )}
                  >
                    <span className="min-w-0">
                      <span className="block truncate">{item.name}</span>
                      <span className="block truncate text-[11px] text-muted-foreground">{item.tagline}</span>
                    </span>
                    <ThemeSwatch id={item.id} />
                  </button>
                ))}
                {searchThemes(themeQuery).length === 0 && (
                  <p className="rounded-md border border-dashed border-border px-3 py-4 text-center text-sm text-muted-foreground">
                    맞는 테마가 없습니다. 다른 말로 찾아 보세요.
                  </p>
                )}
              </div>
            ) : (
              themesByFamily()
              .filter((group) => group.family === family)
              .map((group) => (
                <div key={group.family} className="grid gap-1.5">
                  <p className="text-[11px] leading-relaxed text-muted-foreground">{group.hint}</p>
                  {group.items.map((item) => {
                    const active = item.id === themeId
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => setThemeId(item.id)}
                        aria-pressed={active}
                        className={cn(
                          'flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-left text-sm transition-colors',
                          active ? 'border-accent bg-accent/8 font-medium' : 'border-border hover:bg-secondary',
                        )}
                      >
                        <span className="min-w-0">
                          <span className="block truncate">{item.name}</span>
                          <span className="block truncate text-[11px] text-muted-foreground">
                            {item.mood.join(' · ')}
                          </span>
                        </span>
                        <ThemeSwatch id={item.id} />
                      </button>
                    )
                  })}
                </div>
              ))
            )}
            <FieldHint>테마마다 색과 서체가 한 벌로 맞춰져 있습니다. 학원 기본 테마는 설정 화면에서 정합니다.</FieldHint>
          </CardContent>
        </Card>

        <ImagePicker assets={academy.assets ?? []} value={imageMap} onChange={setImageMap} />

        <Card>
          <CardHeader>
            <CardTitle>문구</CardTitle>
            <CardDescription>포스터·카드 하단에 들어가는 문구입니다.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            {(
              [
                ['subtitle', '부제'],
                ['host', '주최'],
                ['contact', '문의'],
                ['footnote', '관람 안내'],
              ] as [keyof DesignCopy, string][]
            ).map(([key, label]) => (
              <div key={key}>
                <Label htmlFor={`copy-${key}`}>{label}</Label>
                <Input
                  id={`copy-${key}`}
                  value={copy[key]}
                  maxLength={200}
                  onChange={(e) => setCopy((prev) => ({ ...prev, [key]: e.target.value }))}
                />
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>한 벌 인쇄</CardTitle>
            <CardDescription>양식을 하나씩 고르지 않고 필요한 것을 묶어서 한 번에 뽑습니다.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2">
            {PRINT_PACKS.map((pack) => (
              <a key={pack.id} href={`/events/${event.id}/design/print?pack=${pack.id}&theme=${themeId}`} target="_blank" rel="noreferrer">
                <Button variant="outline" className="h-auto w-full justify-start py-2.5 text-left">
                  <span>
                    <span className="block text-sm font-medium">{pack.name}</span>
                    <span className="block text-xs font-normal text-muted-foreground">{pack.description}</span>
                  </span>
                </Button>
              </a>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>사진</CardTitle>
            <CardDescription>사진 포스터·프로그램 표지·SNS 카드·감사 카드에 쓰입니다.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            <div>
              <Label htmlFor="photo-url">이 행사에 쓸 사진 주소</Label>
              <div className="flex items-center gap-3">
                <Input
                  id="photo-url"
                  value={photoUrl}
                  onChange={(e) => setPhotoUrl(e.target.value)}
                  placeholder={academy.photo_url ? '비우면 학원 대표 사진을 씁니다' : 'https://...'}
                />
                {(photoUrl.trim() || academy.photo_url) && (
                  // 외부 URL 이라 next/image 대신 img 로 그린다
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={photoUrl.trim() || academy.photo_url || ''}
                    alt="사진 미리보기"
                    className="h-12 w-16 shrink-0 rounded border border-border object-cover"
                  />
                )}
              </div>
              <FieldHint>
                가로가 긴 사진(3:2 정도)이 가장 잘 맞습니다. 학생 얼굴이 나오는 사진은 학부모 동의를 받은 것만
                쓰세요. 비워 두면 설정의 학원 대표 사진이 쓰입니다.
              </FieldHint>
            </div>
          </CardContent>
        </Card>
      </div>

      <div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">{template.name}</h2>
            <Badge variant="outline">{PAGE_PX[template.page].label}</Badge>
            {sheets > 1 && <Badge variant="default">{sheets}장 출력</Badge>}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={save} disabled={saving}>
              {saved ? <Check className="h-4 w-4" aria-hidden /> : <Save className="h-4 w-4" aria-hidden />}
              {saved ? '저장됨' : '이 행사에 저장'}
            </Button>
            <a href={printUrl} target="_blank" rel="noreferrer">
              <Button size="sm" disabled={blocked}>
                <Printer className="h-4 w-4" aria-hidden />
                인쇄 · PDF
              </Button>
            </a>
          </div>
        </div>

        {blocked ? (
          <Card>
            <CardContent className="py-16 text-center text-sm text-muted-foreground">
              이 양식은 연주 순서가 확정된 뒤에 쓸 수 있습니다. 먼저 순서표를 만들어 주세요.
            </CardContent>
          </Card>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border bg-muted/40 p-5">
            <div
              style={{ width: PREVIEW_WIDTH, height: page.h * scale, margin: '0 auto' }}
              className="shadow-[0_8px_30px_rgba(20,20,43,.12)]"
            >
              <div style={{ transform: `scale(${scale})`, transformOrigin: 'top left' }}>
                {renderTemplate(templateId, ctx, true)}
              </div>
            </div>
            {sheets > 1 && (
              <p className="mt-4 text-center text-xs text-muted-foreground">
                미리보기는 첫 장만 보여 줍니다. 인쇄하면 {sheets}장이 이어서 나옵니다.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
