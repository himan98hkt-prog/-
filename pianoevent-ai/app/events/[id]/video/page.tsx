import Link from 'next/link'
import { notFound } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { ScreenHeader } from '@/components/flow/screen-header'
import { VideoStudio } from '@/components/video/video-studio'
import { resolveLogo, studentPhotoList, studentPhotos } from '@/lib/assets'
import { getTheme } from '@/lib/design/themes'
import { formatEventDate } from '@/lib/format'
import { sharePhotosByName } from '@/lib/program/appearances'
import { resolvePlan } from '@/lib/program/resolve'
import { pastPrefs } from '@/lib/prefs-server'
import { currentAcademy } from '@/lib/session'
import { getRepository, summarizeRsvps } from '@/lib/store'

export const dynamic = 'force-dynamic'
export const metadata = { title: '감동영상' }

/**
 * 감동영상 — 사진과 영상, 음악을 모아 한 편으로 만든다.
 * 전부 이 컴퓨터 안에서 처리한다. 아이들 얼굴이 어디로도 올라가지 않는다.
 */
export default async function VideoPage({
  params,
  searchParams,
}: {
  params: { id: string }
  searchParams: { theme?: string }
}) {
  const repo = getRepository()
  const [academy, event] = await Promise.all([currentAcademy(), repo.getEvent(params.id)])
  if (!event) notFound()

  const [students, rsvps] = await Promise.all([repo.listStudents(event.id), repo.listRsvps(event.id)])
  const { plan } = resolvePlan(students)
  const theme = getTheme(searchParams.theme ?? event.design_theme ?? academy.design_theme)
  // 한 아이가 여러 곡을 맡으면 사진은 한 줄에만 붙어 있다 — 같은 이름끼리 나눠 쓴다
  const photos = sharePhotosByName(studentPhotos(academy.assets ?? [], students), students)
  const photoSets = studentPhotoList(academy.assets ?? [], students)
  // 학부모가 초대장에 남긴 응원 — 영상 끝에 흘린다
  const cheers = summarizeRsvps(rsvps).messages.map((row) => ({
    name: row.name,
    message: row.message,
    student: row.student,
  }))
  const past = await pastPrefs(repo, event, 'video_prefs')
  // 주소에 테마를 직접 적어 여셨다면 그쪽이 이깁니다 — 저장해 둔 값보다 방금 고른 것이 앞섭니다
  const savedPrefs = searchParams.theme
    ? { ...(event.video_prefs ?? {}), theme: theme.id }
    : event.video_prefs

  return (
    <AppShell academyName={academy.name}>
      <ScreenHeader
        step="video"
        eventId={event.id}
        eventTitle={event.title}
        state={{
          hasStudents: students.length > 0,
          hasProgram: event.program_source !== null,
          hasPrint: event.status === 'published' || event.design_template !== null,
        }}
      />

      <div className="mb-5">
        <p className="mt-1 text-sm text-muted-foreground">
          {formatEventDate(event.event_at)} · 학생 {plan.items.length}명 — 명단과 아이 사진에서 장면이 만들어집니다.
          연습 사진·동영상과 음악을 더하면 한 편이 됩니다.
        </p>
        <p className="mt-2 rounded-md border border-border bg-secondary px-3 py-2 text-sm">
          <strong>사진과 영상은 이 컴퓨터 밖으로 나가지 않습니다.</strong> 영상을 만드는 일도 이 브라우저 안에서
          합니다 — 올리는 곳도, 기다리는 줄도 없습니다. 다만 화면을 그리면서 담기 때문에{' '}
          <strong>영상 길이만큼 시간이 걸리고</strong>, 만드는 동안 이 창을 그대로 두셔야 합니다.
        </p>
      </div>

      <VideoStudio
        event={event}
        plan={plan}
        academyName={academy.name}
        initialThemeId={theme.id}
        photos={photos}
        photoSets={photoSets}
        messages={cheers}
        logoUrl={resolveLogo(academy.assets ?? [], event.image_map, academy.logo_url)}
        savedPrefs={savedPrefs}
        pastPrefs={past}
      />

      <div className="mt-5 grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
        <p className="rounded-md border border-border px-3 py-2.5">
          <strong className="text-foreground">언제 쓰나요</strong> — 개회 전 대기 시간에 스크린에 틀거나,
          연주회가 끝난 뒤 학부모 단톡방에 보냅니다. 시상식 전에 틀면 객석이 조용해집니다.
        </p>
        <p className="rounded-md border border-border px-3 py-2.5">
          <strong className="text-foreground">음악은 직접 준비하십시오</strong> — 이 프로그램은 음원을 제공하지
          않습니다. 저작권이 있는 곡을 학원 밖으로 공개하면 문제가 될 수 있습니다.
        </p>
      </div>
    </AppShell>
  )
}
