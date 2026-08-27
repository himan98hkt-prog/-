import type { EventStudent, Level } from '@/lib/types'

let counter = 0

export function student(
  name: string,
  level: Level,
  duration: number,
  extra: Partial<EventStudent> = {},
): EventStudent {
  counter += 1
  return {
    id: extra.id ?? `s${counter}`,
    event_id: 'e1',
    student_name: name,
    piece_title: extra.piece_title ?? `${name}의 곡`,
    composer: extra.composer ?? '',
    duration_sec: duration,
    level,
    order_no: null,
    mc_script: null,
    note: null,
    photo_asset_id: null,
    created_at: '2026-01-01T00:00:00.000Z',
    ...extra,
  }
}
