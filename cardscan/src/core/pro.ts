// Pro 평생 이용권 규칙 — 무료로 어디까지, Pro 로 무엇이 열리는지.
// 원칙: 이미 저장한 명함은 한도를 넘어도 계속 보고·고치고·백업할 수 있다 (데이터를 볼모로 잡지 않는다).
import { ConnectorId } from './types';
import { Settings } from './settings';

/** 구글 플레이 콘솔의 인앱 상품 ID (일회성 상품, 한 번 사면 영구) */
export const PRO_SKU = 'pro_lifetime';
/** 무료로 저장할 수 있는 명함 수 */
export const FREE_CARD_LIMIT = 50;
/** 통화별 정가 — 스토어 가격이 이보다 낮으면 "출시 기념가" 로 보여 준다 (콘솔 가격과 맞출 것) */
export const PRO_REGULAR_PRICE: Record<string, number> = { KRW: 3900, USD: 2.99 };
export const PRO_REGULAR_PRICE_KRW = PRO_REGULAR_PRICE.KRW;

export type ProFeature = 'cards' | 'connectors' | 'csv' | 'batch' | 'continuous';

/** 결제 화면에서 "왜 Pro 가 필요한지" 한 줄 */
export const PRO_REASON: Record<ProFeature, string> = {
  cards: `무료로는 명함 ${FREE_CARD_LIMIT}장까지 저장할 수 있어요`,
  connectors: '구글 시트·HubSpot·웹훅·슬랙 자동 입력은 Pro 기능이에요',
  csv: '엑셀(CSV) 내보내기는 Pro 기능이에요',
  batch: '앨범에서 여러 장 한 번에 등록은 Pro 기능이에요',
  continuous: '연속 촬영은 Pro 기능이에요',
};

/** Pro 로 열리는 것 (결제 화면 목록) */
export const PRO_BENEFITS: string[] = [
  '명함 저장 무제한',
  '구글 시트·HubSpot·웹훅·슬랙 자동 입력',
  '엑셀(CSV) 내보내기',
  '앨범에서 여러 장 한 번에 · 연속 촬영',
  '한 번 결제로 평생 · 앞으로 추가되는 Pro 기능 포함',
];

/** 새 명함을 더 저장할 수 있는지 (같은 사람 갱신은 늘 가능 — 호출하는 쪽에서 판단) */
export function canAddCard(count: number, isPro: boolean): boolean {
  return isPro || count < FREE_CARD_LIMIT;
}

/** 휴대폰 연락처 저장은 무료, 외부 업무 시스템 연동은 Pro */
export function isProConnector(id: ConnectorId): boolean {
  return id !== 'contacts';
}

/** 실제 전송에 쓰는 설정 — Pro 가 아니면(환불 등) 외부 연동을 꺼진 것으로 본다 */
export function effectiveSettings(settings: Settings, isPro: boolean): Settings {
  if (isPro) return settings;
  const connectors = { ...settings.connectors };
  for (const id of Object.keys(connectors) as ConnectorId[]) {
    if (isProConnector(id) && connectors[id].enabled) connectors[id] = { ...connectors[id], enabled: false } as never;
  }
  return { ...settings, connectors, continuousScan: false };
}

/** 스토어 가격이 그 통화의 정가보다 낮으면 출시 기념가 */
export function isLaunchSale(price: number | null | undefined, currency: string | undefined): boolean {
  const regular = currency ? PRO_REGULAR_PRICE[currency] : undefined;
  return !!regular && typeof price === 'number' && price > 0 && price < regular;
}

/** 정가 표시 (₩3,900 / $2.99) — Intl 이 없거나 실패하면 숫자 + 통화 */
export function regularPriceLabel(currency: string | undefined, locale = 'ko-KR'): string {
  const regular = currency ? PRO_REGULAR_PRICE[currency] : undefined;
  if (!regular || !currency) return '';
  try {
    return new Intl.NumberFormat(locale, { style: 'currency', currency, maximumFractionDigits: currency === 'KRW' ? 0 : 2 }).format(regular);
  } catch {
    return `${regular} ${currency}`;
  }
}
