import { describe, expect, it } from 'vitest';
import { canAddCard, effectiveSettings, FREE_CARD_LIMIT, isLaunchSale, isProConnector } from '../src/core/pro';
import { connectorTargets, DEFAULT_SETTINGS, setPath } from '../src/core/settings';

describe('Pro 규칙', () => {
  it(`무료는 ${FREE_CARD_LIMIT}장까지, Pro 는 무제한`, () => {
    expect(canAddCard(FREE_CARD_LIMIT - 1, false)).toBe(true);
    expect(canAddCard(FREE_CARD_LIMIT, false)).toBe(false);
    expect(canAddCard(10_000, true)).toBe(true);
  });

  it('휴대폰 연락처는 무료, 외부 연동은 Pro', () => {
    expect(isProConnector('contacts')).toBe(false);
    for (const id of ['sheets', 'hubspot', 'webhook', 'slack'] as const) expect(isProConnector(id)).toBe(true);
  });

  it('Pro 가 아니면 켜 둔 외부 연동도 보내지 않는다 (환불 등)', () => {
    let s = setPath(DEFAULT_SETTINGS, 'connectors.sheets.enabled', true);
    s = setPath(s, 'connectors.sheets.url', 'https://script.google.com/macros/s/x/exec');
    s = { ...s, continuousScan: true };
    expect(connectorTargets(s, 'customer')).toContain('sheets');
    const free = effectiveSettings(s, false);
    expect(connectorTargets(free, 'customer')).toEqual(['contacts']);
    expect(free.continuousScan).toBe(false);
    // 원래 설정은 그대로 (다시 Pro 가 되면 바로 동작)
    expect(s.connectors.sheets.enabled).toBe(true);
    expect(effectiveSettings(s, true)).toBe(s);
  });

  it('정가보다 낮은 원화 가격만 출시 기념가', () => {
    expect(isLaunchSale(1900, 'KRW')).toBe(true);
    expect(isLaunchSale(3900, 'KRW')).toBe(false);
    expect(isLaunchSale(1.99, 'USD')).toBe(false);
    expect(isLaunchSale(null, 'KRW')).toBe(false);
  });
});
