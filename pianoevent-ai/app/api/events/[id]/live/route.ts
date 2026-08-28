import { guard, fail, ok, readJson } from '@/lib/http'
import { buildLiveList, normalizeLiveState, newerLiveState, EMPTY_LIVE_STATE } from '@/lib/ops/live'
import { resolvePlan } from '@/lib/program/resolve'
import { getRepository } from '@/lib/store'

/**
 * 당일 진행 상태 — 스태프 여러 명이 같은 화면을 보게 하는 자리.
 *
 * 무대 옆에서 원장님이 넘기면 대기실 강사 화면도 함께 넘어가야 한다.
 * 그래서 "지금 몇 번째" 만 서버에 둔다. 계산은 각자 화면에서 한다.
 *
 * 인터넷이 끊기면 이 요청만 실패하고 각자 휴대폰 안에서 그대로 돈다 —
 * 당일에 서버 때문에 순서를 놓치는 일은 없어야 한다.
 */

export async function GET(_req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const event = await getRepository().getEvent(params.id)
    if (!event) return fail('행사를 찾을 수 없습니다.', 404)
    // 몇 초마다 들어오는 요청이다. 순서표까지 다시 세지 않는다 —
    // 길이에 맞춰 다듬는 일은 목록을 들고 있는 화면 쪽에서 한다
    return ok({ live: normalizeLiveState(event.live_state) })
  })
}

export async function POST(req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const repo = getRepository()
    const event = await repo.getEvent(params.id)
    if (!event) return fail('행사를 찾을 수 없습니다.', 404)

    // 올릴 때만 순서표 길이를 확인한다 — 엉뚱한 자리가 저장되면 모두가 그걸 본다
    const { plan } = resolvePlan(await repo.listStudents(params.id))
    const total = buildLiveList(plan).length
    const incoming = normalizeLiveState((await readJson(req)).live, total)
    const stored = normalizeLiveState(event.live_state, total)
    // 늦게 도착한 옛날 상태가 새 상태를 덮지 않게 — 손댄 시각이 나중인 쪽이 이긴다
    const next = newerLiveState(stored, incoming)
    if (next === stored && stored.updated_at !== 0) return ok({ live: stored })

    return ok({ live: (await repo.updateEvent(params.id, { live_state: next })).live_state ?? EMPTY_LIVE_STATE })
  })
}

/** 진행 상태를 지운다 — 리허설로 돌려 본 뒤 처음으로 */
export async function DELETE(_req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    await getRepository().updateEvent(params.id, { live_state: null })
    return ok({ cleared: true })
  })
}
