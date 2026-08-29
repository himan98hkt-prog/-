/**
 * 스토어 검증 응답 → 우리 구독 상태 매핑.
 *
 * Deno(Edge Function)와 vitest 양쪽에서 그대로 import 한다. 그래서 이 파일에는
 * Deno API 도 네트워크도 없다 — 순수 변환만.
 */

export type EntitlementState =
  'active' | 'grace' | 'on_hold' | 'paused' | 'canceled' | 'expired' | 'pending' | 'none';

export interface Entitlement {
  state: EntitlementState;
  /** 만료(다음 결제) 시각 ms. 모르면 null */
  expiresAt: number | null;
  autoRenewing: boolean;
  productId: string | null;
  store: 'play' | 'appstore';
  /** Play 에서 아직 acknowledge 되지 않은 구매인지 — 3일 안에 승인하지 않으면 자동 환불된다 */
  needsAcknowledge?: boolean;
  /** 스토어 테스트 계정의 구매인지 (분석에서 제외하려고 표시) */
  testPurchase?: boolean;
}

/* ---------------- Google Play ---------------- */

/** purchases.subscriptionsv2.get 응답 중 우리가 쓰는 필드 */
export interface PlaySubscriptionV2 {
  subscriptionState?: string;
  acknowledgementState?: string;
  latestOrderId?: string;
  testPurchase?: unknown;
  lineItems?: {
    productId?: string;
    expiryTime?: string;
    autoRenewingPlan?: { autoRenewEnabled?: boolean };
  }[];
}

const PLAY_STATE_MAP: Record<string, EntitlementState> = {
  SUBSCRIPTION_STATE_ACTIVE: 'active',
  SUBSCRIPTION_STATE_IN_GRACE_PERIOD: 'grace',
  SUBSCRIPTION_STATE_ON_HOLD: 'on_hold',
  SUBSCRIPTION_STATE_PAUSED: 'paused',
  SUBSCRIPTION_STATE_CANCELED: 'canceled',
  SUBSCRIPTION_STATE_EXPIRED: 'expired',
  SUBSCRIPTION_STATE_PENDING: 'pending',
  SUBSCRIPTION_STATE_UNSPECIFIED: 'none',
};

function parseTime(raw: unknown): number | null {
  if (typeof raw !== 'string' || !raw) return null;
  const ms = Date.parse(raw);
  return Number.isFinite(ms) ? ms : null;
}

/**
 * Play 응답을 Entitlement 로.
 *
 * 만료 시각은 lineItems 중 **가장 늦은** expiryTime 을 쓴다. 요금제 변경 직후에는
 * 이전 항목과 새 항목이 함께 들어오는데, 이른 쪽을 잡으면 멀쩡한 구독이 만료로 보인다.
 */
export function entitlementFromPlay(response: PlaySubscriptionV2): Entitlement {
  const items = Array.isArray(response.lineItems) ? response.lineItems : [];
  let expiresAt: number | null = null;
  let productId: string | null = null;
  let autoRenewing = false;

  for (const item of items) {
    const time = parseTime(item.expiryTime);
    if (time != null && (expiresAt == null || time > expiresAt)) {
      expiresAt = time;
      productId = item.productId ?? productId;
      autoRenewing = Boolean(item.autoRenewingPlan?.autoRenewEnabled);
    }
    if (productId == null && item.productId) productId = item.productId;
  }

  return {
    state: PLAY_STATE_MAP[response.subscriptionState ?? ''] ?? 'none',
    expiresAt,
    autoRenewing,
    productId,
    store: 'play',
    needsAcknowledge: response.acknowledgementState === 'ACKNOWLEDGEMENT_STATE_PENDING',
    testPurchase: response.testPurchase != null,
  };
}

/* ---------------- Apple App Store ---------------- */

/** verifyReceipt 응답 중 우리가 쓰는 필드 */
export interface AppleVerifyReceipt {
  status?: number;
  latest_receipt_info?: {
    product_id?: string;
    expires_date_ms?: string;
    purchase_date_ms?: string;
    original_transaction_id?: string;
  }[];
  pending_renewal_info?: {
    auto_renew_status?: string;
    expiration_intent?: string;
    is_in_billing_retry_period?: string;
    grace_period_expires_date_ms?: string;
  }[];
}

