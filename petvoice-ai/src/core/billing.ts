/**
 * 인앱 결제 도메인 로직.
 *
 * 여기에는 react-native-iap 도, 네트워크도 없다. 스토어가 돌려준 값을 우리 도메인
 * 타입으로 옮기고 "지금 프로인가"를 판단하는 규칙만 있다. 그래서 전부 테스트로 고정된다.
 */
import type { Subscription, SubscriptionState, SubscriptionStore } from './types';

/** 스토어에 등록하는 상품 ID (Play 구독 ID / App Store 제품 ID 동일하게 맞춘다) */
export const PRO_MONTHLY_SKU = 'petvoice_pro_monthly';
export const SUBSCRIPTION_SKUS = [PRO_MONTHLY_SKU];

/** 서버 검증 결과가 이만큼 지나면 다시 맞춘다 */
export const RESYNC_INTERVAL_MS = 6 * 60 * 60 * 1000;
/** 만료가 이 시간 안으로 다가오면 주기와 무관하게 다시 맞춘다 */
export const RESYNC_NEAR_EXPIRY_MS = 24 * 60 * 60 * 1000;

/**
 * 스토어/서버가 알려 준 구독 상태를 앱이 쓰는 형태로 정규화한다.
 *
 * 기능을 열어 주는 기준:
 * - `active` : 정상 구독
 * - `grace`  : 결제 실패 후 유예 기간. 카드가 잠깐 막힌 사용자에게 곧바로 기능을 끊으면
 *              이탈로 이어지고, 스토어 정책도 유예 기간 제공을 권장한다.
 * - `canceled` : **해지 예약**일 뿐 남은 기간은 이미 결제된 것이다. 만료 시각 전까지는 열어 준다.
 *              (Play 의 SUBSCRIPTION_STATE_CANCELED 가 이 상태다 — 여기서 바로 끊으면 환불 분쟁이 된다)
 *
 * `on_hold` / `paused` / `expired` 는 잠근다.
 */
export function subscriptionFromEntitlement(entitlement: {
  state?: string | null;
  expiresAt?: number | null;
  autoRenewing?: boolean | null;
  store?: string | null;
  productId?: string | null;
}, now = Date.now()): Subscription {
  const state = normalizeState(entitlement.state);
  const expiresAt = toTimestamp(entitlement.expiresAt);
  const entitled =
    state === 'active' || state === 'grace'
      ? expiresAt == null || expiresAt > now
      : // 해지 예약은 만료 시각을 반드시 알아야 열어 준다
        state === 'canceled' && expiresAt != null && expiresAt > now;

  return {
    pro: entitled,
    ...(expiresAt != null ? { expiresAt } : {}),
    ...(entitlement.productId ? { productId: entitlement.productId } : {}),
    ...(entitlement.store ? { store: normalizeStore(entitlement.store) } : {}),
    autoRenewing: Boolean(entitlement.autoRenewing),
    state,
    verifiedAt: now,
  };
}

const KNOWN_STATES: SubscriptionState[] = [
  'active',
  'grace',
  'on_hold',
  'paused',
  'canceled',
  'expired',
  'pending',
  'none',
];

function normalizeState(raw: unknown): SubscriptionState {
  if (typeof raw !== 'string') return 'none';
  const value = raw.trim().toLowerCase().replace(/[\s-]+/g, '_');
  return (KNOWN_STATES as string[]).includes(value) ? (value as SubscriptionState) : 'none';
}

function normalizeStore(raw: unknown): SubscriptionStore {
  const value = typeof raw === 'string' ? raw.toLowerCase() : '';
  if (value === 'appstore' || value === 'ios' || value === 'apple') return 'appstore';
  if (value === 'dev') return 'dev';
  return 'play';
}

