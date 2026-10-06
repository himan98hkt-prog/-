// 명함 → 각 시스템 형식 변환. 네트워크/네이티브 호출 없이 순수 함수로만 구성해 테스트한다.
import { formatKoreanPhone, phoneDigits, splitName, toE164Korea } from './normalize';
import { filterCards as filterBy, matchesQuery } from './organize';
import { BusinessCard, CardKind, KIND_LABEL } from './types';

/** 휴대폰 연락처(expo-contacts CreateContactRecord 와 같은 모양) */
export interface DeviceContactRecord {
  givenName?: string;
  familyName?: string;
  company?: string;
  department?: string;
  jobTitle?: string;
  note?: string;
  phones?: { label?: string; number?: string }[];
  emails?: { label?: string; address?: string }[];
  urlAddresses?: { label?: string; url?: string }[];
  addresses?: { label?: string; street?: string }[];
}

export type ContactNameStyle = 'name' | 'company' | 'companyTitle';

/** 연락처 이름 뒤에 붙일 소속 — 전화 수신 화면에 "홍길동 (한빛상사 팀장)" 으로 보이게 */
export function contactNameSuffix(card: Pick<BusinessCard, 'company' | 'title'>, style: ContactNameStyle): string {
  if (style === 'name') return '';
  const org = companyShort(card.company);
  const inner = style === 'companyTitle' ? [org, card.title].filter(Boolean).join(' ') : org;
  return inner ? ` (${inner})` : '';
}

/** 표시용 회사명 — (주)·주식회사 같은 법인 표기를 뺀다 */
export function companyShort(company: string): string {
  return company.replace(/\(주\)|㈜|주식회사|\(유\)|유한회사/g, '').replace(/\s+/g, ' ').trim();
}

export function toDeviceContact(card: BusinessCard, style: ContactNameStyle = 'name'): DeviceContactRecord {
  const split = splitName(card.name || card.nameEn);
  const family = split.family;
  const given = (split.given + contactNameSuffix(card, style)).trim();
  const phones: { label: string; number: string }[] = [];
  if (card.mobile) phones.push({ label: 'mobile', number: card.mobile });
  if (card.phone) phones.push({ label: 'work', number: card.phone });
  if (card.fax) phones.push({ label: 'workFax', number: card.fax });
  const noteLines = [`[${KIND_LABEL[card.kind]}] 명함 스캔 ${card.createdAt.slice(0, 10)}`];
  if (card.nameEn && card.name) noteLines.push(card.nameEn);
  if (card.memo) noteLines.push(card.memo);
  const rec: DeviceContactRecord = {
    givenName: given || undefined,
    familyName: family || undefined,
    company: card.company || undefined,
    department: card.department || undefined,
    jobTitle: card.title || undefined,
    note: noteLines.join('\n'),
    phones,
    emails: card.email ? [{ label: 'work', address: card.email }] : [],
    urlAddresses: card.website ? [{ label: 'work', url: card.website }] : [],
    addresses: card.address ? [{ label: 'work', street: card.address }] : [],
  };
  return rec;
}

/** 범용 웹훅(ERP·그룹웨어·Zapier·Make·n8n) 으로 보내는 JSON */
export function toWebhookPayload(card: BusinessCard, event: 'card.created' | 'card.updated') {
  return {
    event,
    source: 'cardscan',
    card: {
      id: card.id,
      kind: card.kind,
      kindLabel: KIND_LABEL[card.kind],
      name: card.name,
      nameEn: card.nameEn,
      company: card.company,
      department: card.department,
      title: card.title,
      mobile: card.mobile,
      mobileE164: card.mobile ? toE164Korea(card.mobile) : '',
      phone: card.phone,
      fax: card.fax,
      email: card.email,
      website: card.website,
      address: card.address,
      memo: card.memo,
      extra: card.extra,
      createdAt: card.createdAt,
      updatedAt: card.updatedAt,
    },
  };
}

/** 구글 시트 열 순서 — docs/google-sheets.gs 의 HEADERS 와 반드시 같아야 한다. */
export const SHEET_HEADERS = [
  'id', '구분', '이름', '영문이름', '회사', '부서', '직책', '휴대폰', '전화', '팩스', '이메일', '웹사이트', '주소', '메모', '등록일', '수정일',
] as const;

