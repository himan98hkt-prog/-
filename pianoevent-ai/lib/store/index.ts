import { DemoRepository } from '@/lib/store/demo'
import { SupabaseRepository } from '@/lib/store/supabase'
import { isSupabaseConfigured } from '@/lib/supabase/server'
import type { Repository } from '@/lib/store/types'

let cached: Repository | null = null

/**
 * Supabase 환경변수가 있으면 Supabase, 없으면 데모 드라이버.
 * 덕분에 설치 직후 `npm run dev` 만으로 전 기능을 확인할 수 있다.
 */
export function getRepository(): Repository {
  if (!cached) cached = isSupabaseConfigured() ? new SupabaseRepository() : new DemoRepository()
  return cached
}

export * from '@/lib/store/types'
