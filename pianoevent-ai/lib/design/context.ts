import type { DesignTheme } from '@/lib/design/themes'
import type { Academy, EventRecord, ProgramPlan } from '@/lib/types'

/** 원장이 직접 고쳐 쓰는 문구 */
export interface DesignCopy {
  subtitle: string
  host: string
  contact: string
  footnote: string
}

export function defaultCopy(academy: Academy, event: EventRecord): DesignCopy {
  return {
    subtitle: event.type === 'season' ? '시즌 특강 발표회' : '정기 연주회',
    host: `주최 · ${academy.name}`,
    contact: '',
    footnote: '연주 중에는 휴대전화를 무음으로 해 주시고, 곡이 끝난 뒤 박수로 응원해 주세요.',
  }
}

export interface DesignContext {
  theme: DesignTheme
  academy: Academy
  event: EventRecord
  plan: ProgramPlan
  copy: DesignCopy
  /** 초대장 링크 — 포스터·카드 하단 안내에 쓴다 */
  inviteUrl: string
}
