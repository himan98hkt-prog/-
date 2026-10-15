import { BRAND } from '@/lib/brand'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { CopyButton } from '@/components/copy-button'
import { Printable } from '@/components/print/printable'
import { getPack, getTemplate, packTemplates } from '@/lib/design/templates'
import { formatEventDate } from '@/lib/format'
import { quoteRows, quoteText, quoteTotal } from '@/lib/print/quote'
import { getRepository } from '@/lib/store'

export const dynamic = 'force-dynamic'
export const metadata = { title: '인쇄소 견적용 요약' }

/**
 * 인쇄소에 전화하실 때 손에 드시는 종이 한 장.
 *
 * 인쇄소는 "몇 절이요? 종이는요? 몇 부요?" 라고 묻는다. 원장님은 그 낱말을 모르시고,
 * 모르시니 전화를 못 거신다. 그래서 결국 집 프린터로 100장을 뽑으신다.
 * 여기에 그 답을 미리 적어 둔다.
 */
export default async function QuotePage({
  params,
  searchParams,
}: {
  params: { id: string }
  searchParams: { template?: string; pack?: string; copies?: string }
}) {
  const repo = getRepository()
  const event = await repo.getEvent(params.id)
  if (!event) notFound()

  const [academy, students] = await Promise.all([repo.getAcademy(event.academy_id), repo.listStudents(event.id)])
  const pack = getPack(searchParams.pack)
  const chosen = searchParams.template ?? event.design_template
  const templates = pack ? packTemplates(pack, chosen) : [getTemplate(chosen)]

  const copies = Math.max(1, Math.min(2000, Number(searchParams.copies) || 40))
  const rows = quoteRows(templates, students.length, copies)
  const text = quoteText(event.title, rows)

  return (
    <div className="min-h-screen bg-muted/40 py-8 print:bg-white print:py-0">
      <div className="mx-auto max-w-[860px] px-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 no-print">
          <Link
            href={`/events/${event.id}/design`}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            ← 인쇄물 디자인
          </Link>
          <CopyButton text={text} label="문자로 보낼 글 복사" />
        </div>

        <Printable what="인쇄소 견적용 요약" paperId="a4-portrait" marginMm={14}>
          <article className="print-page bg-white px-10 py-10 shadow-sm print:px-0 print:py-0">
            <header className="border-b-2 border-foreground/80 pb-4">
              <p className="text-xs tracking-[0.25em] text-muted-foreground">인쇄 견적 문의</p>
              <h1 className="mt-2 text-2xl font-bold tracking-tight">{event.title}</h1>
              <p className="mt-1.5 text-sm text-muted-foreground">
                {academy?.name}
                {academy?.director_name ? ` · 원장 ${academy.director_name}` : ''} ·{' '}
                {formatEventDate(event.event_at)}
                {event.venue ? ` · ${event.venue}` : ''}
              </p>
            </header>

            <p className="mt-5 text-sm text-muted-foreground">
              아래 표를 인쇄소에 그대로 보여 주시면 됩니다. 종이 이름과 두께는{' '}
              <strong className="text-foreground">연주회 인쇄물에서 흔히 쓰는 것</strong>으로 적어 두었습니다 —
              인쇄소에서 다른 것을 권하면 그쪽이 맞습니다.
            </p>

            <div className="mt-5 overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm" data-testid="quote-table">
                <thead>
                  <tr className="border-b border-foreground/30 text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">인쇄물</th>
                    <th className="py-2 pr-3 font-medium">규격</th>
                    <th className="py-2 pr-3 font-medium">종이</th>
                    <th className="py-2 pr-3 text-right font-medium">부수</th>
                    <th className="py-2 text-right font-medium">총 장수</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.name} className="border-b border-border align-top">
                      <td className="py-2.5 pr-3 font-medium">
                        {row.name}
                        <span className="mt-0.5 block text-xs font-normal text-muted-foreground">{row.note}</span>
                      </td>
                      <td className="py-2.5 pr-3 whitespace-nowrap">{row.paper}</td>
                      <td className="py-2.5 pr-3 whitespace-nowrap">{row.stock}</td>
                      <td className="py-2.5 pr-3 text-right tabular-nums">{row.copies}부</td>
                      <td className="py-2.5 text-right tabular-nums">{row.total}장</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td className="pt-3 font-semibold" colSpan={4}>
                      합계
                    </td>
                    <td className="pt-3 text-right font-semibold tabular-nums" data-testid="quote-total">
                      {quoteTotal(rows)}장
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>

            <section className="mt-6 rounded-md border border-border bg-muted/40 p-4 text-sm">
              <p className="font-medium">인쇄소에 함께 말씀하실 것</p>
              <ul className="mt-2 grid gap-1 text-muted-foreground">
                <li>· 파일은 <strong className="text-foreground">PDF</strong> 로 드립니다.</li>
                <li>
                  · <strong className="text-foreground">재단선과 물림 여백 3mm</strong> 가 들어 있습니다 (인쇄물
                  화면의 <strong className="text-foreground">[인쇄소용]</strong> 으로 만든 파일입니다).
                </li>
                <li>· 색은 모두 <strong className="text-foreground">단면 컬러</strong> 입니다.</li>
                <li>· 받으실 날짜: 연주회 {formatEventDate(event.event_at)} 보다 며칠 앞으로 잡아 주세요.</li>
              </ul>
            </section>

            <footer className="mt-6 border-t border-border pt-3 text-xs text-muted-foreground">
              {academy?.name}
              {academy?.director_name ? ` · 원장 ${academy.director_name}` : ''} — {BRAND.name}
            </footer>
          </article>
        </Printable>
      </div>
    </div>
  )
}
