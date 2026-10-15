import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { SUPABASE_ANON_KEY, SUPABASE_URL, isConfigured } from './config';

/**
 * 익명 로그인 기반. 사용자는 회원가입 없이 앱을 쓰고,
 * 서버는 그 익명 사용자 토큰으로 요청자를 식별·제한한다.
 */
let client: SupabaseClient | null = null;

export function supabase(): SupabaseClient | null {
  if (!isConfigured) return null;
  if (!client) {
    client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        storage: AsyncStorage,
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: false,
      },
    });
  }
  return client;
}

/** 세션이 없으면 익명으로 만든다. 앱 시작 시 1회 호출. */
export async function ensureSession(): Promise<string | null> {
  const sb = supabase();
  if (!sb) return null;

  const { data } = await sb.auth.getSession();
  if (data.session) return data.session.access_token;

  const { data: signed, error } = await sb.auth.signInAnonymously();
  if (error) return null;
  return signed.session?.access_token ?? null;
}

export async function getAccessToken(): Promise<string | null> {
  const sb = supabase();
  if (!sb) return null;
  const { data } = await sb.auth.getSession();
  return data.session?.access_token ?? (await ensureSession());
}

/**
 * 계정 및 데이터 삭제 (Google Play 필수 요건).
 * 서버 함수가 `auth.users` 행을 지우고, 스키마의 ON DELETE CASCADE 로
 * 프로필·히스토리·사용량 기록이 함께 사라진다.
 */
export async function deleteAccount(): Promise<void> {
  const sb = supabase();
  if (!sb) return;
  const { error } = await sb.functions.invoke('delete-account', { method: 'POST' });
  if (error) throw error;
  await sb.auth.signOut();
}
