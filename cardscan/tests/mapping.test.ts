import { describe, expect, it } from 'vitest';
import {
  filterCards,
  findDuplicate,
  SHEET_HEADERS,
  toDeviceContact,
  toHubSpotProperties,
  toSheetRow,
  toSlackMessage,
  toVCard,
  toWebhookPayload,
} from '../src/core/mapping';
import { makeCard } from './fixtures';

describe('toDeviceContact', () => {
  it('성/이름을 나누고 번호에 라벨을 붙인다', () => {
    const r = toDeviceContact(makeCard());
    expect(r.familyName).toBe('홍');
    expect(r.givenName).toBe('길동');
    expect(r.company).toBe('(주)한빛상사');
    expect(r.jobTitle).toBe('팀장');
    expect(r.phones).toEqual([
      { label: 'mobile', number: '010-1234-5678' },
      { label: 'work', number: '02-123-4567' },
      { label: 'workFax', number: '02-123-4568' },
    ]);
    expect(r.emails).toEqual([{ label: 'work', address: 'gd.hong@hanbit.co.kr' }]);
    expect(r.note).toContain('[고객]');
  });

  it('빈 칸은 넣지 않는다', () => {
    const r = toDeviceContact(makeCard({ phone: '', fax: '', email: '', website: '', address: '' }));
    expect(r.phones).toHaveLength(1);
    expect(r.emails).toEqual([]);
    expect(r.urlAddresses).toEqual([]);
  });
});

describe('외부 시스템 형식', () => {
  it('웹훅 payload', () => {
    const p = toWebhookPayload(makeCard({ kind: 'partner' }), 'card.created');
    expect(p.event).toBe('card.created');
    expect(p.card.kindLabel).toBe('거래처');
    expect(p.card.mobileE164).toBe('+821012345678');
  });

  it('시트 행은 헤더와 열 수가 같다', () => {
    expect(toSheetRow(makeCard())).toHaveLength(SHEET_HEADERS.length);
    expect(toSheetRow(makeCard())[1]).toBe('고객');
  });

  it('HubSpot 은 빈 값을 보내지 않는다 (기존 값 보호)', () => {
    const p = toHubSpotProperties(makeCard({ fax: '', website: '', kind: 'other' }));
    expect(p).not.toHaveProperty('fax');
    expect(p).not.toHaveProperty('website');
    expect(p).not.toHaveProperty('lifecyclestage');
    expect(p.firstname).toBe('길동');
    expect(p.lastname).toBe('홍');
    expect(p.mobilephone).toBe('+821012345678');
    expect(p.jobtitle).toBe('영업1팀 / 팀장');
  });

  it('슬랙 메시지', () => {
    expect(toSlackMessage(makeCard()).text).toContain('*홍길동 팀장*');
  });

  it('vCard 는 특수문자를 이스케이프한다', () => {
    const v = toVCard(makeCard({ memo: '점심; 미팅, 다음주\n화요일' }));
    expect(v.startsWith('BEGIN:VCARD\r\nVERSION:3.0')).toBe(true);
    expect(v).toContain('N:홍;길동;;;');
    expect(v).toContain('TEL;TYPE=CELL:010-1234-5678');
    expect(v).toContain('NOTE:점심\\; 미팅\\, 다음주\\n화요일');
    expect(v.endsWith('END:VCARD')).toBe(true);
  });
});

describe('중복 판정', () => {
  const a = makeCard({ id: 'a' });
  it('휴대폰 번호가 같으면 같은 사람 (표기 달라도)', () => {
    expect(findDuplicate([a], makeCard({ id: 'b', email: '', mobile: '+82 10 1234 5678' }))?.id).toBe('a');
  });
  it('이메일이 같으면 같은 사람 (대소문자 무시)', () => {
    expect(findDuplicate([a], makeCard({ id: 'b', mobile: '', email: 'GD.Hong@hanbit.co.kr' }))?.id).toBe('a');
  });
  it('다르면 새 사람', () => {
    expect(findDuplicate([a], makeCard({ id: 'b', mobile: '010-9999-9999', email: 'x@y.z' }))).toBeUndefined();
  });
  it('둘 다 비어 있으면 같은 사람으로 보지 않는다', () => {
    const empty = makeCard({ id: 'e1', mobile: '', email: '' });
    expect(findDuplicate([empty], makeCard({ id: 'e2', mobile: '', email: '' }))).toBeUndefined();
  });
});

describe('검색·필터', () => {
  const cards = [
    makeCard({ id: '1', name: '홍길동', createdAt: '2026-01-01' }),
    makeCard({ id: '2', name: '김영희', company: '대한물산', kind: 'partner', mobile: '010-5555-1234', email: 'yh@dh.com', createdAt: '2026-02-01' }),
  ];
  it('최신순 정렬', () => {
    expect(filterCards(cards, '', 'all').map((c) => c.id)).toEqual(['2', '1']);
  });
  it('구분 필터', () => {
    expect(filterCards(cards, '', 'partner').map((c) => c.id)).toEqual(['2']);
  });
  it('번호 일부(하이픈 무관)로 검색', () => {
    expect(filterCards(cards, '5555', 'all').map((c) => c.id)).toEqual(['2']);
    expect(filterCards(cards, '1234-5678', 'all').map((c) => c.id)).toEqual(['1']);
  });
  it('여러 단어는 모두 포함해야 한다', () => {
    expect(filterCards(cards, '대한 김영희', 'all').map((c) => c.id)).toEqual(['2']);
    expect(filterCards(cards, '한빛 김영희', 'all')).toEqual([]);
  });
});
