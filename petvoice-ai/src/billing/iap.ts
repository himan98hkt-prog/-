import { NativeModules, Platform } from 'react-native';
import {
  SUBSCRIPTION_SKUS,
  freeTrialPeriod,
  periodOfSku,
  pickAndroidOffer,
  type AndroidOffer,
  type BillingPeriod,
  type RawPurchase,
  type TrialPeriod,
} from '../core/billing';

/**
 * react-native-iap 얇은 래퍼.
 *
 * 결제는 **네이티브 모듈**이라 Expo Go·웹·시뮬레이터 일부에서는 아예 존재하지 않는다.
 * 그때마다 앱이 죽으면 개발이 불가능하므로, 모듈이 없으면 `available === false` 로
 * 조용히 물러나고 나머지 기능은 그대로 돌게 한다.
 *
 * (실제 결제를 테스트하려면 EAS 개발 빌드 + Play Console 내부 테스트 트랙이 필요하다.)
 */

type IapModule = typeof import('react-native-iap');

let moduleCache: IapModule | null | undefined;

/**
 * JS 모듈이 존재하는 것과 **네이티브 모듈이 붙어 있는 것**은 다르다.
 * 웹/Expo Go 에서는 `require` 는 멀쩡히 성공하고 `initConnection` 도 함수로 보이지만,
 * 실제로 부르는 순간 `E_IAP_NOT_AVAILABLE` 이 터진다. 그래서 네이티브 모듈을 직접 확인한다.
 */
function hasNativeModule(): boolean {
  if (Platform.OS !== 'android' && Platform.OS !== 'ios') return false;
  const modules = NativeModules as Record<string, unknown>;
  return Boolean(
    modules.RNIapModule || modules.RNIapAmazonModule || modules.RNIapIos || modules.RNIapIosSk2,
  );
}

function iap(): IapModule | null {
  if (moduleCache !== undefined) return moduleCache;
  if (!hasNativeModule()) {
    moduleCache = null;
    return null;
  }
  try {
    // 정적 import 를 쓰면 네이티브 모듈이 없는 환경에서 번들 평가 단계부터 터질 수 있다.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require('react-native-iap') as Partial<IapModule> | undefined;
    moduleCache = typeof mod?.initConnection === 'function' ? (mod as IapModule) : null;
  } catch {
    moduleCache = null;
  }
  return moduleCache;
}

export function isBillingAvailable(): boolean {
  return iap() !== null;
}

/** 화면에 뿌리는 상품 정보 */
export interface StoreProduct {
  productId: string;
  title: string;
  /** 스토어가 준 현지 통화 표기 ("₩3,900") */
  localizedPrice: string;
  /** 절약률 계산에 쓰는 원가 (마이크로 단위). 모르면 0 */
  priceMicros: number;
  period: BillingPeriod;
  /** Play 구독 구매에 반드시 필요한 오퍼 토큰 */
  offerToken?: string;
  /** 무료 체험 기간. 없으면 null */
  freeTrial: TrialPeriod | null;
}

let connected = false;

export async function connect(): Promise<boolean> {
  const mod = iap();
  if (!mod) return false;
  if (connected) return true;
  try {
    await mod.initConnection();
    if (Platform.OS === 'android') {
      // 앱이 죽어서 마무리하지 못한 구매가 남아 있으면 여기서 정리된다.
      await mod.flushFailedPurchasesCachedAsPendingAndroid().catch(() => undefined);
    }
    connected = true;
    return true;
  } catch {
    return false;
  }
}

export async function disconnect(): Promise<void> {
  const mod = iap();
  if (!mod || !connected) return;
  connected = false;
  await mod.endConnection().catch(() => undefined);
}

