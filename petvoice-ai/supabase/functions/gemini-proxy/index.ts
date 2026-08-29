// supabase/functions/gemini-proxy/index.ts
//
// 앱과 Gemini 사이의 유일한 통로.
//   [App] --Bearer user token--> [이 함수] --GEMINI_API_KEY--> [Gemini]
//
// 여기서 하는 일:
//   1. 사용자 토큰 검증 (익명 계정도 실제 auth.users 행이 있다)
//   2. 서버 기준 사용량 제한 — 클라이언트의 "하루 3회"는 우회 가능하므로 여기가 진짜 방어선
//   3. 입력 검증 (mime 타입 / 용량 / 프롬프트 길이)
//   4. Gemini 호출 후 텍스트만 그대로 전달
//
// 배포:
//   supabase secrets set GEMINI_API_KEY=...
//   supabase functions deploy gemini-proxy

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const GEMINI_API_KEY = Deno.env.get('GEMINI_API_KEY');
const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SUPABASE_ANON_KEY = Deno.env.get('SUPABASE_ANON_KEY')!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;

const FREE_DAILY_LIMIT = 3;
const MAX_MEDIA_BYTES = 5 * 1024 * 1024;
const MAX_PROMPT_CHARS = 8000;
const ALLOWED_MIME = new Set([
  'audio/m4a',
  'audio/mp4',
  'audio/mpeg',
  'audio/wav',
  'image/jpeg',
  'image/png',
]);
// 화이트리스트에만 있으면 클라이언트가 순서를 정할 수 있다.
// 구글이 모델을 갈아치워도 앱을 새로 배포하지 않게 하려는 것.
const ALLOWED_MODELS = new Set([
  'gemini-2.5-flash',
  'gemini-2.5-flash-lite',
  'gemini-2.0-flash',
  'gemini-2.0-flash-lite',
  'gemini-1.5-flash',
  'gemini-1.5-flash-8b',
]);
const DEFAULT_MODELS = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash'];

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
};

/**
 * 분석 품질 지표.
 * 실패해도 요청을 막지 않는다 — 지표 때문에 분석이 안 되면 본말전도다.
 * 개인 식별 정보나 미디어는 넣지 않는다.
 */
async function recordMetric(
  admin: { from: (table: string) => { insert: (row: unknown) => Promise<{ error: unknown }> } },
  entry: { model: string; mediaKind: string; outcome: string; startedAt: number; status?: number },
): Promise<void> {
  try {
    await admin.from('analysis_metrics').insert({
      model: entry.model,
      media_kind: entry.mediaKind,
      outcome: entry.outcome,
      latency_ms: Date.now() - entry.startedAt,
      status_code: entry.status ?? null,
    });
  } catch (error) {
    console.error('metric insert failed', String(error));
  }
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, 'Content-Type': 'application/json' },
  });
}

function text(body: string, status = 200): Response {
  return new Response(body, { status, headers: { ...CORS, 'Content-Type': 'application/json' } });
}

