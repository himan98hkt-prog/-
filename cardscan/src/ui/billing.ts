// 구글 플레이 결제 (Pro 평생 이용권) — expo-iap.
// 결제는 플레이스토어 빌드(EXPO_PUBLIC_STORE=play)에서만 켠다. 직접 설치하는 개인용 APK 는 플레이 결제를 쓸 수 없어 모든 기능을 연다.
import {
  fetchProducts,
  finishTransaction,
  getAvailablePurchases,
  initConnection,
  isUserCancelledError,
  Product,
  Purchase,
  purchaseErrorListener,
  purchaseUpdatedListener,
  requestPurchase,
} from 'expo-iap';
import { PRO_SKU } from '../core/pro';

export const BILLING_ENABLED = process.env.EXPO_PUBLIC_STORE === 'play';

export interface ProProduct {
  displayPrice: string;
  price: number | null;
  currency: string;
}

export type OwnedState = 'owned' | 'pending' | 'none';

let connected: Promise<boolean> | null = null;
function connect(): Promise<boolean> {
  if (!connected) connected = initConnection().then(Boolean).catch(() => ((connected = null), false));
  return connected;
}

function isPro(p: Purchase) {
  return p.productId === PRO_SKU;
}

/** 결제 완료를 구글에 확인(acknowledge) — 3일 안에 안 하면 자동 환불된다 */
async function acknowledge(p: Purchase) {
  if ((p as { isAcknowledgedAndroid?: boolean | null }).isAcknowledgedAndroid) return;
  try {
    await finishTransaction({ purchase: p, isConsumable: false });
  } catch {
    // 다음 실행 때 getAvailablePurchases 에서 다시 시도된다
  }
}

/** 이미 산 적이 있는지 (구매 복원 겸용). 조회 자체가 실패하면 null — 저장해 둔 상태를 그대로 쓴다 */
export async function checkOwned(): Promise<OwnedState | null> {
  if (!(await connect())) return null;
  try {
    const purchases = (await getAvailablePurchases()) ?? [];
    const mine = purchases.filter(isPro);
    const done = mine.find((p) => p.purchaseState === 'purchased');
    if (done) {
      await acknowledge(done);
      return 'owned';
    }
    return mine.some((p) => p.purchaseState === 'pending') ? 'pending' : 'none';
  } catch {
    return null;
  }
}

export async function loadProduct(): Promise<ProProduct | null> {
  if (!(await connect())) return null;
  try {
    const products = ((await fetchProducts({ skus: [PRO_SKU], type: 'in-app' })) ?? []) as Product[];
    const p = products.find((x) => x.id === PRO_SKU);
    return p ? { displayPrice: p.displayPrice, price: p.price ?? null, currency: p.currency } : null;
  } catch {
    return null;
  }
}

/** 결제 창 열기 — 결과는 watchPurchases 로 온다 */
export async function buyPro(): Promise<void> {
  if (!(await connect())) throw new Error('구글 플레이에 연결하지 못했습니다. 인터넷 연결과 플레이스토어 로그인을 확인해 주세요.');
  await requestPurchase({ request: { google: { skus: [PRO_SKU] } }, type: 'in-app' });
}

/** 결제 결과 받기 (앱이 꺼져 있던 사이 끝난 결제도 여기로 온다) */
export function watchPurchases(onState: (s: OwnedState) => void, onError: (message: string) => void): () => void {
  const a = purchaseUpdatedListener(async (p) => {
    if (!isPro(p)) return;
    if (p.purchaseState === 'purchased') {
      await acknowledge(p);
      onState('owned');
    } else if (p.purchaseState === 'pending') {
      onState('pending');
    }
  });
  const b = purchaseErrorListener((e) => {
    if (isUserCancelledError(e as never)) return;
    onError(e.message || '결제를 완료하지 못했습니다');
  });
  return () => {
    a.remove();
    b.remove();
  };
}
