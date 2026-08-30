'use client'

import { Check, ChevronDown, Printer, Save } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
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
  packTemplates,
  sheetCount,
  templatesByCategory,
  type TemplateCategory,
  type TemplateDef,
} from '@/lib/design/templates'
import {
  DESIGN_THEMES,
  getTheme,
  type ThemeFamily,
} from '@/lib/design/themes'
import type { Academy, EventRecord, ProgramPlan, Rsvp } from '@/lib/types'
import { ThemePicker } from '@/components/design/theme-picker'
import { describePick, recommendDesign, recommendDesigns } from '@/lib/design/recommend'
import { cn } from '@/lib/utils'

const PREVIEW_WIDTH = 520
const DESIGN_TEMPLATE_COUNT = DESIGN_TEMPLATES.length

export function DesignStudio({
  academy,
  event,
  plan,
  rsvps,
  inviteUrl,
  initialCopy,
  pickKind,
}: {
  academy: Academy
  event: EventRecord
  plan: ProgramPlan
  rsvps: Rsvp[]
  inviteUrl: string
  initialCopy: DesignCopy
  /** 종이의 QR 을 비추고 오셨다면 그 장 ('chosen' · 'season' · 'plain' · 'fancy') */
  pickKind?: string
}) {
  /**
   * 처음 열면 **이미 골라진 채로** 열린다.
   * 고르신 것이 있으면 그것을, 없으면 행사 달에 어울리는 것을 미리 정해 둔다.
   */
  const pick = useMemo(
    () =>
      recommendDesign({
        eventAt: event.event_at,
        hasProgram: plan.items.length > 0,
        themeId: event.design_theme ?? academy.design_theme ?? null,
        templateId: event.design_template ?? null,
      }),
    [event.event_at, event.design_theme, event.design_template, academy.design_theme, plan.items.length],
  )
  /**
   * 견주어 보실 **세 장.**
   *
   * 하나만 정해 드리면 "마음에 안 드는데" 에서 막히시고, 108종을 펼치면 처음으로 돌아간다.
   * 셋이면 한눈에 견주신다. 눌러 보시면 오른쪽 큰 그림이 그대로 바뀐다.
   */
  const choices = useMemo(
    () =>
      recommendDesigns({
        eventAt: event.event_at,
        hasProgram: plan.items.length > 0,
        themeId: event.design_theme ?? academy.design_theme ?? null,
        templateId: event.design_template ?? null,
      }),
    [event.event_at, event.design_theme, event.design_template, academy.design_theme, plan.items.length],
  )
  /**
   * 종이에서 오셨으면 **그 장으로 열린다.**
   *
   * 종이에 동그라미를 치고 QR 을 비추셨는데 화면이 딴것으로 열리면, 종이에 표시한 일이
   * 헛일이 된다. 없는 장을 가리키면 그냥 첫 장으로 연다 — 멈추는 것보다 낫다.
   */
  const fromPaper = choices.find((item) => item.kind === pickKind) ?? null
  const opening = fromPaper ?? pick

  const [templateId, setTemplateId] = useState(opening.templateId)
  const [themeId, setThemeId] = useState(opening.themeId)
  const [copy, setCopy] = useState<DesignCopy>(initialCopy)
  const [photoUrl, setPhotoUrl] = useState(event.photo_url ?? '')
  const [imageMap, setImageMap] = useState<ImageMap>(event.image_map ?? {})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  /**
   * **직접 고르기는 접어 둔다.**
   *
   * 위에서 "이대로 뽑으셔도 됩니다" 라고 해 놓고 바로 아래에 테마 32개와 양식 목록을
   * 펼쳐 두면, 그 말을 못 믿으신다. 재어 보니 이 화면에 눌러 볼 것이 102개였고
   * 길이가 6,000px 이었다 — 여섯 화면을 내려야 끝나는 화면이다.
   *
   * 세 장으로 되는 분은 여기서 끝내시고, 바꾸실 분만 펴신다.
   */
  const [picking, setPicking] = useState(false)
  // 양식 75종·테마 108종을 한 목록에 늘어놓으면 고를 수가 없다. 묶음을 먼저 고른다.
  const [category, setCategory] = useState<TemplateCategory>(getTemplate(opening.templateId).category)
  const [themeQuery, setThemeQuery] = useState('')
  const [family, setFamily] = useState<ThemeFamily>(getTheme(opening.themeId).family)

  // 행사 달에 맞는 계절 테마 — 108종을 다 훑지 않아도 되게
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

  /**
   * 미리보기가 **늘 보여야** 한다.
   *
   * 예전에는 테마·색을 고르러 아래로 내려가면 미리보기가 화면 위로 사라졌다.
   * 색을 눌러도 무엇이 바뀌었는지 볼 수가 없으니, 고르는 일이 찍기가 된다.
   *
   * 그래서 미리보기를 화면에 붙여 두고(sticky), 남은 자리에 맞게 줄여 그린다.
   * 좁은 화면에서는 위쪽에 붙고, 넓은 화면에서는 오른쪽에 붙는다.
   */
  /**
   * 자리를 **창 크기에서** 잰다.
   *
   * 처음에는 미리보기 상자 자신을 쟀는데, 그 상자의 너비가 곧 칸의 너비였다.
   * 상자가 넓어지면 칸이 넓어지고, 칸이 넓어지면 다시 상자가 넓어진다 —
   * 서로를 밀어 좁은 화면에서 가로로 넘쳤다. 창은 아무것도 밀지 않으므로 창을 잰다.
   */
  const [avail, setAvail] = useState({ w: PREVIEW_WIDTH, h: 0 })

  useEffect(() => {
    const measure = () => {
      const wide = window.innerWidth >= 1024
      setAvail({
        w: wide ? PREVIEW_WIDTH : Math.max(200, Math.min(window.innerWidth - 48, PREVIEW_WIDTH)),
        // 좁은 화면에서는 미리보기가 화면을 다 먹으면 안 된다 — 아래 고르는 칸이 보여야 한다
        h: wide ? 0 : Math.round(window.innerHeight * 0.32),
      })
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [])

  // 가로와 세로 **둘 다** 들어가게 줄인다. 한쪽만 맞추면 긴 인쇄물이 잘린다.
  const scale = Math.min(avail.w / page.w, avail.h > 0 ? avail.h / page.h : Number.POSITIVE_INFINITY)

  const sheets = sheetCount(templateId, plan.items.length)
  /** 한 벌이 종이 몇 장인지 — 고르시는 자리에서 아셔야 한다 */
  const packSheets = (pack: (typeof PRINT_PACKS)[number]) =>
    packTemplates(pack).reduce((sum, item) => sum + sheetCount(item.id, plan.items.length), 0)
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
    <div className="grid items-start gap-6 lg:grid-cols-[340px_1fr]">
      <div className="order-2 grid min-w-0 gap-5 [&>*]:min-w-0 lg:order-1">
        {/* 고를 것이 있다는 사실 자체에서 멈추신다. 하나를 미리 정해 두고 먼저 말한다 */}
        <section className="grid gap-1.5 rounded-lg border border-accent/40 bg-accent/5 p-3" data-testid="design-ready">
          <p className="text-sm font-medium">이대로 뽑으셔도 됩니다</p>
          <p className="text-sm text-muted-foreground">
            {fromPaper ? (
              <>
                종이에서 고르신 <strong className="text-foreground">{describePick(fromPaper)}</strong> 로 맞춰
                두었습니다. 아래 <strong>[인쇄 · PDF]</strong> 만 누르시면 됩니다.
              </>
            ) : (
              <>
                <strong className="text-foreground">{describePick(pick)}</strong> 로 맞춰 두었습니다. {pick.why}{' '}
                오른쪽 그림이 그대로 나옵니다 — 아래 <strong>[인쇄 · PDF]</strong> 만 누르시면 됩니다.
              </>
            )}
          </p>

          {/* 마음에 안 드실 때 108종으로 보내지 않는다. 딴 길 둘만 옆에 세워 둔다 */}
          <div className="mt-1 grid grid-cols-3 gap-2" data-testid="design-choices">
            {choices.map((choice, index) => {
              const chosen = choice.themeId === themeId && choice.templateId === templateId
              return (
                <button
                  key={choice.kind}
                  type="button"
                  onClick={() => {
                    setThemeId(choice.themeId)
                    setTemplateId(choice.templateId)
                    setFamily(getTheme(choice.themeId).family)
                    setCategory(getTemplate(choice.templateId).category)
                  }}
                  aria-pressed={chosen}
                  title={choice.why}
                  data-testid={`design-choice-${choice.kind}`}
                  className={cn(
                    'grid gap-1 rounded-md border p-1.5 text-left transition-colors',
                    chosen ? 'border-accent bg-background shadow-sm' : 'border-border hover:bg-background/60',
                  )}
                >
                  <ChoiceThumb templateId={choice.templateId} ctx={{ ...ctx, theme: getTheme(choice.themeId) }} />
                  {/* 종이에 뽑은 것과 같은 번호 — "종이의 2번" 이 화면에서도 2번이라야 한다 */}
                  <span className="block text-xs font-medium leading-tight">
                    {index + 1}. {choice.label}
                  </span>
                  <span className="block truncate text-xs leading-tight text-muted-foreground">
                    {getTheme(choice.themeId).name}
                  </span>
                </button>
              )
            })}
          </div>

          {/* 화면 색과 종이 색은 다르다. 한 장이면 실물로 견주신다 */}
          <a
            href={`/events/${event.id}/design/compare`}
            target="_blank"
            rel="noreferrer"
            className="text-xs underline underline-offset-4"
            data-testid="compare-link"
          >
            세 장을 A4 한 장에 뽑아 견주기 →
          </a>

        </section>

        <Card>
          <CardHeader>
            <CardTitle>한 벌 인쇄</CardTitle>
            <CardDescription>양식을 하나씩 고르지 않고 필요한 것을 묶어서 한 번에 뽑습니다.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2">
            {PRINT_PACKS.map((pack) => (
              <a
                key={pack.id}
                href={`/events/${event.id}/design/print?pack=${pack.id}&theme=${themeId}`}
                target="_blank"
                rel="noreferrer"
                className="min-w-0"
              >
                {/* 단추는 본디 한 줄짜리다. 설명이 길어 좁은 화면에서 가로로 넘쳤다 — 줄바꿈을 열어 준다 */}
                <Button
                  variant="outline"
                  className="h-auto w-full justify-start whitespace-normal py-2.5 text-left"
                >
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">
                      {pack.name}
                      {/* 몇 장이 나오는지는 고르시는 자리에서 아셔야 한다 — 눌러 들어가 보고 아시면 늦다 */}
                      <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                        종이 {packSheets(pack)}장
                      </span>
                    </span>
                    <span className="block text-xs font-normal text-muted-foreground">{pack.description}</span>
                  </span>
                </Button>
              </a>
            ))}
          </CardContent>
        </Card>

        {/* 셋 다 마음에 안 드실 때만 — 그때까지는 화면에 없는 편이 낫다 */}
        <button
          type="button"
          onClick={() => setPicking((on) => !on)}
          aria-expanded={picking}
          className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-4 py-3 text-left text-sm hover:bg-secondary"
          data-testid="design-picking-toggle"
        >
          <span>
            <span className="font-medium">{picking ? '직접 고르기 닫기' : '직접 고르기'}</span>
            <span className="ml-1.5 text-xs text-muted-foreground">
              양식 {DESIGN_TEMPLATE_COUNT}종 · 테마 {DESIGN_THEMES.length}종 · 문구 · 사진
            </span>
          </span>
          <ChevronDown className={cn('h-4 w-4 shrink-0 transition-transform', picking && 'rotate-180')} aria-hidden />
        </button>

        <div className={cn('grid gap-5', !picking && 'hidden')} data-testid="design-picking">
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

            {/*
              **이름으로는 못 고르신다.** "3단 접지 프로그램" 이 어떤 종이인지는 봐야 안다.
              지금 고르신 테마로 그린 축소 그림을 늘어놓는다 — 가짓수는 그대로 75종이다.
            */}
            <div className="grid grid-cols-3 gap-2" data-testid="template-grid">
              {(templatesByCategory().find((g) => g.category === category)?.items ?? []).map((item: TemplateDef) => {
                const active = item.id === templateId
                const needsProgram = item.needsProgram && plan.items.length === 0
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setTemplateId(item.id)}
                    aria-pressed={active}
                    title={item.description}
                    className={cn(
                      'grid justify-items-center gap-1 rounded-md border p-1.5 text-center transition-colors',
                      active ? 'border-accent bg-accent/8' : 'border-border hover:bg-secondary',
                    )}
                  >
                    <ChoiceThumb templateId={item.id} ctx={ctx} width={82} />
                    {/* 이름을 자르면 그림으로 바꾼 뜻이 반은 사라진다 — 두 줄까지 */}
                    <span className={cn('block w-full text-xs leading-tight', active && 'font-medium')}>
                      {item.name}
                    </span>
                    <span className="block w-full truncate text-xs text-muted-foreground">
                      {needsProgram ? '순서표 필요' : PAGE_PX[item.page].label}
                    </span>
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
            <ThemePicker value={themeId} onChange={setThemeId} eventAt={event.event_at} />
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

        {/* 다 고르셨으면 여기서 저장하거나 바로 뽑으세요 */}
        <div className="flex flex-wrap gap-2 rounded-lg border border-border bg-card p-3">
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
          <p className="w-full text-xs text-muted-foreground">
            저장해 두시면 다음에 여실 때 이 모양 그대로 열립니다.
          </p>
        </div>
      </div>

      {/* 미리보기는 화면에 붙어 따라다닌다 — 색을 고르는 동안에도 늘 보여야 한다.
          붙어 있는 칸에는 미리보기만 둔다. 단추까지 넣으면 좁은 화면을 다 먹는다. */}
      <div
        className="order-1 sticky top-16 z-10 min-w-0 rounded-xl border border-border bg-background/95 p-2 backdrop-blur lg:order-2 lg:top-20 lg:border-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-none"
        data-testid="design-preview"
      >
        <div className="mb-2 flex min-w-0 flex-wrap items-center gap-2">
          <h2 className="truncate text-base font-semibold sm:text-lg">{template.name}</h2>
          <Badge variant="outline">{PAGE_PX[template.page].label}</Badge>
          {sheets > 1 && <Badge variant="default">{sheets}장 출력</Badge>}
          <span className="ml-auto text-xs text-muted-foreground">고르시는 대로 여기서 바뀝니다</span>
        </div>

        {blocked ? (
          <Card>
            <CardContent className="py-16 text-center text-sm text-muted-foreground">
              이 양식은 연주 순서가 확정된 뒤에 쓸 수 있습니다. 먼저 순서표를 만들어 주세요.
            </CardContent>
          </Card>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border bg-muted/40 p-3 sm:p-5">
            <div
              style={{ width: page.w * scale, height: page.h * scale, margin: '0 auto' }}
              className="shadow-[0_8px_30px_rgba(20,20,43,.12)]"
            >
              <div style={{ transform: `scale(${scale})`, transformOrigin: 'top left' }}>
                {renderTemplate(templateId, ctx, true)}
              </div>
            </div>
            {sheets > 1 && (
              <p className="mt-3 text-center text-xs text-muted-foreground">
                미리보기는 첫 장만 보여 줍니다. 인쇄하면 {sheets}장이 이어서 나옵니다.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * 견줌 카드에 들어가는 아주 작은 그림.
 *
 * 색 동그라미 세 개로는 "무슨 느낌인지" 를 알 수 없다. 실제로 뽑힐 그림을
 * 그대로 줄여 보여 드려야 고르실 수 있다. 큰 미리보기와 같은 것을 그리되,
 * 카드 폭에 맞게만 줄인다.
 */
function ChoiceThumb({
  templateId,
  ctx,
  width = 88,
}: {
  templateId: string
  ctx: Parameters<typeof renderTemplate>[1]
  width?: number
}) {
  const page = PAGE_PX[getTemplate(templateId).page]
  const scale = width / page.w

  return (
    <span
      className="block overflow-hidden rounded border border-border bg-muted/40"
      style={{ width, height: Math.round(page.h * scale) }}
      aria-hidden
    >
      <span className="block" style={{ transform: `scale(${scale})`, transformOrigin: 'top left' }}>
        {renderTemplate(templateId, ctx, true)}
      </span>
    </span>
  )
}
