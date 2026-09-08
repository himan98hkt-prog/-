import { buildBundle, bundleFilename } from '@/lib/events/transfer'
import { fail, guard } from '@/lib/http'
import { getRepository } from '@/lib/store'

/**
 * 행사 하나를 파일 한 개로 내보낸다.
 *
 * 브라우저가 바로 내려받게 Content-Disposition 을 붙인다. 한글 파일 이름은
 * filename* (RFC 5987) 로 적어야 윈도우 탐색기에서도 깨지지 않는다.
 */
export async function GET(_req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const repo = getRepository()
    const event = await repo.getEvent(params.id)
    if (!event) return fail('행사를 찾을 수 없습니다.', 404)

    const [academy, students] = await Promise.all([repo.getAcademy(event.academy_id), repo.listStudents(event.id)])
    const bundle = buildBundle({
      academyName: academy?.name ?? '',
      event,
      students,
      assets: academy?.assets ?? [],
    })
    const name = bundleFilename(event.title, event.event_at)

    return new Response(JSON.stringify(bundle, null, 2), {
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Content-Disposition': `attachment; filename="event.json"; filename*=UTF-8''${encodeURIComponent(name)}`,
        'Cache-Control': 'no-store',
      },
    })
  })
}
