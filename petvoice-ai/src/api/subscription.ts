import { subscriptionFromEntitlement } from '../core/billing';
import type { NormalizedPurchase } from '../core/billing';
import type { Subscription } from '../core/types';
import { isConfigured } from './config';
import { ApiError, codeFromStatus } from './errors';
import { supabase } from './supabase';

/**
 * 구독 상태의 출처는 언제나 서버다.
 * 앱은 서버가 검증해 준 결과를 받아 보여 주기만 한다.
 */

/** 서버에 저장된 구독 상태를 읽어 온다. 행이 없으면 무료 사용자. */
export async function fetchServerSubscription(): Promise<Subscription | null> {
  const sb = supabase();
  if (!sb) return null;

  const { data, error } = await sb
    .from('subscriptions')
    .select('state, expires_at, auto_renewing, store, product_id')
    .maybeSingle();

  if (error) return null;
  if (!data) return subscriptionFromEntitlement({ state: 'none' });

  return subscriptionFromEntitlement({
    state: data.state,
    expiresAt: data.expires_at,
    autoRenewing: data.auto_renewing,
    store: data.store,
    productId: data.product_id,
  });
}

/**
 * 영수증을 서버로 보내 검증받는다.
 * 성공하면 서버가 판정한 구독 상태가 돌아온다 — 앱이 스스로 프로로 바꾸는 경로는 없다.
 */
export async function verifyPurchase(purchase: NormalizedPurchase): Promise<Subscription> {
  const sb = supabase();
  if (!sb || !isConfigured) {
    throw new ApiError('server', '결제 검증 서버가 설정되지 않았습니다.');
  }

  const { data, error } = await sb.functions.invoke('verify-purchase', {
    body: { store: purchase.store, productId: purchase.productId, token: purchase.token },
  });

  if (error) {
    const status = (error as { context?: { status?: number } }).context?.status;
    throw new ApiError(
      status ? codeFromStatus(status) : 'server',
      error.message ?? '검증에 실패했습니다.',
      status,
    );
  }

  return subscriptionFromEntitlement(data as Record<string, unknown>);
}