function parseMs(raw: unknown): number | null {
  if (typeof raw !== 'string' || !raw) return null;
  const ms = Number(raw);
  return Number.isFinite(ms) && ms > 0 ? ms : null;
}

/**
 * Apple 영수증을 Entitlement 로.
 *
 * Apple 은 상태를 직접 주지 않아서 만료 시각 + 갱신 정보로 우리가 판정해야 한다.
 * - 아직 만료 전 + 자동갱신 켜짐 → active
 * - 아직 만료 전 + 자동갱신 꺼짐 → canceled (남은 기간은 이용 가능)
 * - 만료됐지만 결제 재시도 중이고 유예 기간이 남음 → grace
 * - 만료됐고 결제 재시도 중 → on_hold
 */
export function entitlementFromApple(response: AppleVerifyReceipt, now = Date.now()): Entitlement {
  const infos = Array.isArray(response.latest_receipt_info) ? response.latest_receipt_info : [];
  const latest = infos.reduce<{ ms: number; item: (typeof infos)[number] } | null>((best, item) => {
    const ms = parseMs(item.expires_date_ms);
    if (ms == null) return best;
    return best == null || ms > best.ms ? { ms, item } : best;
  }, null);

  const renewal = response.pending_renewal_info?.[0];
  const autoRenewing = renewal?.auto_renew_status === '1';
  const retrying = renewal?.is_in_billing_retry_period === '1';
  const graceUntil = parseMs(renewal?.grace_period_expires_date_ms);

  if (!latest) {
    return { state: 'none', expiresAt: null, autoRenewing, productId: null, store: 'appstore' };
  }

  const expiresAt = latest.ms;
  const productId = latest.item.product_id ?? null;

  let state: EntitlementState;
  if (expiresAt > now) {
    state = autoRenewing ? 'active' : 'canceled';
  } else if (graceUntil != null && graceUntil > now) {
    state = 'grace';
  } else if (retrying) {
    state = 'on_hold';
  } else {
    state = 'expired';
  }

  return {
    state,
    // 유예 기간에는 그 종료 시각까지 이용 가능하다
    expiresAt: state === 'grace' && graceUntil != null ? graceUntil : expiresAt,
    autoRenewing,
    productId,
    store: 'appstore',
  };
}

/* ---------------- Play 실시간 개발자 알림(RTDN) ---------------- */

/** RTDN notificationType — 재검증이 필요한 것만 추린다 */
export const RTDN_TYPES: Record<number, string> = {
  1: 'RECOVERED',
  2: 'RENEWED',
  3: 'CANCELED',
  4: 'PURCHASED',
  5: 'ON_HOLD',
  6: 'IN_GRACE_PERIOD',
  7: 'RESTARTED',
  8: 'PRICE_CHANGE_CONFIRMED',
  9: 'DEFERRED',
  10: 'PAUSED',
  11: 'PAUSE_SCHEDULE_CHANGED',
  12: 'REVOKED',
  13: 'EXPIRED',
  20: 'PENDING_PURCHASE_CANCELED',
};

export interface RtdnPayload {
  purchaseToken: string;
  subscriptionId: string | null;
  notificationType: number;
  notificationName: string;
}

/**
 * Pub/Sub push 메시지(base64 data)에서 구독 알림을 꺼낸다.
 * 구독 알림이 아니면(테스트 알림, 일회성 상품 알림) null.
 */
export function parseRtdnMessage(decodedJson: string): RtdnPayload | null {
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(decodedJson);
  } catch {
    return null;
  }

  const sub = parsed.subscriptionNotification as
    { purchaseToken?: string; subscriptionId?: string; notificationType?: number } | undefined;
  if (!sub?.purchaseToken || typeof sub.notificationType !== 'number') return null;

  return {
    purchaseToken: sub.purchaseToken,
    subscriptionId: sub.subscriptionId ?? null,
    notificationType: sub.notificationType,
    notificationName: RTDN_TYPES[sub.notificationType] ?? `UNKNOWN_${sub.notificationType}`,
  };
}
