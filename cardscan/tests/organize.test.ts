import { describe, expect, it } from 'vitest';
import { makeBackup, mergeBackup, parseBackup, toCsv } from '../src/core/exportData';
import { contactNameSuffix, toDeviceContact } from '../src/core/mapping';
import {
  addDays, allTags, colleaguesOf, companyKey, dueFollowUps, filterCards, groupByCompany, matchesQuery, mergeRescan, sortCards, stats,
  toChosung, upcomingFollowUps,
} from '../src/core/organize';
import { darkRuns, qrMatrix, utf8ByteString } from '../src/core/qr';
import { EMPTY_FIELDS } from '../src/core/types';
import { makeCard } from './fixtures';

describe('초성 검색', () => {
  it('toChosung', () => {
    expect(toChosung('홍길동')).toBe('ㅎㄱㄷ');
    expect(toChosung('한빛상사 A1')).toBe('ㅎㅂㅅㅅ A1');
  });
  it('이름·회사 초성으로 찾는다', () => {
    const c = makeCard();
    expect(matchesQuery(c, 'ㅎㄱㄷ')).toBe(true);
    expect(matchesQuery(c, 'ㅎㅂㅅㅅ')).toBe(true);
    expect(matchesQuery(c, 'ㄱㄷ')).toBe(true);
    expect(matchesQuery(c, 'ㅋㅋ')).toBe(false);
  });
  it('그룹·메모·이전 회사로도 찾는다', () => {
    const c = makeCard({
      tags: ['2026 전시회'],
      notes: [{ id: 'n', at: '2026-10-01T00:00:00Z', text: '골프 좋아함' }],
      history: [{ company: '대한물산', department: '', title: '과장', until: '2026-01-01' }],
    });
    expect(matchesQuery(c, '전시회')).toBe(true);
    expect(matchesQuery(c, '골프')).toBe(true);
    expect(matchesQuery(c, '대한물산')).toBe(true);
  });
});

describe('정렬·필터', () => {
  const cards = [
    makeCard({ id: '1', name: '홍길동', company: '(주)한빛상사', createdAt: '2026-01-01', updatedAt: '2026-03-01' }),
    makeCard({ id: '2', name: '김영희', company: '대한물산', kind: 'partner', createdAt: '2026-02-01', updatedAt: '2026-02-01', favorite: true, tags: ['VIP'] }),
    makeCard({ id: '3', name: '박민수', company: '한빛상사', createdAt: '2026-03-01', updatedAt: '2026-01-01', tags: ['VIP', '전시회'] }),
  ];
  it('이름순·회사순·수정순', () => {
    expect(sortCards(cards, 'name').map((c) => c.id)).toEqual(['2', '3', '1']);
    expect(sortCards(cards, 'company').map((c) => c.id)).toEqual(['2', '3', '1']); // 대한물산, 한빛상사(박민수·홍길동)
    expect(sortCards(cards, 'updated').map((c) => c.id)).toEqual(['1', '2', '3']);
  });
  it('즐겨찾기는 항상 위, 그룹·즐겨찾기 필터', () => {
    expect(filterCards(cards, {}).map((c) => c.id)).toEqual(['2', '3', '1']);
    expect(filterCards(cards, { favoritesOnly: true }).map((c) => c.id)).toEqual(['2']);
    expect(filterCards(cards, { tag: '전시회' }).map((c) => c.id)).toEqual(['3']);
  });
  it('그룹 목록은 많이 쓰인 순', () => {
    expect(allTags(cards)).toEqual([{ tag: 'VIP', count: 2 }, { tag: '전시회', count: 1 }]);
  });
  it('(주) 표기가 달라도 같은 회사로 묶고 동료를 찾는다', () => {
    expect(companyKey('(주)한빛상사')).toBe(companyKey('한빛상사'));
    expect(companyKey('주식회사 한빛상사')).toBe(companyKey('한빛상사 Co., Ltd.'));
    const groups = groupByCompany(cards);
    expect(groups[0].cards.map((c) => c.id).sort()).toEqual(['1', '3']);
    expect(colleaguesOf(cards[0], cards).map((c) => c.id)).toEqual(['3']);
  });
});

