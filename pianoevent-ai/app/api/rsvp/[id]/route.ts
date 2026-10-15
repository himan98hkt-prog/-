import { guard, ok } from '@/lib/http'
import { getRepository } from '@/lib/store'

/** 원장이 잘못 들어온 회신을 지운다 */
export async function DELETE(_req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    await getRepository().deleteRsvp(params.id)
    return ok({ deleted: true })
  })
}
