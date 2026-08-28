import { describe, expect, it } from 'vitest';
import {
  entitlementFromApple,
  entitlementFromPlay,
  parseRtdnMessage,
} from '../supabase/functions/_shared/entitlement';

const NOW = Date.UTC(2026, 7, 28, 12);
const DAY = 24 * 60 * 60 * 1000;

describe('entitlementFromPlay', () => {
  const base = {
    subscriptionState: 'SUBSCRIPTION_STATE_ACTIVE',
    acknowledgementState: 'ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED',
    lineItems: [
      {
        productId: 'petvoice_pro_monthly',
        expiryTime: new Date(NOW + 30 * DAY).toISOString(),
        autoRenewingPlan: { autoRenewEnabled: true },
      },
    ],
  };

  it('활성 구독을 읽는다', () => {
    const e = entitlementFromPlay(base);
    expect(e).toMatchObject({
      state: 'active',
      expiresAt: NOW + 30 * DAY,
      autoRenewing: true,
      productId: 'petvoice_pro_monthly',
      store: 'play',
    });
  });

  it('Play 의 상태 열거값을 우리 상태로 옮긴다', () => {
    const cases: [string, string][] = [
      ['SUBSCRIPTION_STATE_IN_GRACE_PERIOD', 'grace'],
      ['SUBSCRIPTION_STATE_ON_HOLD', 'on_hold'],
      ['SUBSCRIPTION_STATE_PAUSED', 'paused'],
      ['SUBSCRIPTION_STATE_CANCELED', 'canceled'],
      ['SUBSCRIPTION_STATE_EXPIRED', 'expired'],
      ['SUBSCRIPTION_STATE_PENDING', 'pending'],
    ];
    for (const [playState, expected] of cases) {
      expect(entitlementFromPlay({ ...base, subscriptionState: playState }).state).toBe(expected);
    }
  });

  it('모르는 상태는 none', () => {
    expect(entitlementFromPlay({ subscriptionState: 'SOMETHING_NEW' }).state).toBe('none');
  });

  it('요금제 변경 중 lineItems 가 여러 개면 가장 늦은 만료를 쓴다', () => {
    const e = entitlementFromPlay({
      ...base,
      lineItems: [
        { productId: 'old', expiryTime: new Date(NOW + DAY).toISOString(), autoRenewingPlan: { autoRenewEnabled: false } },
        {
          productId: 'petvoice_pro_monthly',
          expiryTime: new Date(NOW + 30 * DAY).toISOString(),
          autoRenewingPlan: { autoRenewEnabled: true },
        },
      ],
    });
    expect(e.expiresAt).toBe(NOW + 30 * DAY);
    expect(e.productId).toBe('petvoice_pro_monthly');
    expect(e.autoRenewing).toBe(true);
  });

  it('승인 대기 상태를 표시한다', () => {
    expect(entitlementFromPlay({ ...base, acknowledgementState: 'ACKNOWLEDGEMENT_STATE_PENDING' }).needsAcknowledge).toBe(true);
    expect(entitlementFromPlay(base).needsAcknowledge).toBe(false);
  });

  it('테스트 구매를 표시한다', () => {
    expect(entitlementFromPlay({ ...base, testPurchase: {} }).testPurchase).toBe(true);
    expect(entitlementFromPlay(base).testPurchase).toBe(false);
  });

  it('lineItems 가 없어도 죽지 않는다', () => {
    expect(entitlementFromPlay({ subscriptionState: 'SUBSCRIPTION_STATE_EXPIRED' })).toMatchObject({
      state: 'expired',
      expiresAt: null,
      productId: null,
    });
  });
});

describe('entitlementFromApple', () => {
  const receipt = (expiresMs: number, autoRenew = '1', extra: Record<string, string> = {}) => ({
    status: 0,
    latest_receipt_info: [
      { product_id: 'petvoice_pro_monthly', expires_date_ms: String(expiresMs), original_transaction_id: 'orig-1' },
    ],
    pending_renewal_info: [{ auto_renew_status: autoRenew, ...extra }],
  });

  it('만료 전 + 자동갱신이면 active', () => {
    const e = entitlementFromApple(receipt(NOW + 10 * DAY), NOW);
    expect(e).toMatchObject({ state: 'active', expiresAt: NOW + 10 * DAY, autoRenewing: true, store: 'appstore' });
  });

  it('만료 전 + 자동갱신 꺼짐이면 해지 예약', () => {
    expect(entitlementFromApple(receipt(NOW + 10 * DAY, '0'), NOW).state).toBe('canceled');
  });

  it('만료됐고 유예 기간이 남았으면 grace, 만료 시각은 유예 종료로 본다', () => {
    const graceUntil = NOW + 3 * DAY;
    const e = entitlementFromApple(
      receipt(NOW - DAY, '1', { is_in_billing_retry_period: '1', grace_period_expires_date_ms: String(graceUntil) }),
      NOW,
    );
    expect(e.state).toBe('grace');
    expect(e.expiresAt).toBe(graceUntil);
  });

  it('유예 없이 결제 재시도 중이면 on_hold', () => {
    expect(entitlementFromApple(receipt(NOW - DAY, '1', { is_in_billing_retry_period: '1' }), NOW).state).toBe('on_hold');
  });

  it('그냥 지났으면 expired', () => {
    expect(entitlementFromApple(receipt(NOW - DAY, '0'), NOW).state).toBe('expired');
  });

  it('여러 영수증 중 가장 늦은 만료를 쓴다', () => {
    const e = entitlementFromApple(
      {
        status: 0,
        latest_receipt_info: [
          { product_id: 'petvoice_pro_monthly', expires_date_ms: String(NOW - 30 * DAY) },
          { product_id: 'petvoice_pro_monthly', expires_date_ms: String(NOW + 5 * DAY) },
        ],
        pending_renewal_info: [{ auto_renew_status: '1' }],
      },
      NOW,
    );
    expect(e.expiresAt).toBe(NOW + 5 * DAY);
    expect(e.state).toBe('active');
  });

  it('구매 이력이 없으면 none', () => {
    expect(entitlementFromApple({ status: 0, latest_receipt_info: [] }, NOW).state).toBe('none');
  });
});

describe('parseRtdnMessage', () => {
  it('구독 알림을 읽는다', () => {
    const payload = JSON.stringify({
      version: '1.0',
      packageName: 'app.petvoice.ai',
      subscriptionNotification: { version: '1.0', notificationType: 13, purchaseToken: 'tok', subscriptionId: 'petvoice_pro_monthly' },
    });
    expect(parseRtdnMessage(payload)).toEqual({
      purchaseToken: 'tok',
      subscriptionId: 'petvoice_pro_monthly',
      notificationType: 13,
      notificationName: 'EXPIRED',
    });
  });

  it('테스트 알림처럼 구독 정보가 없으면 null', () => {
    expect(parseRtdnMessage(JSON.stringify({ testNotification: { version: '1.0' } }))).toBeNull();
  });

  it('망가진 JSON 도 null 로 흘려보낸다', () => {
    expect(parseRtdnMessage('not json')).toBeNull();
  });

  it('모르는 알림 유형에도 이름을 붙인다', () => {
    const payload = JSON.stringify({ subscriptionNotification: { notificationType: 99, purchaseToken: 'tok' } });
    expect(parseRtdnMessage(payload)?.notificationName).toBe('UNKNOWN_99');
  });
});