describe('팔로업', () => {
  it('addDays 는 달·해를 넘긴다', () => {
    expect(addDays('2026-10-30', 3)).toBe('2026-11-02');
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01');
  });
  it('오늘까지(지난 것 포함)와 다가오는 7일', () => {
    const cards = [
      makeCard({ id: 'a', followUp: '2026-10-01' }),
      makeCard({ id: 'b', followUp: '2026-10-06' }),
      makeCard({ id: 'c', followUp: '2026-10-09' }),
      makeCard({ id: 'd', followUp: '2026-11-30' }),
      makeCard({ id: 'e' }),
    ];
    expect(dueFollowUps(cards, '2026-10-06').map((c) => c.id)).toEqual(['a', 'b']);
    expect(upcomingFollowUps(cards, '2026-10-06').map((c) => c.id)).toEqual(['c']);
    expect(stats(cards, '2026-10-06').dueFollowUps).toBe(2);
  });
});

describe('재촬영 병합 — 경력 이력', () => {
  let n = 0;
  const id = () => `note-${++n}`;

  it('이직하면 이전 소속을 이력·메모에 남긴다', () => {
    const old = makeCard({ company: '(주)한빛상사', title: '과장', department: '영업1팀' });
    const { card, changed } = mergeRescan(old, { ...EMPTY_FIELDS, name: '홍길동', company: '대한물산', title: '부장', mobile: '010-1234-5678' }, '2026-10-06T00:00:00Z', id);
    expect(changed).toEqual({ company: '(주)한빛상사', department: '영업1팀', title: '과장', until: '2026-10-06T00:00:00Z' });
    expect(card.company).toBe('대한물산');
    expect(card.title).toBe('부장');
    expect(card.department).toBe('영업1팀'); // 이번에 못 읽은 칸은 유지
    expect(card.history).toHaveLength(1);
    expect(card.notes?.[0].text).toBe('소속 변경: (주)한빛상사 과장 → 대한물산 부장');
  });

  it('(주) 표기만 다르면 같은 소속 — 이력을 만들지 않는다', () => {
    const old = makeCard({ company: '(주)한빛상사', title: '팀장' });
    const { changed, card } = mergeRescan(old, { ...EMPTY_FIELDS, company: '한빛상사', title: '팀장' }, 'now', id);
    expect(changed).toBeNull();
    expect(card.history).toBeUndefined();
  });

  it('회사·직책을 못 읽은 재촬영은 이력을 만들지 않는다', () => {
    const { changed } = mergeRescan(makeCard(), { ...EMPTY_FIELDS, mobile: '010-1234-5678' }, 'now', id);
    expect(changed).toBeNull();
  });

  it('메모는 덮지 않고 이어 붙인다', () => {
    const { card } = mergeRescan(makeCard({ memo: '첫 미팅' }), { ...EMPTY_FIELDS, memo: '전시회에서 재회' }, 'now', id);
    expect(card.memo).toBe('첫 미팅\n전시회에서 재회');
  });
});

describe('엑셀(CSV)', () => {
  it('BOM·헤더·번호 앞 0 보존·쉼표/줄바꿈 따옴표', () => {
    const csv = toCsv([makeCard({ memo: '점심, 미팅\n다음주', tags: ['VIP'], favorite: true })]);
    expect(csv.startsWith('﻿구분,즐겨찾기,이름')).toBe(true);
    expect(csv).toContain('"=""010-1234-5678"""');
    expect(csv).toContain('"점심, 미팅\n다음주"');
    expect(csv).toContain(',★,');
  });
  it('수식으로 실행될 수 있는 값은 막는다 (CSV 주입)', () => {
    const csv = toCsv([makeCard({ company: '=HYPERLINK("http://evil")', name: '+cmd' })]);
    expect(csv).toContain(`"'=HYPERLINK(""http://evil"")"`);
    expect(csv).toContain(`'+cmd`);
  });
});

