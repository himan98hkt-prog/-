import { cookies } from 'next/headers'
import { getRepository } from '@/lib/store'
import type { Academy } from '@/lib/types'

export const ACADEMY_COOKIE = 'pe_academy'

/** 현재 브라우저에 연결된 학원. 없으면 만들어 준다. */
export async function currentAcademy(): Promise<Academy> {
  const id = cookies().get(ACADEMY_COOKIE)?.value
  return getRepository().ensureAcademy(id)
}

export function currentAcademyId(): string | undefined {
  return cookies().get(ACADEMY_COOKIE)?.value
}
