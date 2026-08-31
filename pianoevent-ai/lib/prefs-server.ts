import { hasPrefs, type Prefs } from '@/lib/prefs'
import type { Repository } from '@/lib/store/types'
import type { EventRecord } from '@/lib/types'

/**
 * 설정을 저장해 둔 지난 행사들 — "작년 것 불러오기" 목록.
 *
 * 연주회는 해마다 돌아온다. 작년에 맞춰 둔 화면을 다시 만들 이유가 없다.
 * 최근 것부터 몇 개만 보여 준다 — 목록이 길면 고르기 어려워진다.
 */
export async function pastPrefs(
  repo: Repository,
  event: EventRecord,
  field: 'stage_prefs' | 'video_prefs',
  limit = 8,
): Promise<{ id: string; title: string; prefs: Prefs }[]> {
  const siblings = await repo.listEvents(event.academy_id)
  return siblings
    .filter((item) => item.id !== event.id && hasPrefs(item[field]))
    .slice(0, limit)
    .map((item) => ({ id: item.id, title: item.title, prefs: item[field] as Prefs }))
}
