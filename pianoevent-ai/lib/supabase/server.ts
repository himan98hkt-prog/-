import { createClient, type SupabaseClient } from '@supabase/supabase-js'

/**
 * 서버 전용 Supabase 클라이언트.
 * service_role 키가 있으면 그것을, 없으면 anon 키를 쓴다.
 * service_role 키는 절대 클라이언트로 내려보내지 않는다.
 */

const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim()
const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY?.trim()
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim()

export function isSupabaseConfigured(): boolean {
  return Boolean(url && (serviceKey || anonKey))
}

let cached: SupabaseClient | null = null

export function getServerSupabase(): SupabaseClient {
  if (!url || !(serviceKey || anonKey)) {
    throw new Error('Supabase 환경변수가 없습니다. NEXT_PUBLIC_SUPABASE_URL 과 키를 설정하세요.')
  }
  if (!cached) {
    cached = createClient(url, (serviceKey ?? anonKey)!, {
      auth: { persistSession: false, autoRefreshToken: false },
    })
  }
  return cached
}
