import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fail, guard } from '@/lib/http'
import { concatList, findFfmpeg, joinWithFfmpeg } from '@/lib/video/ffmpeg'

export const dynamic = 'force-dynamic'
/** 8분짜리 두 토막이면 파일이 제법 크다 */
export const maxDuration = 300

/**
 * 토막 이어 붙이기 — 이 컴퓨터에 ffmpeg 이 있을 때만.
 *
 * 있으면 몇 초, 없으면 화면에서 하던 대로(실제 시간만큼) 한다.
 * 원장님께는 묻지 않는다 — 화면이 알아서 이쪽을 먼저 두드려 보고, 안 되면 조용히 제 길로 간다.
 *
 * 파일은 이 컴퓨터의 임시 자리에서만 오간다. 끝나면 지운다.
 */
export async function GET() {
  return Response.json({ ok: true, available: findFfmpeg() !== null })
}

export async function POST(req: Request) {
  return guard(async () => {
    const bin = findFfmpeg()
    if (!bin) return fail('이 컴퓨터에는 빠른 잇기 도구가 없습니다.', 501)

    const form = await req.formData()
    const parts = form.getAll('parts').filter((item): item is File => item instanceof File)
    if (parts.length < 2) return fail('이을 토막이 두 개는 있어야 합니다.')

    const dir = await mkdtemp(path.join(tmpdir(), 'pianoevent-join-'))
    try {
      const paths: string[] = []
      for (const [index, file] of parts.entries()) {
        const ext = file.name.toLowerCase().endsWith('.mp4') ? 'mp4' : 'webm'
        const spot = path.join(dir, `part-${String(index).padStart(3, '0')}.${ext}`)
        await writeFile(spot, Buffer.from(await file.arrayBuffer()))
        paths.push(spot)
      }
      const listPath = path.join(dir, 'list.txt')
      await writeFile(listPath, concatList(paths), 'utf8')

      const outExt = paths[0].endsWith('.mp4') ? 'mp4' : 'webm'
      const outPath = path.join(dir, `joined.${outExt}`)
      const result = joinWithFfmpeg(bin, listPath, outPath)
      if (!result.ok) return fail(`이어 붙이지 못했습니다. ${result.error ?? ''}`.trim(), 500)

      const bytes = await readFile(outPath)
      return new Response(new Uint8Array(bytes), {
        headers: {
          'Content-Type': outExt === 'mp4' ? 'video/mp4' : 'video/webm',
          'X-Reencoded': result.reencoded ? '1' : '0',
          'Cache-Control': 'no-store',
        },
      })
    } finally {
      await rm(dir, { recursive: true, force: true })
    }
  })
}