export function toSheetRow(card: BusinessCard): string[] {
  return [
    card.id, KIND_LABEL[card.kind], card.name, card.nameEn, card.company, card.department, card.title,
    card.mobile, card.phone, card.fax, card.email, card.website, card.address, card.memo, card.createdAt, card.updatedAt,
  ];
}

/** HubSpot CRM contact 기본 속성 */
export function toHubSpotProperties(card: BusinessCard): Record<string, string> {
  const { family, given } = splitName(card.name || card.nameEn);
  const props: Record<string, string> = {
    firstname: given,
    lastname: family,
    company: card.company,
    jobtitle: [card.department, card.title].filter(Boolean).join(' / '),
    mobilephone: card.mobile ? toE164Korea(card.mobile) : '',
    phone: card.phone ? toE164Korea(card.phone) : '',
    fax: card.fax ? toE164Korea(card.fax) : '',
    email: card.email,
    website: card.website,
    address: card.address,
    lifecyclestage: card.kind === 'customer' ? 'customer' : card.kind === 'partner' ? 'other' : '',
  };
  // 빈 값을 보내면 HubSpot 에 이미 있던 값을 지워 버리므로 뺀다
  for (const k of Object.keys(props)) if (!props[k]) delete props[k];
  return props;
}

export function toSlackMessage(card: BusinessCard): { text: string } {
  const who = [card.name, card.title].filter(Boolean).join(' ');
  const org = [card.company, card.department].filter(Boolean).join(' ');
  const reach = [card.mobile, card.email].filter(Boolean).join(' · ');
  return { text: `:card_index: 새 ${KIND_LABEL[card.kind]} 명함 — *${who || '이름 미상'}*${org ? ` (${org})` : ''}${reach ? `\n${reach}` : ''}` };
}

function vEscape(s: string): string {
  return s.replace(/\\/g, '\\\\').replace(/\n/g, '\\n').replace(/([,;])/g, '\\$1');
}

/** vCard 3.0 — 다른 사람에게 명함을 공유하거나 PC 주소록으로 옮길 때 쓴다. */
export function toVCard(card: BusinessCard): string {
  const { family, given } = splitName(card.name || card.nameEn);
  const lines = ['BEGIN:VCARD', 'VERSION:3.0', `N:${vEscape(family)};${vEscape(given)};;;`, `FN:${vEscape(card.name || card.nameEn)}`];
  if (card.company || card.department) lines.push(`ORG:${vEscape(card.company)}${card.department ? ';' + vEscape(card.department) : ''}`);
  if (card.title) lines.push(`TITLE:${vEscape(card.title)}`);
  if (card.mobile) lines.push(`TEL;TYPE=CELL:${card.mobile}`);
  if (card.phone) lines.push(`TEL;TYPE=WORK,VOICE:${card.phone}`);
  if (card.fax) lines.push(`TEL;TYPE=WORK,FAX:${card.fax}`);
  if (card.email) lines.push(`EMAIL;TYPE=INTERNET,WORK:${card.email}`);
  if (card.website) lines.push(`URL:${card.website}`);
  if (card.address) lines.push(`ADR;TYPE=WORK:;;${vEscape(card.address)};;;;`);
  if (card.memo) lines.push(`NOTE:${vEscape(card.memo)}`);
  lines.push('END:VCARD');
  return lines.join('\r\n');
}

/** 같은 사람인지 — 휴대폰 번호나 이메일이 같으면 동일인으로 본다. */
export function isSamePerson(a: Pick<BusinessCard, 'mobile' | 'email'>, b: Pick<BusinessCard, 'mobile' | 'email'>): boolean {
  const ma = phoneDigits(a.mobile);
  const mb = phoneDigits(b.mobile);
  if (ma.length >= 10 && ma === mb) return true;
  const ea = a.email.trim().toLowerCase();
  return !!ea && ea === b.email.trim().toLowerCase();
}

export function findDuplicate(cards: BusinessCard[], card: BusinessCard): BusinessCard | undefined {
  return cards.find((c) => c.id !== card.id && isSamePerson(c, card));
}

/** 검색·필터는 organize.ts 로 옮겼다 — 예전 호출 모양을 유지하는 얇은 래퍼 */
export { matchesQuery };
export function filterCards(cards: BusinessCard[], query: string, kind: CardKind | 'all'): BusinessCard[] {
  return filterBy(cards, { query, kind });
}

export { formatKoreanPhone };