/** 서버가 초 단위나 문자열로 줘도 ms 로 맞춘다. */
function toTimestamp(raw: unknown): number | undefined {
  if (raw == null) return undefined;
  if (typeof raw === 'number') {
    if (!Number.isFinite(raw) || raw <= 0) return undefined;
    // 10자리면 초 단위로 본다 (2001년 ~ 2286년)
    return raw < 1e11 ? Math.round(raw * 1000) : Math.round(raw);
  }
  if (typeof raw === 'string') {
    const numeric = Number(raw);
    if (Number.isFinite(numeric) && numeric > 0) return toTimestamp(numeric);
    const parsed = Date.parse(raw);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

/**
 * 서버와 다시 맞춰야 하는지.
 * 앱을 열 때마다 검증을 때리면 낭비고, 아예 안 맞추면 해지·환불이 반영되지 않는다.
 */
export function shouldResync(sub: Subscription | undefined, now = Date.now()): boolean {
  if (!sub) return false;
  // 무료 사용자인데 결제 이력도 없으면 굳이 물어볼 게 없다
  if (!sub.pro && !sub.verifiedAt && !sub.productId) return false;
  if (!sub.verifiedAt) return true;
  if (now - sub.verifiedAt >= RESYNC_INTERVAL_MS) return true;
  if (sub.expiresAt != null && sub.expiresAt - now <= RESYNC_NEAR_EXPIRY_MS) return true;
  return false;
}

/** 설정 화면에 그대로 뿌리는 구독 상태 설명 */
export function describeSubscription(sub: Subscription | undefined, now = Date.now()): string {
  if (!sub?.pro) return '무료 플랜';

  const until = sub.expiresAt ? formatDate(sub.expiresAt) : null;
  if (sub.state === 'grace') {
    return `결제 확인이 필요해요${until ? ` · ${until}까지 이용 가능` : ''}`;
  }
  if (sub.autoRenewing === false) {
    return until ? `해지 예약됨 · ${until}까지 이용 가능` : '해지 예약됨';
  }
  if (until) return `프로 이용 중 · ${until} 자동 갱신`;
  return '프로 이용 중';
}

function formatDate(ts: number): string {
  const d = new Date(ts);
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
}

/* ---------- 스토어 상품/구매 정규화 ---------- */

/** Play 의 구독 오퍼 한 건 (react-native-iap `SubscriptionAndroid.subscriptionOfferDetails`) */
export interface AndroidOffer {
  offerToken: string;
  basePlanId?: string;
  offerId?: string | null;
  pricingPhases?: {
    pricingPhaseList?: { priceAmountMicros?: string; billingPeriod?: string; formattedPrice?: string }[];
  };
}

/**
 * 구매에 쓸 오퍼를 고른다.
 * 무료 체험/할인 오퍼(첫 구간 가격 0)가 있으면 그쪽을 먼저 준다 — 전환율이 눈에 띄게 다르다.
 */
export function pickAndroidOffer(offers: AndroidOffer[] | undefined): AndroidOffer | null {
  if (!offers || offers.length === 0) return null;
  const introductory = offers.find((offer) => {
    const first = offer.pricingPhases?.pricingPhaseList?.[0];
    return first?.priceAmountMicros === '0';
  });
  return introductory ?? offers[0];
}

/** 오퍼가 무료 체험을 포함하면 체험 기간 문자열을 돌려준다. (`P1W` → `7일`) */
export function freeTrialLabel(offer: AndroidOffer | null): string | null {
  const first = offer?.pricingPhases?.pricingPhaseList?.[0];
  if (!first || first.priceAmountMicros !== '0' || !first.billingPeriod) return null;
  return isoPeriodToKo(first.billingPeriod);
}

/** ISO-8601 기간(`P1W`, `P3D`, `P1M`)을 한국어로 */
export function isoPeriodToKo(period: string): string | null {
  const match = /^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?$/.exec(period.trim().toUpperCase());
  if (!match) return null;
  const [, y, m, w, d] = match;
  if (y) return `${Number(y)}년`;
  if (m) return `${Number(m)}개월`;
  if (w) return `${Number(w) * 7}일`;
  if (d) return `${Number(d)}일`;
  return null;
}

/** 결제 라이브러리가 준 구매 객체를 서버 검증에 필요한 최소 정보로 줄인다. */
export interface NormalizedPurchase {
  productId: string;
  /** Play: purchaseToken · App Store: 영수증 또는 트랜잭션 ID */
  token: string;
  store: SubscriptionStore;
  transactionId?: string;
  /** Play 에서 아직 승인(acknowledge)되지 않은 구매인지 */
  needsAcknowledge: boolean;
  /** 결제 대기(느린 결제 수단) 상태인지 */
  pending: boolean;
}

export interface RawPurchase {
  productId?: string;
  transactionId?: string;
  transactionReceipt?: string;
  purchaseToken?: string;
  purchaseStateAndroid?: number;
  isAcknowledgedAndroid?: boolean;
  originalTransactionIdentifierIOS?: string;
}

/** Play 의 PurchaseState — 1 이 구매 완료, 2 가 결제 대기 */
const ANDROID_PURCHASED = 1;
const ANDROID_PENDING = 2;

export function normalizePurchase(
  purchase: RawPurchase | null | undefined,
  platform: 'android' | 'ios',
): NormalizedPurchase | null {
  if (!purchase?.productId) return null;

  if (platform === 'android') {
    const token = purchase.purchaseToken;
    if (!token) return null;
    const pending = purchase.purchaseStateAndroid === ANDROID_PENDING;
    return {
      productId: purchase.productId,
      token,
      store: 'play',
      ...(purchase.transactionId ? { transactionId: purchase.transactionId } : {}),
      // 결제 대기 중이면 아직 승인할 게 없다
      needsAcknowledge:
        !pending &&
        purchase.isAcknowledgedAndroid !== true &&
        (purchase.purchaseStateAndroid == null || purchase.purchaseStateAndroid === ANDROID_PURCHASED),
      pending,
    };
  }

  // iOS 는 영수증(StoreKit1) 또는 JWS(StoreKit2)를 그대로 서버로 보낸다
  const token = purchase.transactionReceipt || purchase.purchaseToken;
  if (!token) return null;
  return {
    productId: purchase.productId,
    token,
    store: 'appstore',
    ...(purchase.originalTransactionIdentifierIOS || purchase.transactionId
      ? { transactionId: purchase.originalTransactionIdentifierIOS ?? purchase.transactionId }
      : {}),
    needsAcknowledge: true, // StoreKit 은 finishTransaction 을 항상 호출해야 한다
    pending: false,
  };
}

/** 여러 복원 구매 중 가장 최근/유효한 것을 고른다. */
export function pickLatestPurchase(
  purchases: RawPurchase[],
  platform: 'android' | 'ios',
): NormalizedPurchase | null {
  const candidates = purchases
    .filter((p) => SUBSCRIPTION_SKUS.includes(p.productId ?? ''))
    .map((p) => normalizePurchase(p, platform))
    .filter((p): p is NormalizedPurchase => p !== null);

  if (candidates.length === 0) return null;
  // 결제 대기 건보다 완료 건을 먼저
  return candidates.find((c) => !c.pending) ?? candidates[0];
}
