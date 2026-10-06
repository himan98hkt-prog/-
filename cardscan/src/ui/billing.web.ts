// 웹앱(아이폰)에는 구글 플레이 결제가 없다 — 모든 기능을 연다.
export const BILLING_ENABLED = false;

export interface ProProduct {
  displayPrice: string;
  price: number | null;
  currency: string;
}
export type OwnedState = 'owned' | 'pending' | 'none';

export async function checkOwned(): Promise<OwnedState | null> {
  return null;
}
export async function loadProduct(): Promise<ProProduct | null> {
  return null;
}
export async function buyPro(): Promise<void> {
  throw new Error('Billing is not available here');
}
export function watchPurchases(): () => void {
  return () => {};
}
