import { keepWithinRetention, type RetentionPolicy } from '../core/retention';
import type { AnalysisEntry } from '../core/types';
import { isConfigured } from './config';
import { ApiError } from './errors';
import { supabase } from './supabase';

/**
 * 다이어리 백업 (프로 전용).
 *
 * 기록은 원래 기기에만 있다 — 폰을 바꾸면 몇 달치가 사라진다.
 * 사진·녹음 파일은 올리지 않는다. 경로는 다른 기기에서 의미가 없고,
 * 무엇보다 개인정보처리방침에 "미디어는 서버에 저장하지 않는다"고 적어 뒀다.
 */

/** 백업에 담기지 않는 필드 (로컬 파일 경로) */
function stripLocalMedia(entry: AnalysisEntry): AnalysisEntry {
  const { mediaUri: _mediaUri, audioUri: _audioUri, ...rest } = entry;
  return rest;
}

export async function backupEntries(entries: AnalysisEntry[]): Promise<number> {
  const sb = supabase();
  if (!sb || !isConfigured) throw new ApiError('server', '백업 서버가 설정되지 않았습니다.');

  const { data: userData } = await sb.auth.getUser();
  const userId = userData.user?.id;
  if (!userId) throw new ApiError('unauthorized', '세션이 없습니다.');

  const rows = entries.map((entry) => ({
    id: entry.id,
    user_id: userId,
    pet_id: entry.petId,
    created_at: new Date(entry.createdAt).toISOString(),
    health_level: entry.health.level,
    payload: stripLocalMedia(entry),
  }));

  // 한 번에 다 올리면 큰 요청이 되니 나눠 보낸다
  const CHUNK = 200;
  for (let i = 0; i < rows.length; i += CHUNK) {
    const { error } = await sb.from('analyses').upsert(rows.slice(i, i + CHUNK), { onConflict: 'id' });
    if (error) throw new ApiError('server', error.message);
  }
  return rows.length;
}

/**
 * 보관 기간이 지난 백업 행을 서버에서도 지운다.
 *
 * 기기만 정리하고 서버를 두면 두 곳의 규칙이 갈라진다.
 * 사용자는 "6개월만 보관"을 골랐는데 서버에는 2년치가 남아 있는 상태가 되고,
 * 그건 개인정보처리방침에 적어 둔 것과 다른 동작이다.
 *
 * 삭제는 RLS 로 자기 행만 닿는다. `user_id` 조건은 그 위에 한 번 더 거는 안전장치다.
 */
export async function pruneBackupBefore(cutoff: number): Promise<void> {
  const sb = supabase();
  if (!sb || !isConfigured) return;

  const { data: userData } = await sb.auth.getUser();
  const userId = userData.user?.id;
  if (!userId) return;

  const { error } = await sb
    .from('analyses')
    .delete()
    .eq('user_id', userId)
    .lt('created_at', new Date(cutoff).toISOString());

  if (error) throw new ApiError('server', error.message);
}

/**
 * 백업에서 되살린다.
 *
 * `policy` 를 넘기면 그 기간 밖 기록은 되살리지 않는다.
 * 예전 기기에서 만든 백업에는 지금 정책보다 오래된 것이 들어 있을 수 있다.
 */
export async function restoreEntries(policy: RetentionPolicy = 'forever'): Promise<AnalysisEntry[]> {
  const sb = supabase();
  if (!sb || !isConfigured) throw new ApiError('server', '백업 서버가 설정되지 않았습니다.');

  const { data, error } = await sb
    .from('analyses')
    .select('payload')
    .order('created_at', { ascending: false })
    .limit(2000);

  if (error) throw new ApiError('server', error.message);
  const restored = (data ?? [])
    .map((row) => row.payload as AnalysisEntry)
    .filter((entry): entry is AnalysisEntry => Boolean(entry?.id && entry?.result));

  return keepWithinRetention(restored, policy);
}
