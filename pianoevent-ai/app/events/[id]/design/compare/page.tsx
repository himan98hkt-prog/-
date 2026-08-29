import Link from 'next/link'
import { notFound } from 'next/navigation'
import { renderTemplate } from '@/components/design/render'
import { PrintTips } from '@/components/print/print-tips'
import { resolveLogo, resolvePhoto } from '@/lib/assets'
import { defaultCopy, type DesignCopy } from '@/lib/design/context'
import { recommendDesigns } from '@/lib/design/recommend'
import { PAGE_PX, getTemplate } from '@/lib/design/templates'
import { getTheme } from '@/lib/design/themes'
import { resolvePlan } from '@/lib/program/resolve'
import { getRepository } from '@/lib/store'

export const dynamic = 'force-dynamic'
export const metadata = { title: '세 장 견주기' }

/** A4 가로 한 장에 셋을 나란히 — 한 칸의 너비(px, 96dpi) */
const SLOT_W = 300

/**
 * **세 장을 종이로 견주기.**
 *
 * 화면 색과 종이 색은 다르다. 화면에서 곱게 보이던 금색이 종이에서는 누렇게 나오고,
 * 옅은 하늘색은 아예 안 나온다. 그래서 화면에서 고르신 것을 뽑아 보고 "어, 이게 아닌데" 를
 * 하시게 된다 — 그때는 이미 100부를 거신 뒤다.
 *
 * A4 **한 장**에 셋을 나란히 뽑아 드린다. 종이 한 장이면 실물로 견주실 수 있다.
 */
export default async function DesignComparePage({ params }: { params: { id: string } }) {
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
  const choices = recommendDesigns({
    eventAt: event.event_at,
    hasProgram: plan.items.length > 0,
    themeId: event.design_theme ?? academy.design_theme ?? null,
    templateId: event.design_template ?? null,
  })
  const base = defaultCopy(academy, event)
  const copy: DesignCopy = { ...base, ...(event.design_copy ?? {}) }
  const page = PAGE_PX['a4-landscape']

  return (
    <div className="min-h-screen bg-muted/50 py-8 print:bg-white print:py-0">
      <style
        dangerouslySetInnerHTML={{
          __html: `
            @media print {
              @page { size: ${page.css}; margin: 0; }
              html, body { background: #fff !important; }
            }
          `,
        }}
      />

      <div className="mx-auto mb-5 grid max-w-[860px] gap-2 px-4">
        <PrintTips what="세 장 견주기 (한 장에 셋)" paperLabel={page.label} sheets={1} />
        <p className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-muted-foreground no-print">
          화면 색과 종이 색은 다릅니다. <strong>한 장만 뽑아</strong> 실물로 견주시고, 마음에 드는 것을{' '}
          <Link href={`/events/${event.id}/design`} className="underline underline-offset-4">
            인쇄물 디자인
          </Link>{' '}
          화면에서 고르시면 됩니다.
        </p>
      </div>

      <div className="mx-auto w-fit bg-white shadow-lg print:shadow-none d-sheet" style={{ width: page.w, height: page.h }}>
        <div className="flex h-full flex-col px-10 py-8" data-testid="compare-sheet">
          <p className="text-lg font-bold">{event.title} · 인쇄물 세 장 견주기</p>
          <p className="mt-0.5 text-xs text-neutral-500">
            {academy.name} · 마음에 드는 것 하나에 동그라미 치시고, 화면에서 그것을 고르시면 됩니다.
          </p>

          <div className="mt-5 grid flex-1 grid-cols-3 gap-6">
            {choices.map((choice) => {
              const theme = getTheme(choice.themeId)
              const template = getTemplate(choice.templateId)
              const slot = PAGE_PX[template.page]
              const scale = SLOT_W / slot.w
              const ctx = {
                theme,
                academy,
                event,
                plan,
                copy,
                inviteUrl: `/e/${event.id}`,
                logoUrl: resolveLogo(academy.assets ?? [], event.image_map, academy.logo_url),
                photoUrl: resolvePhoto(academy.assets ?? [], event.image_map, template.category, [
                  event.photo_url,
                  academy.photo_url,
                ]),
                placeholder: false,
                rsvps,
              }

              return (
                <div key={choice.kind} className="flex flex-col" data-testid={`compare-${choice.kind}`}>
                  <div className="flex items-baseline gap-1.5">
                    {/* 종이에 동그라미를 치실 자리 */}
                    <span className="inline-block h-4 w-4 shrink-0 rounded-full border-2 border-neutral-400" />
                    <span className="text-sm font-bold">{choice.label}</span>
                  </div>
                  <p className="mt-0.5 text-[11px] text-neutral-500">
                    {theme.name} · {template.name}
                  </p>
                  <div
                    className="mt-2 overflow-hidden border border-neutral-300"
                    style={{ width: SLOT_W, height: Math.round(slot.h * scale) }}
                  >
                    <div style={{ transform: `scale(${scale})`, transformOrigin: 'top left' }}>
                      {renderTemplate(choice.templateId, ctx, true)}
                    </div>
                  </div>
                  <p className="mt-2 text-[11px] leading-snug text-neutral-600">{choice.why}</p>
                </div>
              )
            })}
          </div>

          <p className="mt-4 text-[10px] text-neutral-400">
            실제 인쇄물은 이보다 큽니다 — 여기서는 색과 분위기만 견주세요. 크기는 화면에서 [종이로 보기] 로 보십니다.
          </p>
        </div>
      </div>
    </div>
  )
}
