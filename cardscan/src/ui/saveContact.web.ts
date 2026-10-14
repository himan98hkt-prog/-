// 웹(아이폰): vCard(.vcf)를 열어 iOS 연락처 카드 화면을 띄운다 → 사용자가 "새로운 연락처 생성"을 누른다.
import { toVCard } from '../core/mapping';
import { t } from '../i18n';
import { BusinessCard } from '../core/types';

export const CAN_OPEN_VCARD = true;

function open(vcf: string, filename: string) {
  const blob = new Blob([vcf], { type: 'text/vcard;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

const safe = (s: string) => s.replace(/[\\/:*?"<>|]/g, '').trim() || t('명함');

export function openVCard(card: BusinessCard): void {
  open(toVCard(card), `${safe(card.name || card.company)}.vcf`);
}

/** 명함 전체를 한 파일로 — 아이폰 연락처에서 한 번에 여러 명 추가 */
export function exportAllVCards(cards: BusinessCard[]): void {
  open(cards.map(toVCard).join('\r\n'), t('명함스캔-전체-{1}명.vcf', { 1: cards.length }));
}
