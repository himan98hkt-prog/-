import { guard, ok } from '@/lib/http'
import { getRepository, summarizeRsvps } from '@/lib/store'

/** 원장 화면의 참석 집계 (폴링용) */
export async function GET(_req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const rsvps = await getRepository().listRsvps(params.id)
    return ok({ rsvps, summary: summarizeRsvps(rsvps) })
  })
}
