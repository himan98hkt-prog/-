// 휴대폰 주소록 연동 (expo-contacts, Expo SDK 57 의 Contact 클래스 API)
import { Contact, requestPermissionsAsync } from 'expo-contacts';
import { toDeviceContact } from '../core/mapping';
import { phoneDigits } from '../core/normalize';
import { BusinessCard } from '../core/types';
import { Connector } from './http';

async function ensurePermission() {
  const { granted } = await requestPermissionsAsync();
  if (!granted) throw new Error('연락처 접근 권한이 없습니다. 설정 > 앱 > 권한에서 연락처를 허용하세요.');
}

/** 이름이 같은 연락처 중 휴대폰 번호가 같은 사람을 찾는다 — 같은 명함을 두 번 찍어도 중복 연락처가 생기지 않게 */
async function findExisting(card: BusinessCard): Promise<Contact | undefined> {
  const mobile = phoneDigits(card.mobile);
  if (!card.name || mobile.length < 10) return undefined;
  const candidates = await Contact.getAll({ name: card.name, limit: 20 });
  for (const c of candidates) {
    const phones = await c.getPhones();
    if (phones.some((p) => phoneDigits(p.number ?? '') === mobile)) return c;
  }
  return undefined;
}

export const deviceContactsConnector: Connector = async (card, { previous, settings }) => {
  await ensurePermission();
  const record = toDeviceContact(card, settings.contactName);

  if (previous?.remoteId) {
    try {
      await new Contact(previous.remoteId).update(record);
      return { remoteId: previous.remoteId, message: '연락처 갱신' };
    } catch {
      // 사용자가 주소록에서 지운 경우 — 아래에서 다시 찾거나 새로 만든다
    }
  }

  const existing = await findExisting(card);
  if (existing) {
    // 원래 있던 연락처는 사용자가 넣어 둔 정보(생일·다른 번호 등)를 지우지 않도록 회사 정보만 고치고 빠진 항목만 더한다
    await existing.patch({ company: record.company, department: record.department, jobTitle: record.jobTitle });
    const known = new Set((await existing.getPhones()).map((p) => phoneDigits(p.number ?? '')));
    for (const p of record.phones ?? []) if (!known.has(phoneDigits(p.number ?? ''))) await existing.addPhone(p);
    const emails = new Set((await existing.getEmails()).map((e) => (e.address ?? '').toLowerCase()));
    for (const e of record.emails ?? []) if (!emails.has((e.address ?? '').toLowerCase())) await existing.addEmail(e);
    return { remoteId: existing.id, message: '기존 연락처에 합침' };
  }
  const created = await Contact.create(record);
  return { remoteId: created.id, message: '새 연락처 저장' };
};
