/**
 * 클라이언트 설정.
 *
 * `EXPO_PUBLIC_*` 는 앱 번들에 그대로 박히는 값이다. 그래서 여기에는
 * **공개돼도 안전한 값만** 둔다. Gemini 키가 실수로 들어오면 개발 중에 바로 터뜨린다.
 */

export const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL ?? '';
export const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? '';

/** 설정이 비어 있으면 데모 모드(모의 응답)로 동작한다. */
export const isConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);

/**
 * Play Console 보안 스캔 대비 가드레일.
 * 클라이언트 번들에 AI 제공자 키가 들어오면 개발/테스트 단계에서 즉시 실패시킨다.
 */
export function assertNoAiKeyInClient(env: Record<string, string | undefined> = process.env as never): void {
  const leaked = Object.keys(env).filter((key) =>
    /^(EXPO_PUBLIC_|REACT_APP_|NEXT_PUBLIC_)/.test(key) && /(GEMINI|GOOGLE_AI|GENAI|OPENAI|ANTHROPIC)_?API_?KEY/i.test(key),
  );
  if (leaked.length > 0) {
    throw new Error(
      `[보안] AI API 키가 클라이언트 환경변수에 노출됐습니다: ${leaked.join(', ')}\n` +
        'Supabase Edge Function 의 서버 환경변수로 옮기세요. (README 보안 아키텍처 참고)',
    );
  }
}
