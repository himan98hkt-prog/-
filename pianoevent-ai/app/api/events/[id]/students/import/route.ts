import { carryPhotoIds } from '@/lib/assets'
import { averageTiming, normalizeTimingLog } from '@/lib/ops/timing'
import { fail, guard, ok, readJson, str } from '@/lib/http'
import { getRepository } from '@/lib/store'

/**
 * 지난 행사에서 명단 가져오기.
 *
 * 학원은 학생이 그대로다. 매 행사마다 12~30명을 다시 치는 것이 가장 반복되는 일이라
 * 이름과 난이도는 가져오고 곡은 비워 준다. 원장은 곡만 채우면 된다.
 */
export async function POST(req: Request, { params }: { params: { id: string } }) {
  return guard(async () => {
    const repo = getRepository()
    const target = await repo.getEvent(params.id)
    if (!target) return fail('행사를 찾을 수 없습니다.', 404)

    const body = await readJson(req)
    const sourceId = str(body.from_event_id, 60)
    if (!sourceId) return fail('어느 행사에서 가져올지 골라 주세요.')
    if (sourceId === params.id) return fail('같은 행사에서는 가져올 수 없습니다.')

    const source = await repo.getEvent(sourceId)
    if (!source || source.academy_id !== target.academy_id) {
      return fail('그 행사를 찾을 수 없습니다.', 404)
    }

    const rows = await repo.listStudents(sourceId)
    if (rows.length === 0) return fail('가져올 학생이 없는 행사입니다.')

    // 곡까지 그대로 가져올지, 이름만 가져올지 — 기본은 이름만
    const keepPieces = body.keep_pieces === true
    // 사진은 기본으로 따라온다. 보관함은 학원 것이고 아이도 그 아이다 —
    // 30명 얼굴을 해마다 다시 짝지을 이유가 없다. (그 사이 지운 사진은 뺀다)
    const keepPhotos = body.keep_photos !== false
    const academy = await repo.getAcademy(target.academy_id)
    const assets = keepPhotos ? (academy?.assets ?? []) : []
    // 곡을 비우고 이름만 가져올 때는 난이도로 추정할 수밖에 없다.
    // 그 아이가 지난 무대에서 실제로 걸린 시간이 있으면 그쪽이 낫다.
    const timings = normalizeTimingLog(academy?.timing_log)

    const imported = await repo.replaceStudents(
      params.id,
      rows.map((row) => {
        const photos = keepPhotos ? carryPhotoIds(assets, row) : []
        return {
          student_name: row.student_name,
          piece_title: keepPieces ? row.piece_title : '',
          composer: keepPieces ? row.composer : '',
          duration_sec: keepPieces ? row.duration_sec : averageTiming(timings, row.student_name),
          level: row.level,
          note: row.note,
          photo_asset_id: photos[0] ?? null,
          photo_asset_ids: photos.length > 1 ? photos : null,
        }
      }),
    )

    const withPhoto = imported.filter((row) => row.photo_asset_id).length
    const withTiming = keepPieces
      ? 0
      : rows.filter((row) => averageTiming(timings, row.student_name) !== null).length
    return ok(
      { students: imported, from: source.title, keep_pieces: keepPieces, with_photo: withPhoto, with_timing: withTiming },
      201,
    )
  })
}
