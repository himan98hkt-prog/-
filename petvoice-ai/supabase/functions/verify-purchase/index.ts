// supabase/functions/verify-purchase/index.ts
//
// 인앱 결제 영수증 검증. **앱이 보내온 "프로예요"를 절대 믿지 않는다.**
// 스토어에 직접 물어보고, 그 결과만 DB 에 쓴다.
//
//   [앱] --Bearer 토큰 + purchaseToken--> [이 함수] --서비스 계정--> [Google Play / App Store]
//                                              |
//                                              └─> subscriptions 테이블 (권한의 유일한 출처)
//
// 배포:
//   supabase secrets set GOOGLE_SERVICE_ACCOUNT_JSON='{"client_email":...,"private_key":...}'
//   supabase secrets set ANDROID_PACKAGE_NAME=app.petvoice.ai
//   supabase secrets set APPLE_SHARED_SECRET=...            # App Store 구독용
//   supabase functions deploy verify-purchase

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { CORS, json } from '../_shared/cors.ts';
import {
  entitlementFromApple,
  entitlementFromPlay,
  type Entitlement,
} from '../_shared/entitlement.ts';
import { getGoogleAccessToken } from '../_shared/googleAuth.ts';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SUPABASE_ANON_KEY = Deno.env.get('SUPABASE_ANON_KEY')!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const ANDROID_PACKAGE_NAME = Deno.env.get('ANDROID_PACKAGE_NAME') ?? 'app.petvoice.ai';
const APPLE_SHARED_SECRET = Deno.env.get('APPLE_SHARED_SECRET') ?? '';

/** 스토어에 등록한 상품만 받는다. 임의의 상품 ID 를 밀어 넣지 못하게. */
const ALLOWED_PRODUCTS = new Set(['petvoice_pro_monthly']);

const APPLE_PROD = 'https://buy.itunes.apple.com/verifyReceipt';
const APPLE_SANDBOX = 'https://sandbox.itunes.apple.com/verifyReceipt';

/** Play 구독 조회 */
async function fetchPlayEntitlement(purchaseToken: string): Promise<Entitlement> {
  const accessToken = await getGoogleAccessToken();
  const url =
    `https://androidpublisher.googleapis.com/androidpublisher/v3/applications/` +
    `${encodeURIComponent(ANDROID_PACKAGE_NAME)}/purchases/subscriptionsv2/tokens/${encodeURIComponent(purchaseToken)}`;

  const response = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
  if (response.status === 404 || response.status === 410) {
    // 존재하지 않거나 이미 만료·취소된 토큰
    return { state: 'expired', expiresAt: null, autoRenewing: false, productId: null, store: 'play' };
  }
  if (!response.ok) {
    throw new Error(`play_verify_failed:${response.status}`);
  }
  return entitlementFromPlay(await response.json());
}

/**
 * Play 구매 승인(acknowledge).
 * 3일 안에 승인하지 않으면 Google 이 자동 환불한다 — 검증에 성공한 그 자리에서 처리한다.
 */
async function acknowledgePlay(subscriptionId: string, purchaseToken: string): Promise<void> {
  const accessToken = await getGoogleAccessToken();
  const url =
    `https://androidpublisher.googleapis.com/androidpublisher/v3/applications/` +
    `${encodeURIComponent(ANDROID_PACKAGE_NAME)}/purchases/subscriptions/` +
    `${encodeURIComponent(subscriptionId)}/tokens/${encodeURIComponent(purchaseToken)}:acknowledge`;

  const response = await fetch(url, {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
    body: '{}',
  });
  // 이미 승인된 구매는 400 을 준다 — 실패로 볼 일이 아니다
  if (!response.ok && response.status !== 400) {
    console.error('acknowledge failed', response.status, await response.text().catch(() => ''));
  }
}

/** Apple 영수증 검증. 프로덕션에 먼저 묻고 21007 이면 샌드박스로 재시도한다. */
async function fetchAppleEntitlement(receipt: string): Promise<Entitlement> {
  const body = JSON.stringify({
    'receipt-data': receipt,
    password: APPLE_SHARED_SECRET,
    'exclude-old-transactions': true,
  });

  const ask = async (endpoint: string) => {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });
    if (!response.ok) throw new Error(`apple_verify_failed:${response.status}`);
    return response.json();
  };

  let payload = await ask(APPLE_PROD);
  if (payload?.status === 21007) payload = await ask(APPLE_SANDBOX);
  if (payload?.status !== 0) {
    throw new Error(`apple_verify_status:${payload?.status}`);
  }
  return entitlementFromApple(payload);
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS });
  if (req.method !== 'POST') return json({ error: 'method_not_allowed' }, 405);

  const authHeader = req.headers.get('Authorization');
  if (!authHeader?.startsWith('Bearer ')) return json({ error: 'unauthorized' }, 401);

  const userClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    global: { headers: { Authorization: authHeader } },
  });
  const { data: userData, error: userError } = await userClient.auth.getUser();
  if (userError || !userData.user) return json({ error: 'unauthorized' }, 401);
  const userId = userData.user.id;

  let payload: { store?: string; productId?: string; token?: string };
  try {
    payload = await req.json();
  } catch {
    return json({ error: 'invalid_json' }, 400);
  }

  const store = payload.store === 'appstore' ? 'appstore' : 'play';
  const productId = (payload.productId ?? '').trim();
  const token = (payload.token ?? '').trim();
  if (!token) return json({ error: 'missing_token' }, 400);
  if (!ALLOWED_PRODUCTS.has(productId)) return json({ error: 'unknown_product' }, 400);

  const admin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

  // 같은 영수증이 다른 계정에 이미 묶여 있으면 거절한다 (구독 공유 방지).
  const { data: existing } = await admin
    .from('subscriptions')
    .select('user_id')
    .eq('purchase_token', token)
    .maybeSingle();
  if (existing && existing.user_id !== userId) {
    return json({ error: 'token_bound_to_other_account' }, 409);
  }

  let entitlement: Entitlement;
  try {
    entitlement = store === 'play' ? await fetchPlayEntitlement(token) : await fetchAppleEntitlement(token);
  } catch (error) {
    console.error('verify failed', String(error));
    return json({ error: 'verify_failed' }, 502);
  }

  if (store === 'play' && entitlement.needsAcknowledge) {
    await acknowledgePlay(entitlement.productId ?? productId, token);
  }

  const { error: upsertError } = await admin.from('subscriptions').upsert(
    {
      user_id: userId,
      pro: entitlement.state === 'active' || entitlement.state === 'grace' || entitlement.state === 'canceled',
      state: entitlement.state,
      expires_at: entitlement.expiresAt ? new Date(entitlement.expiresAt).toISOString() : null,
      auto_renewing: entitlement.autoRenewing,
      store,
      product_id: entitlement.productId ?? productId,
      purchase_token: token,
      is_test: entitlement.testPurchase ?? false,
      updated_at: new Date().toISOString(),
    },
    { onConflict: 'user_id' },
  );
  if (upsertError) {
    console.error('upsert failed', upsertError.message);
    return json({ error: 'persist_failed' }, 500);
  }

  return json({
    state: entitlement.state,
    expiresAt: entitlement.expiresAt,
    autoRenewing: entitlement.autoRenewing,
    productId: entitlement.productId ?? productId,
    store,
  });
});
