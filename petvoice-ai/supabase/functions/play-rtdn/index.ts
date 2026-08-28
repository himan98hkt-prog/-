// supabase/functions/play-rtdn/index.ts
//
// Google Play 실시간 개발자 알림(RTDN) 수신용 Pub/Sub push 엔드포인트.
//
// 앱이 켜져 있을 때만 갱신 상태를 맞추면 해지·환불·결제 실패가 며칠씩 늦게 반영된다.
// RTDN 을 받으면 그 자리에서 스토어에 다시 물어 DB 를 갱신한다.
//
// 설정:
//   1) Play Console ▸ 수익 창출 설정 ▸ 실시간 개발자 알림에 Pub/Sub 주제 등록
//   2) 그 주제에 push 구독 생성 → 엔드포인트:
//      https://<project>.functions.supabase.co/play-rtdn?secret=<RTDN_SECRET>
//   3) supabase secrets set RTDN_SECRET=<충분히 긴 임의 문자열>
//   4) 이 함수는 사용자 토큰이 아니라 위 secret 으로 인증하므로 JWT 검증을 꺼야 한다:
//      supabase functions deploy play-rtdn --no-verify-jwt

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { entitlementFromPlay, parseRtdnMessage } from '../_shared/entitlement.ts';
import { getGoogleAccessToken } from '../_shared/googleAuth.ts';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const ANDROID_PACKAGE_NAME = Deno.env.get('ANDROID_PACKAGE_NAME') ?? 'app.petvoice.ai';
const RTDN_SECRET = Deno.env.get('RTDN_SECRET') ?? '';

/** 길이가 달라도 같은 시간이 걸리게 비교한다 (타이밍 공격 방지) */
function safeEqual(a: string, b: string): boolean {
  const encoder = new TextEncoder();
  const left = encoder.encode(a);
  const right = encoder.encode(b);
  let diff = left.length ^ right.length;
  const max = Math.max(left.length, right.length);
  for (let i = 0; i < max; i += 1) {
    diff |= (left[i] ?? 0) ^ (right[i] ?? 0);
  }
  return diff === 0;
}

Deno.serve(async (req) => {
  if (req.method !== 'POST') return new Response('method_not_allowed', { status: 405 });

  const secret = new URL(req.url).searchParams.get('secret') ?? '';
  if (!RTDN_SECRET || !safeEqual(secret, RTDN_SECRET)) {
    return new Response('unauthorized', { status: 401 });
  }

  // Pub/Sub push 는 { message: { data: base64 } } 형태로 온다.
  let envelope: { message?: { data?: string; messageId?: string } };
  try {
    envelope = await req.json();
  } catch {
    // 형식이 깨진 메시지를 4xx 로 돌려주면 Pub/Sub 가 끝없이 재시도한다. 삼키고 200.
    return new Response('ok', { status: 200 });
  }

  const encoded = envelope.message?.data;
  if (!encoded) return new Response('ok', { status: 200 });

  const notification = parseRtdnMessage(atob(encoded));
  if (!notification) return new Response('ok', { status: 200 });

  const admin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
  const { data: row } = await admin
    .from('subscriptions')
    .select('user_id')
    .eq('purchase_token', notification.purchaseToken)
    .maybeSingle();

  if (!row) {
    // 아직 앱이 검증을 올리기 전에 알림이 먼저 도착할 수 있다. 앱이 곧 올린다.
    console.log('rtdn: unknown token', notification.notificationName);
    return new Response('ok', { status: 200 });
  }

  try {
    const accessToken = await getGoogleAccessToken();
    const url =
      `https://androidpublisher.googleapis.com/androidpublisher/v3/applications/` +
      `${encodeURIComponent(ANDROID_PACKAGE_NAME)}/purchases/subscriptionsv2/tokens/` +
      `${encodeURIComponent(notification.purchaseToken)}`;
    const response = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });

    const entitlement =
      response.status === 404 || response.status === 410
        ? { state: 'expired' as const, expiresAt: null, autoRenewing: false, productId: null }
        : entitlementFromPlay(await response.json());

    await admin
      .from('subscriptions')
      .update({
        pro: entitlement.state === 'active' || entitlement.state === 'grace' || entitlement.state === 'canceled',
        state: entitlement.state,
        expires_at: entitlement.expiresAt ? new Date(entitlement.expiresAt).toISOString() : null,
        auto_renewing: entitlement.autoRenewing,
        updated_at: new Date().toISOString(),
      })
      .eq('user_id', row.user_id);

    console.log('rtdn applied', notification.notificationName, entitlement.state);
  } catch (error) {
    // 여기서 5xx 를 주면 Pub/Sub 가 재시도한다 — 일시적 오류라면 그게 맞다.
    console.error('rtdn failed', String(error));
    return new Response('retry', { status: 500 });
  }

  return new Response('ok', { status: 200 });
});
