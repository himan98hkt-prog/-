import Link from 'next/link'
import { notFound } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { ScreenHeader } from '@/components/flow/screen-header'
import { StageScreen } from '@/components/stage/stage-screen'
import { resolveLogo, studentPhotos } from '@/lib/assets'
import { getTheme } from '@/lib/design/themes'
import { formatEventDate } from '@/lib/format'
import { sharePhotosByName } from '@/lib/program/appearances'
import { resolvePlan } from '@/lib/program/resolve'
import { pastPrefs } from '@/lib/prefs-server'
import { currentAcademy } from '@/lib/session'
import { buildStageDeck, STAGE_SLIDE_H, STAGE_SLIDE_W } from '@/lib/stage/deck'
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
  searchParams: { theme?: string }
}) {
  const repo = getRepository()
  const [academy, event] = await Promise.all([currentAcademy(), repo.getEvent(params.id)])
  if (!event) notFound()

  const students = await repo.listStudents(event.id)
  const { plan } = resolvePlan(students)
  const theme = getTheme(searchParams.theme ?? event.design_theme ?? academy.design_theme)
  // 장수는 화면에서 테마·항목을 바꿔도 바뀌므로 첫 화면에 보일 값만 계산한다
  const slideCount = buildStageDeck(event, plan, academy.name).length
  // 한 아이가 여러 곡을 맡으면 사진은 한 줄에만 붙어 있다 — 같은 이름끼리 나눠 쓴다
  const photos = sharePhotosByName(studentPhotos(academy.assets ?? [], students), students)
  const withPhoto = Object.keys(photos).length
  const past = await pastPrefs(repo, event, 'stage_prefs')
  // 주소에 테마를 직접 적어 여셨다면 그쪽이 이깁니다 — 저장해 둔 값보다 방금 고른 것이 앞섭니다
  const savedPrefs = searchParams.theme
    ? { ...(event.stage_prefs ?? {}), theme: theme.id }
    : event.stage_prefs

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
      <ScreenHeader
        step="stage"
        eventId={event.id}
        eventTitle={event.title}
        state={{
          hasStudents: students.length > 0,
          hasProgram: event.program_source !== null,
          hasPrint: event.status === 'published' || event.design_template !== null,
        }}
      />

      <div className="mb-5 no-print">
        <p className="mt-1 text-sm text-muted-foreground">
          {formatEventDate(event.event_at)} · 학생 {plan.items.length}명 · 슬라이드 {slideCount}장 — 명단과 순서표에서
          바로 만들어집니다. 순서를 바꾸면 이 화면도 함께 바뀝니다.
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {withPhoto > 0 ? (
            <>
              아이 사진 <strong className="text-foreground">{withPhoto}명</strong> 분이 연주자 화면에 함께 올라갑니다.
              {withPhoto < plan.items.length && ` 나머지 ${plan.items.length - withPhoto}명은 이름만 나옵니다 — `}
              {withPhoto < plan.items.length && (
                <Link href={`/events/${event.id}?tab=roster`} className="underline underline-offset-4">
                  명단에서 사진 넣기
                </Link>
              )}
            </>
          ) : (
            <>
              <Link href={`/events/${event.id}?tab=roster`} className="underline underline-offset-4">
                명단에서 아이 사진
              </Link>
              을 넣으면 연주자 화면에 그 얼굴이 함께 올라갑니다. 웃는 사진 한 장이 객석을 조용하게 만듭니다.
            </>
          )}
        </p>
        <p className="mt-2 rounded-md border border-border bg-secondary px-3 py-2 text-sm">
          노트북을 빔프로젝터·TV 에 연결하고 <strong>[전체화면]</strong> 을 누르세요. 넘기기는{' '}
          <strong>→ ← 화살표 · 스페이스 · 화면 클릭</strong> — 프레젠터(리모컨)도 그대로 됩니다.
          인터넷이 끊겨도 그대로 넘어갑니다.
        </p>
      </div>

      <StageScreen
        event={event}
        plan={plan}
        academyName={academy.name}
        initialThemeId={theme.id}
        photos={photos}
        logoUrl={resolveLogo(academy.assets ?? [], event.image_map, academy.logo_url)}
        savedPrefs={savedPrefs}
        pastPrefs={past}
      />

      <div className="mt-4 grid gap-2 text-sm text-muted-foreground no-print sm:grid-cols-2">
        <p className="rounded-md border border-border px-3 py-2.5">
          <strong className="text-foreground">파워포인트로 받기</strong> — 진짜 <code>.pptx</code> 파일입니다.
          슬라이드가 그림이 아니라 <strong>글상자</strong>라 파워포인트에서 이름 하나도 바로 고칠 수 있습니다.
          고른 테마의 색과 서체가 그대로 들어갑니다.
        </p>
        <p className="rounded-md border border-border px-3 py-2.5">
          <strong className="text-foreground">PDF로 저장</strong> — 16:9 슬라이드가 한 파일로 나옵니다. 어느 노트북에서나
          그대로 넘어갑니다. 인쇄 대화상자에서{' '}
          <strong>배율 100% · 여백 없음 · 배경 그래픽 켜기</strong>로 두십시오.
        </p>
      </div>
    </AppShell>
  )
}
