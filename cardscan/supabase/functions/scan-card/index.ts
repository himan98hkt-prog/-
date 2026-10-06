// Supabase Edge Function: POST { image: base64, mediaType } → { fields, extra, note }
// 배포: supabase functions deploy scan-card   (자세한 순서는 cardscan/README.md)
// 비밀값: supabase secrets set ANTHROPIC_API_KEY=... APP_SHARED_SECRET=...
import Anthropic from '@anthropic-ai/sdk';
import { ExtractError, extractCard, ImageMediaType } from './extract.ts';

const client = new Anthropic({ apiKey: Deno.env.get('ANTHROPIC_API_KEY') });
const SHARED_SECRET = Deno.env.get('APP_SHARED_SECRET') ?? '';
const MAX_BASE64 = 7_000_000; // 약 5MB 이미지 — 앱은 1600px 로 줄여서 보내므로 보통 300KB 안팎
const MEDIA_TYPES: ImageMediaType[] = ['image/jpeg', 'image/png', 'image/webp'];

function timingSafeEqual(a: string, b: string): boolean {
  const x = new TextEncoder().encode(a);
  const y = new TextEncoder().encode(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] ?? 0) ^ (y[i] ?? 0);
  return diff === 0;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json; charset=utf-8' } });

Deno.serve(async (req) => {
  if (req.method !== 'POST') return json({ error: 'POST 만 지원합니다' }, 405);
  // 비밀키 없이 열어 두면 누구나 API 크레딧을 쓸 수 있으므로 설정을 강제한다
  if (!SHARED_SECRET) return json({ error: '서버에 APP_SHARED_SECRET 이 설정되지 않았습니다' }, 500);
  if (!timingSafeEqual(req.headers.get('x-app-secret') ?? '', SHARED_SECRET)) return json({ error: '앱 비밀키가 맞지 않습니다' }, 401);

  let body: { image?: unknown; mediaType?: unknown; ping?: unknown };
  try {
    body = await req.json();
  } catch {
    return json({ error: '요청 본문이 JSON 이 아닙니다' }, 400);
  }
  if (body.ping) return json({ ok: true });

  const image = typeof body.image === 'string' ? body.image.replace(/^data:image\/\w+;base64,/, '') : '';
  if (!image) return json({ error: 'image(base64) 가 필요합니다' }, 400);
  if (image.length > MAX_BASE64) return json({ error: '이미지가 너무 큽니다' }, 413);
  const mediaType = MEDIA_TYPES.includes(body.mediaType as ImageMediaType) ? (body.mediaType as ImageMediaType) : 'image/jpeg';

  try {
    const result = await extractCard(client, image, mediaType);
    if (!result.isBusinessCard) return json({ error: '명함이 아닌 사진으로 보입니다. 명함이 화면에 꽉 차게 다시 찍어 주세요.' }, 422);
    return json({ fields: result.fields, extra: result.extra, note: result.note });
  } catch (e) {
    if (e instanceof ExtractError) return json({ error: e.message }, e.status);
    if (e instanceof Anthropic.RateLimitError) return json({ error: '요청이 많습니다. 잠시 후 다시 시도하세요.' }, 429);
    if (e instanceof Anthropic.AuthenticationError) return json({ error: '서버의 ANTHROPIC_API_KEY 가 올바르지 않습니다' }, 500);
    if (e instanceof Anthropic.APIError) return json({ error: `인식 서비스 오류 (${e.status})` }, 502);
    console.error(e);
    return json({ error: '서버 오류' }, 500);
  }
});
