import { describe, expect, it } from 'vitest';
import {
  PRO_MONTHLY_SKU,
  PRO_YEARLY_SKU,
  RESYNC_INTERVAL_MS,
  periodOfSku,
  savingsPercent,
  describeSubscription,
  freeTrialPeriod,
  parseIsoPeriod,
  normalizePurchase,
  pickAndroidOffer,
  pickLatestPurchase,
  shouldResync,
  subscriptionFromEntitlement,
} from '../src/core/billing';

const NOW = Date.UTC(2026, 7, 28, 12);
const DAY = 24 * 60 * 60 * 1000;

describe('subscriptionFromEntitlement', () => {
  it('활성 구독은 프로를 연다', () => {
    const sub = subscriptionFromEntitlement(
      { state: 'active', expiresAt: NOW + 30 * DAY, autoRenewing: true },
      NOW,
    );
    expect(sub.pro).toBe(true);
    expect(sub.state).toBe('active');
    expect(sub.verifiedAt).toBe(NOW);
  });

  it('유예 기간(결제 실패)에도 기능을 유지한다', () => {
    expect(subscriptionFromEntitlement({ state: 'grace', expiresAt: NOW + DAY }, NOW).pro).toBe(true);
  });

  it('해지 예약은 만료 전까지 이용 가능하다', () => {
    const sub = subscriptionFromEntitlement(
      { state: 'canceled', expiresAt: NOW + 5 * DAY, autoRenewing: false },
      NOW,
    );
    expect(sub.pro).toBe(true);
    expect(sub.autoRenewing).toBe(false);
  });

  it('해지 예약이라도 만료가 지나면 잠근다', () => {
    expect(subscriptionFromEntitlement({ state: 'canceled', expiresAt: NOW - DAY }, NOW).pro).toBe(false);
  });

  it('만료 시각을 모르는 해지 예약은 열어 주지 않는다', () => {
    expect(subscriptionFromEntitlement({ state: 'canceled' }, NOW).pro).toBe(false);
  });

  it('보류(on_hold)·일시정지·만료는 잠근다', () => {
    for (const state of ['on_hold', 'paused', 'expired', 'pending', 'none']) {
      expect(subscriptionFromEntitlement({ state, expiresAt: NOW + DAY }, NOW).pro).toBe(false);
    }
  });

  it('활성이어도 만료가 지났으면 잠근다', () => {
    expect(subscriptionFromEntitlement({ state: 'active', expiresAt: NOW - 1 }, NOW).pro).toBe(false);
  });

  it('초 단위 timestamp 와 ISO 문자열을 모두 받는다', () => {
    const seconds = subscriptionFromEntitlement({ state: 'active', expiresAt: (NOW + DAY) / 1000 }, NOW);
    const iso = subscriptionFromEntitlement(
      { state: 'active', expiresAt: new Date(NOW + DAY).toISOString() as never },
      NOW,
    );
    expect(seconds.expiresAt).toBe(NOW + DAY);
    expect(iso.expiresAt).toBe(NOW + DAY);
  });

  it('모르는 상태 문자열은 none 으로 떨어뜨린다', () => {
    expect(subscriptionFromEntitlement({ state: 'SOMETHING_NEW', expiresAt: NOW + DAY }, NOW).state).toBe(
      'none',
    );
  });

  it('스토어 표기를 정규화한다', () => {
    expect(subscriptionFromEntitlement({ state: 'active', store: 'apple' }, NOW).store).toBe('appstore');
    expect(subscriptionFromEntitlement({ state: 'active', store: 'PLAY' }, NOW).store).toBe('play');
  });
});

describe('shouldResync', () => {
  it('검증 이력이 없는 순수 무료 사용자는 굳이 묻지 않는다', () => {
    expect(shouldResync({ pro: false }, NOW)).toBe(false);
  });

  it('결제 이력이 있으면 검증 기록이 없을 때 맞춘다', () => {
    expect(shouldResync({ pro: false, productId: 'petvoice_pro_monthly' }, NOW)).toBe(true);
  });

  it('마지막 검증이 오래됐으면 맞춘다', () => {
    expect(shouldResync({ pro: true, verifiedAt: NOW - RESYNC_INTERVAL_MS - 1 }, NOW)).toBe(true);
    expect(shouldResync({ pro: true, verifiedAt: NOW - 60_000 }, NOW)).toBe(false);
  });

  it('만료가 코앞이면 주기와 무관하게 맞춘다', () => {
    expect(
      shouldResync({ pro: true, verifiedAt: NOW - 60_000, expiresAt: NOW + 3 * 60 * 60 * 1000 }, NOW),
    ).toBe(true);
  });
});

describe('describeSubscription', () => {
  it('무료 · 자동갱신 · 해지 예약 · 유예를 구분해 설명한다', () => {
    expect(describeSubscription({ pro: false })).toMatchObject({ key: 'billing.state.free' });
    expect(
      describeSubscription({ pro: true, state: 'active', autoRenewing: true, expiresAt: NOW + DAY }),
    ).toMatchObject({
      key: 'billing.state.renewsOn',
    });
    expect(
      describeSubscription({ pro: true, state: 'canceled', autoRenewing: false, expiresAt: NOW + DAY }),
    ).toMatchObject({
      key: 'billing.state.canceledUntil',
    });
    expect(describeSubscription({ pro: true, state: 'grace', expiresAt: NOW + DAY })).toMatchObject({
      key: 'billing.state.graceUntil',
    });
  });

  it('만료 시각을 모르면 날짜 없는 문구를 쓴다', () => {
    expect(describeSubscription({ pro: true, state: 'active', autoRenewing: true })).toMatchObject({
      key: 'billing.state.active',
    });
  });
});

