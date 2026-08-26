import { notFound } from 'next/navigation'
import { renderTemplate } from '@/components/design/render'
import { PrintButton } from '@/components/print-button'
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
  searchParams: { template?: string; theme?: string; pack?: string }
}) {
  const repo = getRepository()
  const event = await repo.getEvent(params.id)
  if (!event) notFound()

  const [academy, students] = await Promise.all([repo.getAcademy(event.academy_id), repo.listStudents(event.id)])
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
    logoUrl: academy.logo_url,
    // 행사 사진이 없으면 학원 대표 사진으로 내려간다
    photoUrl: event.photo_url ?? academy.photo_url,
    // 인쇄물에는 빈 로고·사진 상자를 찍지 않는다
    placeholder: false,
  }

  return (
    <div className="min-h-screen bg-muted/50 py-8 print:bg-white print:py-0">
      {/* 인쇄면 크기에 맞춰 용지를 지정한다. 여백 0 으로 두고 디자인 안에서 여백을 잡는다 */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
            @media print {
              @page { size: ${page.css}; margin: 0; }
              html, body { background: #fff !important; }
              .d-sheet { break-after: page; page-break-after: always; }
              .d-sheet:last-child { break-after: auto; page-break-after: auto; }
            }
          `,
        }}
      />

      <div className="mx-auto mb-5 flex max-w-[860px] flex-wrap items-center justify-between gap-3 px-4 no-print">
        <p className="text-sm text-muted-foreground">
          {pack ? `${pack.name} (${templates.map((t) => t.name).join(' · ')})` : template.name} · {page.label} ·{' '}
          {sheets}장 — 인쇄 대화상자에서 <strong>배율 100%</strong>, 여백 없음으로 두면 그대로 나옵니다.
        </p>
        <PrintButton />
      </div>

      <div className="flex flex-col items-center gap-6 print:gap-0">
        {templates.map((item) => (
          <div key={item.id} className="contents">
            {renderTemplate(item.id, ctx)}
          </div>
        ))}
      </div>
    </div>
  )
}
