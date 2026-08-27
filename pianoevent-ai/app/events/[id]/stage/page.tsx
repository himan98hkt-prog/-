import Link from 'next/link'
import { notFound } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { StageScreen } from '@/components/stage/stage-screen'
import { resolveLogo } from '@/lib/assets'
import { getTheme } from '@/lib/design/themes'
import { formatEventDate } from '@/lib/format'
import { resolvePlan } from '@/lib/program/resolve'
import { currentAcademy } from '@/lib/session'
import { buildStageDeck, DEFAULT_STAGE_OPTIONS, STAGE_SLIDE_H, STAGE_SLIDE_W } from '@/lib/stage/deck'
import { getRepository } from '@/lib/store'

export const dynamic = 'force-dynamic'
export const metadata = { title: '무대 화면' }

/**
 * 연주회 당일 스크린 — 빔프로젝터·TV 에 띄우는 화면.
 * 순서표에서 바로 만들어지므로 파워포인트를 따로 만들 필요가 없다.
 */
export default async function StagePage({
  params,
  searchParams,
}: {
  params: { id: string }
  searchParams: { theme?: string; commentary?: string; sections?: string; agenda?: string }
}) {
  const repo = getRepository()
  const [academy, event] = await Promise.all([currentAcademy(), repo.getEvent(params.id)])
  if (!event) notFound()

  const students = await repo.listStudents(event.id)
  const { plan } = resolvePlan(students)
  const theme = getTheme(searchParams.theme ?? event.design_theme ?? academy.design_theme)
  const off = (value: string | undefined) => value !== '0'
  const slides = buildStageDeck(event, plan, academy.name, {
    ...DEFAULT_STAGE_OPTIONS,
    show_commentary: off(searchParams.commentary),
    show_sections: off(searchParams.sections),
    show_agenda: off(searchParams.agenda),
  })

  return (
    <AppShell academyName={academy.name} className="container py-8 print:max-w-none print:p-0">
      {/* PDF 로 저장하면 16:9 슬라이드가 한 장에 한 화면씩 들어간다 */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
            @media print {
              @page { size: ${STAGE_SLIDE_W}px ${STAGE_SLIDE_H}px; margin: 0; }
              html, body { background: #fff !important; }
            }
          `,
        }}
      />
      <div className="mb-5 no-print">
        <Link href={`/events/${event.id}`} className="text-sm text-muted-foreground hover:text-foreground">
          ← {event.title}
        </Link>
        <h1 className="mt-2 text-2xl font-bold tracking-tight">무대 화면</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {formatEventDate(event.event_at)} · 슬라이드 {slides.length}장 — 순서표가 바뀌면 이 화면도 함께 바뀝니다.
        </p>
        <p className="mt-2 rounded-md border border-border bg-secondary px-3 py-2 text-sm">
          노트북을 빔프로젝터·TV 에 연결하고 <strong>[전체화면]</strong> 을 누르세요. 넘기기는{' '}
          <strong>→ ← 화살표 · 스페이스 · 화면 클릭</strong> — 프레젠터(리모컨)도 그대로 됩니다.
          인터넷이 끊겨도 그대로 넘어갑니다.
        </p>
      </div>

      <StageScreen
        slides={slides}
        theme={theme}
        academyName={academy.name}
        logoUrl={resolveLogo(academy.assets ?? [], event.image_map, academy.logo_url)}
      />

      <p className="mt-4 text-sm text-muted-foreground no-print">
        <strong>PDF로 저장</strong>을 누르면 16:9 슬라이드 {slides.length}장이 한 파일로 나옵니다. USB 에 담아 가면
        공연장 노트북에서 그대로 넘길 수 있고, 파워포인트에 그림으로 넣어도 됩니다. 인쇄 대화상자에서{' '}
        <strong>배율 100% · 여백 없음 · 배경 그래픽 켜기</strong>로 두십시오.
      </p>
    </AppShell>
  )
}