/** 스토어에서 구독 상품과 가격을 읽어 온다. */
export async function fetchProducts(): Promise<StoreProduct[]> {
  const mod = iap();
  if (!mod || !(await connect())) return [];

  try {
    const raw = await mod.getSubscriptions({ skus: SUBSCRIPTION_SKUS });
    return raw
      .map((item) => {
        const androidOffers = (item as { subscriptionOfferDetails?: AndroidOffer[] }).subscriptionOfferDetails;
        const offer = pickAndroidOffer(androidOffers);
        const lastPhase = offer?.pricingPhases?.pricingPhaseList?.at(-1);
        const iosPrice = (item as { price?: string }).price;

        return {
          productId: item.productId,
          title: (item as { title?: string }).title ?? '',
          localizedPrice:
            (item as { localizedPrice?: string }).localizedPrice ?? lastPhase?.formattedPrice ?? '',
          priceMicros: Number(lastPhase?.priceAmountMicros ?? (iosPrice ? Number(iosPrice) * 1_000_000 : 0)) || 0,
          period: periodOfSku(item.productId),
          ...(offer ? { offerToken: offer.offerToken } : {}),
          freeTrial: freeTrialPeriod(offer),
        };
      })
      // 월간 → 연간 순서로 고정해 화면이 스토어 응답 순서에 흔들리지 않게
      .sort((a, b) => (a.period === b.period ? 0 : a.period === 'month' ? -1 : 1));
  } catch {
    return [];
  }
}

/**
 * 구독 구매 요청.
 * 실제 결과는 `purchaseUpdatedListener` 로 들어온다 — 여기서 기다리지 않는다.
 * (스토어 시트를 닫았다가 다시 여는 경우, 느린 결제 수단 등 경로가 여럿이라
 *  리스너 하나로 모으는 편이 훨씬 안전하다.)
 */
export async function requestProSubscription(sku: string, offerToken?: string): Promise<void> {
  const mod = iap();
  if (!mod || !(await connect())) throw new Error('billing_unavailable');

  if (Platform.OS === 'android') {
    if (!offerToken) throw new Error('missing_offer_token');
    await mod.requestSubscription({ subscriptionOffers: [{ sku, offerToken }] });
    return;
  }
  await mod.requestSubscription({ sku });
}

/** 기기를 바꾼 사용자를 위한 구매 복원 */
export async function fetchAvailablePurchases(): Promise<RawPurchase[]> {
  const mod = iap();
  if (!mod || !(await connect())) return [];
  try {
    return (await mod.getAvailablePurchases()) as RawPurchase[];
  } catch {
    return [];
  }
}

/**
 * 구매 마무리. 서버 검증이 끝난 **뒤에만** 부른다.
 * 검증 전에 마무리하면 영수증을 잃어버리고, 안 하면 Play 가 3일 뒤 자동 환불한다.
 */
export async function finishPurchase(purchase: unknown): Promise<void> {
  const mod = iap();
  if (!mod) return;
  try {
    await mod.finishTransaction({ purchase: purchase as never, isConsumable: false });
  } catch {
    // 이미 마무리된 구매 — 무시해도 된다
  }
}

export interface PurchaseListeners {
  onPurchase: (purchase: RawPurchase) => void;
  onError: (error: { code?: string; message?: string }) => void;
}

/** 구매 이벤트 구독. 해제 함수를 돌려준다. */
export function addPurchaseListeners({ onPurchase, onError }: PurchaseListeners): () => void {
  const mod = iap();
  if (!mod) return () => undefined;

  try {
    const purchaseSub = mod.purchaseUpdatedListener((purchase) => onPurchase(purchase as RawPurchase));
    const errorSub = mod.purchaseErrorListener((error) => onError(error));
    return () => {
      purchaseSub.remove();
      errorSub.remove();
    };
  } catch {
    // 네이티브 모듈 확인을 통과했는데도 실패하는 예외적인 기기가 있다. 앱을 죽이진 않는다.
    return () => undefined;
  }
}

/** 스토어의 구독 관리 화면으로 보낸다 (해지·결제수단 변경은 스토어에서만 가능) */
export async function openManageSubscriptions(sku = SUBSCRIPTION_SKUS[0]): Promise<void> {
  const mod = iap();
  if (!mod) return;
  await mod.deepLinkToSubscriptions({ sku }).catch(() => undefined);
}

/** 결제 오류 → 번역 키. 사용자가 직접 닫은 경우는 null (조용히 지나간다). */
export function billingErrorKey(error: { code?: string; message?: string }): string | null {
  switch (error.code) {
    case 'E_USER_CANCELLED':
      return null;
    case 'E_ALREADY_OWNED':
      return 'billing.error.alreadyOwned';
    case 'E_ITEM_UNAVAILABLE':
      return 'billing.error.itemUnavailable';
    case 'E_NETWORK_ERROR':
    case 'E_SERVICE_ERROR':
      return 'billing.error.network';
    case 'E_DEFERRED_PAYMENT':
      return 'billing.error.deferred';
    default:
      return 'billing.error.generic';
  }
}
