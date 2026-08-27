import { studentPhotos } from '@/lib/assets'
import { getTheme } from '@/lib/design/themes'
import { resolvePlan } from '@/lib/program/resolve'
import { buildStageDeck, DEFAULT_STAGE_OPTIONS } from '@/lib/stage/deck'
import { buildPptx } from '@/lib/stage/pptx'
import { getRepository } from '@/lib/store'

export const dynamic = 'force-dynamic'

/**
 * 무대 화면을 파워포인트 파일(.pptx)로 내려받는다.
 *
 * 인터넷도 외부 서비스도 쓰지 않는다 — 이 컴퓨터에서 XML 을 만들어 ZIP 으로 묶어 보낸다.
 * 슬라이드가 그림이 아니라 글상자라, 받은 파일을 파워포인트에서 바로 고칠 수 있다.
 */
export async function GET(req: Request, { params }: { params: { id: string } }) {
  const repo = getRepository()
  const event = await repo.getEvent(params.id)
  if (!event) return new Response('행사를 찾을 수 없습니다.', { status: 404 })

  const [academy, students] = await Promise.all([repo.getAcademy(event.academy_id), repo.listStudents(event.id)])
  if (!academy) return new Response('학원을 찾을 수 없습니다.', { status: 404 })

  const url = new URL(req.url)
  const off = (key: string) => url.searchParams.get(key) !== '0'
  const { plan } = resolvePlan(students)
  const theme = getTheme(url.searchParams.get('theme') ?? event.design_theme ?? academy.design_theme)
  const slides = buildStageDeck(
    event,
    plan,
    academy.name,
    {
      ...DEFAULT_STAGE_OPTIONS,
      show_commentary: off('commentary'),
      show_sections: off('sections'),
      show_agenda: off('agenda'),
      show_photos: off('photos'),
    },
    studentPhotos(academy.assets ?? [], students),
  )

  const file = buildPptx({
    slides,
    theme,
    academyName: academy.name,
    title: `${event.title} · 무대 화면`,
    dark: url.searchParams.get('dark') === '1',
  })

  // 한글 파일명은 브라우저마다 다루는 법이 달라 RFC 5987 형식을 함께 보낸다
  const name = `${event.title.replace(/[\\/:*?"<>|]/g, ' ').trim() || '연주회'} 무대화면.pptx`
  return new Response(file.buffer as ArrayBuffer, {
    headers: {
      'Content-Type': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      'Content-Disposition': `attachment; filename="stage.pptx"; filename*=UTF-8''${encodeURIComponent(name)}`,
      'Content-Length': String(file.length),
      'Cache-Control': 'no-store',
    },
  })
}