/** base64 문자열의 실제 바이트 수 (디코딩하지 않고 계산) */
function base64Bytes(data: string): number {
  const padding = data.endsWith('==') ? 2 : data.endsWith('=') ? 1 : 0;
  return Math.floor((data.length * 3) / 4) - padding;
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS });
  if (req.method !== 'POST') return json({ error: 'method_not_allowed' }, 405);
  if (!GEMINI_API_KEY) return json({ error: 'server_misconfigured' }, 500);

  // 1) 인증 --------------------------------------------------------------
  const authHeader = req.headers.get('Authorization');
  if (!authHeader?.startsWith('Bearer ')) return json({ error: 'unauthorized' }, 401);

  const userClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    global: { headers: { Authorization: authHeader } },
  });
  const { data: userData, error: userError } = await userClient.auth.getUser();
  if (userError || !userData.user) return json({ error: 'unauthorized' }, 401);
  const userId = userData.user.id;

  // 2) 입력 검증 ---------------------------------------------------------
  let payload: {
    task?: string;
    model?: string;
    models?: string[];
    prompt?: string;
    responseSchema?: unknown;
    temperature?: number;
    media?: { mimeType?: string; data?: string };
  };
  try {
    payload = await req.json();
  } catch {
    return json({ error: 'invalid_json' }, 400);
  }

  const requested = payload.models ?? (payload.model ? [payload.model] : []);
  const models = requested.filter((m) => ALLOWED_MODELS.has(m));
  const chain = models.length > 0 ? models : DEFAULT_MODELS;
  const prompt = (payload.prompt ?? '').toString();
  if (!prompt || prompt.length > MAX_PROMPT_CHARS) return json({ error: 'invalid_prompt' }, 400);

  const media = payload.media;
  if (media) {
    if (!media.mimeType || !ALLOWED_MIME.has(media.mimeType))
      return json({ error: 'unsupported_media' }, 415);
    if (!media.data || base64Bytes(media.data) > MAX_MEDIA_BYTES)
      return json({ error: 'media_too_large' }, 413);
  }

  // 3) 사용량 제한 (서버 기준) -------------------------------------------
  const admin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
  const { data: allowed, error: quotaError } = await admin.rpc('consume_quota', {
    p_user_id: userId,
    p_free_limit: FREE_DAILY_LIMIT,
  });
  if (quotaError) return json({ error: 'quota_check_failed' }, 500);
  if (allowed === false) {
    await recordMetric(admin, {
      model: chain[0],
      mediaKind: 'none',
      outcome: 'quota',
      startedAt: Date.now(),
    });
    return json({ error: 'quota_exceeded' }, 402);
  }

  // 4) Gemini 호출 -------------------------------------------------------
  const parts: unknown[] = [];
  if (media?.data && media.mimeType) {
    parts.push({ inline_data: { mime_type: media.mimeType, data: media.data } });
  }
  parts.push({ text: prompt });

  const mediaKind = media?.mimeType?.startsWith('audio') ? 'audio' : media ? 'image' : 'none';

  const generationConfig: Record<string, unknown> = {
    responseMimeType: 'application/json',
    temperature: typeof payload.temperature === 'number' ? payload.temperature : 0.4,
  };
  if (payload.responseSchema) generationConfig.responseSchema = payload.responseSchema;

  /**
   * 앞에서부터 시도한다.
   * 모델이 없거나(404) 요청을 거절하면(400) 다음 모델로 내려가고,
   * 과부하(429)나 서버 오류는 그대로 올려 보낸다 — 그건 모델을 바꿔도 같은 결과다.
   */
  const startedAt = Date.now();
  let body: unknown = null;
  let lastStatus = 0;
  let usedModel = '';

  for (const model of chain) {
    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${GEMINI_API_KEY}`;

    let upstream: Response;
    try {
      upstream = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contents: [{ role: 'user', parts }], generationConfig }),
      });
    } catch {
      await recordMetric(admin, { model, mediaKind, outcome: 'upstream_error', startedAt });
      return json({ error: 'upstream_unreachable' }, 502);
    }

    if (upstream.ok) {
      body = await upstream.json();
      usedModel = model;
      break;
    }

    lastStatus = upstream.status;
    // 상류 오류 본문에는 키가 섞일 수 있으므로 그대로 전달하지 않는다.
    console.error('gemini error', model, upstream.status, await upstream.text().catch(() => ''));

    // 이 모델을 못 쓰는 경우에만 다음 후보로 내려간다
    if (upstream.status === 404 || upstream.status === 400) continue;
    await recordMetric(admin, {
      model,
      mediaKind,
      outcome: 'upstream_error',
      startedAt,
      status: upstream.status,
    });
    return json({ error: 'upstream_error' }, upstream.status === 429 ? 429 : 502);
  }

  if (body == null) {
    await recordMetric(admin, {
      model: chain.join(','),
      mediaKind,
      outcome: 'upstream_error',
      startedAt,
      status: lastStatus,
    });
    return json({ error: 'no_usable_model' }, 502);
  }

  const output =
    (body as { candidates?: { content?: { parts?: { text?: string }[] } }[] }).candidates?.[0]?.content?.parts
      ?.map((p) => p.text ?? '')
      .join('') ?? '';

  if (!output) {
    await recordMetric(admin, { model: usedModel, mediaKind, outcome: 'empty', startedAt });
    return json({ error: 'empty_response' }, 502);
  }

  await recordMetric(admin, { model: usedModel, mediaKind, outcome: 'ok', startedAt });
  return text(output);
});
