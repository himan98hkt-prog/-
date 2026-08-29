import type { AnalysisEntry, Locale } from '../core/types';
import { isConfigured } from './config';
import { supabase } from './supabase';

/**
 * "맞아요 / 아니에요" 수집.
 *
 * 어떤 상황에서 어떤 감정을 틀리는지가 보이면 프롬프트를 고칠 근거가 생긴다.
 * 지금부터 모아야 나중에 쓴다.
 *
 * 보내는 것은 판정과 분류값뿐이다 — 사진·녹음·분석 문장은 올리지 않는다.
 * 실패해도 조용히 넘어간다. 피드백 때문에 사용자 흐름이 끊기면 안 된다.
 */
export async function sendFeedback(
  entry: AnalysisEntry,
  verdict: 'up' | 'down',
  locale: Locale,
): Promise<void> {
  const sb = supabase();
  if (!sb || !isConfigured) return;

  try {
    const { data } = await sb.auth.getUser();
    const userId = data.user?.id;
    if (!userId) return;

    await sb.from('analysis_feedback').upsert(
      {
        user_id: userId,
        entry_id: entry.id,
        verdict,
        emotion: entry.result.primaryEmotion,
        context_key: entry.contextKey ?? null,
        media_kind: entry.mediaKind,
        locale,
      },
      { onConflict: 'user_id,entry_id' },
    );
  } catch {
    // 의도적으로 삼킨다
  }
}
