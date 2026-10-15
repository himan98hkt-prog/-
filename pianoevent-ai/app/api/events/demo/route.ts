import { randomUUID } from 'node:crypto'
import type { AcademyAsset } from '@/lib/assets'
import { DEMO_ROSTER, DEMO_TITLE, DEMO_VENUE, demoEventAt, demoFace } from '@/lib/events/demo-seed'
import { guard, ok } from '@/lib/http'
import { buildProgram } from '@/lib/program/order'
import { buildMcScript } from '@/lib/program/script'
import { resolvePlan } from '@/lib/program/resolve'
import { currentAcademyId } from '@/lib/session'
import { getRepository } from '@/lib/store'
import { DEFAULT_PROGRAM_OPTIONS } from '@/lib/types'

export const dynamic = 'force-dynamic'

/**
 * 구경용 행사를 하나 만들어 드린다.
 *
 * 아이 · 곡 · 사진 · 순서 · 사회자 멘트까지 **한 번에 다 채운다.** 그래야 인쇄물부터
 * 무대 화면 · 감동영상까지 그 자리에서 다 보실 수 있다. 하나라도 비면 그 화면에서
 * "아직 없습니다" 를 만나시고, 거기서 구경이 끝난다.
 *
 * 순서표는 AI 를 쓰지 않고 내장 규칙으로 만든다 — 구경하는 데 몇 초를 기다리실 이유가 없고,
 * 인터넷이 없어도 되어야 한다.
 */
export async function POST() {
  return guard(async () => {
    const repo = getRepository()
    const academy = await repo.ensureAcademy(currentAcademyId())

    // ── 사진 먼저. 명단이 사진 번호를 가리키므로 보관함에 있어야 붙는다
    const faces: AcademyAsset[] = DEMO_ROSTER.map((row, index) => ({
      id: randomUUID(),
      kind: 'photo' as const,
      label: `${row.student_name} (구경용)`,
      url: demoFace(index, DEMO_ROSTER.length),
      created_at: new Date().toISOString(),
    }))
    await repo.updateAcademy(academy.id, { assets: [...(academy.assets ?? []), ...faces] })

    // ── 행사와 명단
    const event = await repo.createEvent(academy.id, {
      title: DEMO_TITLE,
      type: 'recital',
      event_at: demoEventAt(),
      venue: DEMO_VENUE,
      greeting: '한 해 동안 아이들이 쌓아 온 시간을 부모님께 들려드리는 자리입니다.',
    })
    const students = await repo.addStudents(
      event.id,
      DEMO_ROSTER.map((row, index) => ({ ...row, photo_asset_id: faces[index].id })),
    )

    // ── 순서와 멘트까지 채워 둔다
    const plan = buildProgram(students, DEFAULT_PROGRAM_OPTIONS)
    const script = buildMcScript(plan, { eventTitle: event.title, academyName: academy.name })
    await repo.saveProgram(
      event.id,
      plan.items.map((item) => ({
        id: item.student.id,
        order_no: item.order_no,
        mc_script: script.byStudentId[item.student.id] ?? null,
      })),
    )
    await repo.updateEvent(event.id, {
      program_source: 'rule',
      program_generated_at: new Date().toISOString(),
      mc_opening: script.opening,
      mc_closing: script.closing,
    })

    const saved = await repo.listStudents(event.id)
    const { plan: ready } = resolvePlan(saved)
    return ok({ event, students: saved.length, order: ready.items.length }, 201)
  })
}