describe('백업·복원', () => {
  it('사진·연동 상태는 빼고, 다시 읽으면 같은 명함', () => {
    const cards = [makeCard({ imageUri: 'file:///x.jpg', tags: ['VIP'], followUp: '2026-11-01', sync: { contacts: { state: 'ok', at: 'x' } } })];
    const text = JSON.stringify(makeBackup(cards, '2026-10-06T00:00:00Z'));
    expect(text).not.toContain('x.jpg');
    const back = parseBackup(text);
    expect(back[0]).toMatchObject({ id: 'c1', name: '홍길동', tags: ['VIP'], followUp: '2026-11-01', sync: {} });
  });
  it('형식이 다른 파일은 거부', () => {
    expect(() => parseBackup('not json')).toThrow('JSON');
    expect(() => parseBackup('{"app":"other","cards":[]}')).toThrow('백업 파일이 아닙니다');
  });
  it('없는 명함은 추가, 같은 명함은 더 최근 것으로 (내 사진 유지)', () => {
    const mine = [makeCard({ id: 'a', updatedAt: '2026-01-01', imageUri: 'file:///a.jpg', name: '옛이름' }), makeCard({ id: 'b', updatedAt: '2026-05-01' })];
    const incoming = [makeCard({ id: 'a', updatedAt: '2026-02-01', name: '새이름' }), makeCard({ id: 'b', updatedAt: '2026-04-01', name: '더오래됨' }), makeCard({ id: 'c' })];
    const r = mergeBackup(mine, incoming);
    expect(r.added).toBe(1);
    expect(r.updated).toBe(1);
    const a = r.cards.find((c) => c.id === 'a')!;
    expect(a.name).toBe('새이름');
    expect(a.imageUri).toBe('file:///a.jpg');
    expect(r.cards.find((c) => c.id === 'b')!.name).toBe('홍길동');
  });
});

describe('전화 올 때 회사명 — 연락처 이름', () => {
  it('이름 뒤에 (회사) 또는 (회사 직책), 법인 표기는 뺀다', () => {
    const c = makeCard({ company: '(주)한빛상사', title: '팀장' });
    expect(contactNameSuffix(c, 'name')).toBe('');
    expect(contactNameSuffix(c, 'company')).toBe(' (한빛상사)');
    expect(contactNameSuffix(c, 'companyTitle')).toBe(' (한빛상사 팀장)');
    expect(toDeviceContact(c, 'company')).toMatchObject({ familyName: '홍', givenName: '길동 (한빛상사)' });
    expect(toDeviceContact(c)).toMatchObject({ givenName: '길동' });
  });
  it('회사가 없으면 붙이지 않는다', () => {
    expect(contactNameSuffix(makeCard({ company: '', title: '' }), 'companyTitle')).toBe('');
  });
});

describe('QR', () => {
  it('한글 vCard 도 QR 행렬로 만든다', () => {
    const m = qrMatrix('BEGIN:VCARD\r\nVERSION:3.0\r\nFN:홍길동\r\nTEL:010-1234-5678\r\nEND:VCARD');
    expect(m.length).toBeGreaterThanOrEqual(21);
    expect(m.every((row) => row.length === m.length)).toBe(true);
    // 세 모서리의 위치 찾기 패턴(7x7 테두리)이 검은 칸
    expect(m[0][0] && m[0][6] && m[6][0] && m[0][m.length - 1] && m[m.length - 1][0]).toBe(true);
  });
  it('UTF-8 바이트 변환 (TextEncoder 와 같은 결과)', () => {
    const s = 'A홍😀';
    const bytes = [...utf8ByteString(s)].map((c) => c.charCodeAt(0));
    expect(bytes).toEqual([...new TextEncoder().encode(s)]);
  });
  it('darkRuns 는 연속 검은 칸을 묶는다', () => {
    expect(darkRuns([true, true, false, true, false, false, true, true, true])).toEqual([[0, 2], [3, 1], [6, 3]]);
  });
});
