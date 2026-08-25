'use client'

import { createClient, type SupabaseClient } from '@supabase/supabase-js'

/** 브라우저용 Supabase 클라이언트 — RSVP 실시간 집계에만 쓴다. anon 키만 사용한다. */

let cached: SupabaseClient | null = null

export function getBrowserSupabase(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!url || !anonKey) return null
  if (!cached) cached = createClient(url, anonKey, { auth: { persistSession: false } })
  return cached
}