describe('Play 오퍼 선택', () => {
  const paid = {
    offerToken: 'paid-token',
    pricingPhases: { pricingPhaseList: [{ priceAmountMicros: '3900000', formattedPrice: '₩3,900' }] },
  };
  const trial = {
    offerToken: 'trial-token',
    pricingPhases: {
      pricingPhaseList: [
        { priceAmountMicros: '0', billingPeriod: 'P1W' },
        { priceAmountMicros: '3900000', formattedPrice: '₩3,900' },
      ],
    },
  };

  it('무료 체험 오퍼가 있으면 그쪽을 먼저 고른다', () => {
    expect(pickAndroidOffer([paid, trial])?.offerToken).toBe('trial-token');
  });

  it('무료 체험이 없으면 첫 오퍼', () => {
    expect(pickAndroidOffer([paid])?.offerToken).toBe('paid-token');
  });

  it('오퍼가 없으면 null', () => {
    expect(pickAndroidOffer([])).toBeNull();
    expect(pickAndroidOffer(undefined)).toBeNull();
  });

  it('체험 기간을 구조로 돌려준다', () => {
    expect(freeTrialPeriod(trial)).toEqual({ unit: 'day', count: 7 });
    expect(freeTrialPeriod(paid)).toBeNull();
  });

  it('ISO 기간 파싱 — 주는 일로 환산한다', () => {
    expect(parseIsoPeriod('P3D')).toEqual({ unit: 'day', count: 3 });
    expect(parseIsoPeriod('P2W')).toEqual({ unit: 'day', count: 14 });
    expect(parseIsoPeriod('P1M')).toEqual({ unit: 'month', count: 1 });
    expect(parseIsoPeriod('P1Y')).toEqual({ unit: 'year', count: 1 });
    expect(parseIsoPeriod('잘못된값')).toBeNull();
  });
});

describe('normalizePurchase', () => {
  it('Play 구매에서 purchaseToken 을 뽑고 승인 필요 여부를 판단한다', () => {
    const purchase = normalizePurchase(
      {
        productId: 'petvoice_pro_monthly',
        purchaseToken: 'tok',
        purchaseStateAndroid: 1,
        isAcknowledgedAndroid: false,
      },
      'android',
    );
    expect(purchase).toMatchObject({ token: 'tok', store: 'play', needsAcknowledge: true, pending: false });
  });

  it('이미 승인된 Play 구매는 다시 승인하지 않는다', () => {
    const purchase = normalizePurchase(
      {
        productId: 'petvoice_pro_monthly',
        purchaseToken: 'tok',
        purchaseStateAndroid: 1,
        isAcknowledgedAndroid: true,
      },
      'android',
    );
    expect(purchase?.needsAcknowledge).toBe(false);
  });

  it('결제 대기 중인 구매는 pending 으로 표시하고 승인하지 않는다', () => {
    const purchase = normalizePurchase(
      { productId: 'petvoice_pro_monthly', purchaseToken: 'tok', purchaseStateAndroid: 2 },
      'android',
    );
    expect(purchase?.pending).toBe(true);
    expect(purchase?.needsAcknowledge).toBe(false);
  });

  it('토큰이 없는 Play 구매는 버린다', () => {
    expect(normalizePurchase({ productId: 'petvoice_pro_monthly' }, 'android')).toBeNull();
  });

  it('iOS 는 영수증을 토큰으로 쓰고 원본 트랜잭션 ID 를 함께 담는다', () => {
    const purchase = normalizePurchase(
      {
        productId: 'petvoice_pro_monthly',
        transactionReceipt: 'receipt',
        originalTransactionIdentifierIOS: 'orig-1',
      },
      'ios',
    );
    expect(purchase).toMatchObject({ token: 'receipt', store: 'appstore', transactionId: 'orig-1' });
  });

  it('상품 ID 가 없으면 버린다', () => {
    expect(normalizePurchase({ purchaseToken: 'tok' }, 'android')).toBeNull();
    expect(normalizePurchase(null, 'android')).toBeNull();
  });
});

describe('pickLatestPurchase', () => {
  it('우리 상품만 고르고 결제 완료 건을 우선한다', () => {
    const picked = pickLatestPurchase(
      [
        { productId: '남의_상품', purchaseToken: 'x' },
        { productId: 'petvoice_pro_monthly', purchaseToken: 'pending', purchaseStateAndroid: 2 },
        { productId: 'petvoice_pro_monthly', purchaseToken: 'done', purchaseStateAndroid: 1 },
      ],
      'android',
    );
    expect(picked?.token).toBe('done');
  });

  it('복원할 게 없으면 null', () => {
    expect(pickLatestPurchase([{ productId: '남의_상품', purchaseToken: 'x' }], 'android')).toBeNull();
  });
});

describe('연간 구독', () => {
  it('상품 ID 로 결제 주기를 판단한다', () => {
    expect(periodOfSku(PRO_MONTHLY_SKU)).toBe('month');
    expect(periodOfSku(PRO_YEARLY_SKU)).toBe('year');
  });

  it('연간이 월간 대비 얼마나 싼지 계산한다', () => {
    // 월 3,900원 × 12 = 46,800원 vs 연 29,000원
    expect(savingsPercent(3900e6, 29000e6)).toBe(38);
  });

  it('연간이 더 비싸거나 같으면 배지를 달지 않는다', () => {
    expect(savingsPercent(3900e6, 46800e6)).toBeNull();
    expect(savingsPercent(3900e6, 50000e6)).toBeNull();
  });

  it('가격을 모르면 null', () => {
    expect(savingsPercent(0, 29000e6)).toBeNull();
    expect(savingsPercent(Number.NaN, 29000e6)).toBeNull();
  });
});
