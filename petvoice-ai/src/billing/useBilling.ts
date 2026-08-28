import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';
import { isConfigured } from '../api';
import { userMessageKey } from '../api/errors';
import { msg, type Message } from '../core/message';
import { fetchServerSubscription, verifyPurchase } from '../api/subscription';
import { normalizePurchase, pickLatestPurchase, shouldResync, type RawPurchase } from '../core/billing';
import { usePetStore } from '../store/usePetStore';
import {
  addPurchaseListeners,
  billingErrorKey,
  connect,
  disconnect,
  fetchAvailablePurchases,
  fetchProducts,
  finishPurchase,
  isBillingAvailable,
  openManageSubscriptions,
  requestProSubscription,
  type StoreProduct,
} from './iap';

const platform = (): 'android' | 'ios' => (Platform.OS === 'ios' ? 'ios' : 'android');

export interface BillingState {
  /** 이 기기에서 결제를 시도할 수 있는지 (네이티브 모듈 + 서버 설정) */
  available: boolean;
  loading: boolean;
  /** 구매·복원·검증이 진행 중 */
  busy: boolean;
  products: StoreProduct[];
  /** 사용자에게 보여 줄 안내/오류 한 줄 (번역 참조) */
  notice: Message | null;
  clearNotice: () => void;
  buy: (sku: string) => Promise<void>;
  restore: () => Promise<void>;
  openManage: () => Promise<void>;
}

/**
 * 결제 흐름 전체를 한곳에 모은다.
 *
 * 구매 → (스토어) → purchaseUpdatedListener → 서버 검증 → 구독 상태 반영 → finishTransaction
 *
 * 순서가 중요하다. **검증 전에 finishTransaction 을 부르면** 영수증이 사라져
 * 결제는 됐는데 프로가 안 열리는 상태가 되고, **끝내 부르지 않으면** Play 가 3일 뒤 자동 환불한다.
 */
export function useBilling(): BillingState {
  const setSubscription = usePetStore((s) => s.setSubscription);
  const [available, setAvailable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [products, setProducts] = useState<StoreProduct[]>([]);
  const [notice, setNotice] = useState<Message | null>(null);
  const mounted = useRef(true);

  const handlePurchase = useCallback(
    async (raw: RawPurchase) => {
      const purchase = normalizePurchase(raw, platform());
      if (!purchase) {
        setBusy(false);
        return;
      }

      // 느린 결제 수단(계좌이체 등)은 승인될 때 이벤트가 다시 온다. 지금은 마무리하지 않는다.
      if (purchase.pending) {
        setBusy(false);
        setNotice(msg('billing.notice.pending'));
        return;
      }

      try {
        const subscription = await verifyPurchase(purchase);
        setSubscription(subscription);
        // 검증에 성공한 뒤에만 마무리한다
        await finishPurchase(raw);
        setNotice(msg(subscription.pro ? 'billing.notice.purchased' : 'billing.notice.notActive'));
      } catch (error) {
        // 마무리하지 않았으므로 다음 실행에서 이 구매가 다시 전달된다.
        setNotice(msg('billing.notice.verifyFailed', { reason: `@${userMessageKey(error)}` }));
      } finally {
        if (mounted.current) setBusy(false);
      }
    },
    [setSubscription],
  );

  useEffect(() => {
    mounted.current = true;
    const nativeReady = isBillingAvailable();
    setAvailable(nativeReady && isConfigured);

    if (!nativeReady) {
      setLoading(false);
      return () => {
        mounted.current = false;
      };
    }

    const remove = addPurchaseListeners({
      onPurchase: (raw) => void handlePurchase(raw),
      onError: (error) => {
        setBusy(false);
        const key = billingErrorKey(error);
        if (key) setNotice(msg(key));
      },
    });

    void (async () => {
      await connect();
      const list = await fetchProducts();
      if (mounted.current) {
        setProducts(list);
        setLoading(false);
      }
    })();

    return () => {
      mounted.current = false;
      remove();
      void disconnect();
    };
  }, [handlePurchase]);

  const buy = useCallback(
    async (sku: string) => {
    if (busy) return;
    setNotice(null);
    setBusy(true);
    try {
      const offerToken = products.find((p) => p.productId === sku)?.offerToken;
      await requestProSubscription(sku, offerToken);
      // 성공/실패는 리스너로 들어온다. busy 해제도 거기서.
    } catch (error) {
      setBusy(false);
      setNotice(msg(billingErrorKey(error as { code?: string }) ?? 'billing.notice.startFailed'));
    }
    },
    [busy, products],
  );

  const restore = useCallback(async () => {
    if (busy) return;
    setNotice(null);
    setBusy(true);
    try {
      const purchases = await fetchAvailablePurchases();
      const latest = pickLatestPurchase(purchases, platform());

      if (!latest) {
        // 스토어에 없더라도 서버에 기록이 남아 있을 수 있다 (기기 변경 등)
        const server = await fetchServerSubscription();
        if (server?.pro) {
          setSubscription(server);
          setNotice(msg('billing.notice.restored'));
        } else {
          setNotice(msg('billing.notice.restoreNone'));
        }
        return;
      }

      const subscription = await verifyPurchase(latest);
      setSubscription(subscription);
      setNotice(msg(subscription.pro ? 'billing.notice.restored' : 'billing.notice.expired'));
    } catch (error) {
      setNotice(msg(userMessageKey(error)));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }, [busy, setSubscription]);

  return {
    available,
    loading,
    busy,
    products,
    notice,
    clearNotice: () => setNotice(null),
    buy,
    restore,
    openManage: openManageSubscriptions,
  };
}

/**
 * 앱을 열 때 서버와 구독 상태를 맞춘다.
 * 해지·환불·결제 실패는 앱이 모르는 사이에 일어나므로, 로컬 값만 믿으면 안 된다.
 */
export async function syncSubscriptionFromServer(): Promise<void> {
  if (!isConfigured) return;
  const state = usePetStore.getState();
  if (!shouldResync(state.subscription)) return;

  const server = await fetchServerSubscription();
  if (server) usePetStore.getState().setSubscription(server);
}
