import { notFound } from 'next/navigation'
import { renderTemplate } from '@/components/design/render'
import { BleedFrame } from '@/components/print/crop-marks'
import { PrintTips } from '@/components/print/print-tips'
import { BLEED_MM, bleedPageCss } from '@/lib/print/paper'
import { resolveLogo, resolvePhoto } from '@/lib/assets'
import { defaultCopy, type DesignCopy } from '@/lib/design/context'
import { PAGE_PX, getPack, getTemplate, packTemplates, sheetCount } from '@/lib/design/templates'
import { getTheme } from '@/lib/design/themes'
import { resolvePlan } from '@/lib/program/resolve'
import { getRepository } from '@/lib/store'

export const dynamic = 'force-dynamic'
export const metadata = { title: '인쇄물' }

export default async function DesignPrintPage({
  params,
  searchParams,
}: {
  params: { id: string }
  searchParams: { template?: string; theme?: string; pack?: string; bleed?: string }
}) {
  const repo = getRepository()
  const event = await repo.getEvent(params.id)
  if (!event) notFound()

  const [academy, students, rsvps] = await Promise.all([
    repo.getAcademy(event.academy_id),
    repo.listStudents(event.id),
    repo.listRsvps(event.id),
  ])
  if (!academy) notFound()

  const { plan } = resolvePlan(students)
  const pack = getPack(searchParams.pack)
  const templates = pack ? packTemplates(pack) : [getTemplate(searchParams.template ?? event.design_template)]
  const template = templates[0]
  const theme = getTheme(searchParams.theme ?? event.design_theme ?? academy.design_theme)
  const base = defaultCopy(academy, event)
  const copy: DesignCopy = { ...base, ...(event.design_copy ?? {}) }
  const page = PAGE_PX[template.page]
  const sheets = templates.reduce((sum, item) => sum + sheetCount(item.id, plan.items.length), 0)
  const ctx = {
    theme,
    academy,
    event,
    plan,
    copy,
    inviteUrl: `/e/${event.id}`,
    logoUrl: resolveLogo(academy.assets ?? [], event.image_map, academy.logo_url),
    // 갈래 지정 → 기본 지정 → 행사 사진 → 학원 대표 사진 순으로 내려간다
    photoUrl: resolvePhoto(academy.assets ?? [], event.image_map, template.category, [
      event.photo_url,
      academy.photo_url,
    ]),
    // 인쇄물에는 빈 로고·사진 상자를 찍지 않는다
    placeholder: false,
    // 좌석 배치도·접수 확인표가 실제 회신을 쓴다
    rsvps,
  }

  // 인쇄소에 맡기실 때는 사방 3mm 를 더 뽑아 재단선을 찍는다
  const bleed = searchParams.bleed === '1'
  const here = new URLSearchParams()
  if (searchParams.template) here.set('template', searchParams.template)
  if (searchParams.theme) here.set('theme', searchParams.theme)
  if (searchParams.pack) here.set('pack', searchParams.pack)
  const withBleed = new URLSearchParams(here)
  withBleed.set('bleed', '1')

  return (
    <div className="min-h-screen bg-muted/50 py-8 print:bg-white print:py-0">
      {/* 인쇄면 크기에 맞춰 용지를 지정한다. 여백 0 으로 두고 디자인 안에서 여백을 잡는다 */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
            @media print {
              @page { size: ${bleed ? bleedPageCss(page.w, page.h) : page.css}; margin: 0; }
              html, body { background: #fff !important; }
              .d-sheet { break-after: page; page-break-after: always; }
              .d-bleed { break-after: page; page-break-after: always; }
              .d-sheet:last-child, .d-bleed:last-child { break-after: auto; page-break-after: auto; }
              .d-bleed .d-sheet { break-after: auto; page-break-after: auto; }
              .${'print-first-only'} .d-sheet:not(:first-of-type),
              .${'print-first-only'} .d-bleed:not(:first-of-type) { display: none !important; }
            }
          `,
        }}
      />

      <div className="mx-auto mb-5 grid max-w-[860px] gap-2 px-4">
        <PrintTips
          what={pack ? `${pack.name} (${templates.map((t) => t.name).join(' · ')})` : template.name}
          paperLabel={bleed ? `${page.label} + 물림 ${BLEED_MM}mm` : page.label}
          sheets={sheets}
        />

        {/* 인쇄소에 맡기실 때만 필요한 것 — 평소에는 한 줄로 접어 둔다 */}
        <div
          className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs no-print"
          data-testid="bleed-bar"
        >
          {bleed ? (
            <>
              <span className="mr-auto">
                <strong>인쇄소용</strong> — 사방 {BLEED_MM}mm 를 더 그리고 네 모서리에 재단선을 찍었습니다. 이대로{' '}
                <strong>PDF로 저장</strong> 해서 인쇄소에 넘기세요.
              </span>
              <a
                href={`?${here.toString()}`}
                className="rounded-md border border-border px-2.5 py-1 hover:bg-secondary"
              >
                집 프린터용으로
              </a>
            </>
          ) : (
            <>
              <span className="mr-auto text-muted-foreground">
                인쇄소·현수막 업체에 맡기시나요? 자를 자리 표시와 여백이 있어야 가장자리가 하얗게 뜨지 않습니다.
              </span>
              <a
                href={`?${withBleed.toString()}`}
                className="rounded-md border border-border px-2.5 py-1 hover:bg-secondary"
                data-testid="bleed-on"
              >
                인쇄소용 (재단선 · 여백 {BLEED_MM}mm)
              </a>
            </>
          )}
        </div>
      </div>

      <div className="flex flex-col items-center gap-6 print:gap-0">
        {templates.map((item) => {
          const sheet = renderTemplate(item.id, {
            ...ctx,
            // 한 벌 안에서도 포스터와 순서지가 서로 다른 사진을 쓸 수 있다
            photoUrl: resolvePhoto(academy.assets ?? [], event.image_map, item.category, [
              event.photo_url,
              academy.photo_url,
            ]),
          })
          return (
            <div key={item.id} className="contents">
              {bleed ? <BleedFrame paper={theme.palette.paper}>{sheet}</BleedFrame> : sheet}
            </div>
          )
        })}
      </div>
    </div>
  )
}
