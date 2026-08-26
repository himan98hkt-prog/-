'use client'

import { Check, Printer, Save } from 'lucide-react'
import { useMemo, useState } from 'react'
import { renderTemplate } from '@/components/design/render'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldHint, Input, Label } from '@/components/ui/field'
import type { DesignCopy } from '@/lib/design/context'
import {
  CATEGORY_LABEL,
  PAGE_PX,
  getTemplate,
  sheetCount,
  templatesByCategory,
  type TemplateDef,
} from '@/lib/design/templates'
import { DESIGN_THEMES, getTheme } from '@/lib/design/themes'
import type { Academy, EventRecord, ProgramPlan } from '@/lib/types'
import { cn } from '@/lib/utils'

const PREVIEW_WIDTH = 520

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
  inviteUrl,
  initialCopy,
}: {
  academy: Academy
  event: EventRecord
  plan: ProgramPlan
  inviteUrl: string
  initialCopy: DesignCopy
}) {
  const [templateId, setTemplateId] = useState(event.design_template ?? 'poster-classic')
  const [themeId, setThemeId] = useState(event.design_theme ?? academy.design_theme ?? 'classic-navy')
  const [copy, setCopy] = useState<DesignCopy>(initialCopy)
  const [photoUrl, setPhotoUrl] = useState(event.photo_url ?? '')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

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
      logoUrl: academy.logo_url,
      photoUrl: photoUrl.trim() || academy.photo_url,
      placeholder: true,
    }),
    [theme, academy, event, plan, copy, inviteUrl, photoUrl],
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
            <CardTitle>양식</CardTitle>
            <CardDescription>{template.description}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            {templatesByCategory().map((group) => (
              <div key={group.category}>
                <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  {CATEGORY_LABEL[group.category]}
                </p>
                <div className="grid gap-1.5">
                  {group.items.map((item: TemplateDef) => {
                    const active = item.id === templateId
                    const needsProgram = item.needsProgram && plan.items.length === 0
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => setTemplateId(item.id)}
                        aria-pressed={active}
                        className={cn(
                          'flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors',
                          active ? 'border-accent bg-accent/8 font-medium' : 'border-border hover:bg-secondary',
                        )}
                      >
                        <span className="min-w-0 truncate">{item.name}</span>
                        <span className="flex shrink-0 items-center gap-1.5">
                          {needsProgram && <span className="text-[10px] text-muted-foreground">순서표 필요</span>}
                          <span className="text-[10px] text-muted-foreground">{PAGE_PX[item.page].label}</span>
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>테마</CardTitle>
            <CardDescription>{getTheme(themeId).tagline}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-1.5">
            {DESIGN_THEMES.map((item) => {
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
                    <span className="block truncate text-[11px] text-muted-foreground">{item.mood.join(' · ')}</span>
                  </span>
                  <ThemeSwatch id={item.id} />
                </button>
              )
            })}
            <FieldHint>테마마다 색과 서체가 한 벌로 맞춰져 있습니다. 학원 기본 테마는 설정 화면에서 정합니다.</FieldHint>
          </CardContent>
        </Card>

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
