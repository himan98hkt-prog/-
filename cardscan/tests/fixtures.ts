import { BusinessCard } from '../src/core/types';

export function makeCard(over: Partial<BusinessCard> = {}): BusinessCard {
  return {
    id: 'c1',
    kind: 'customer',
    name: '홍길동',
    nameEn: 'Gildong Hong',
    company: '(주)한빛상사',
    department: '영업1팀',
    title: '팀장',
    mobile: '010-1234-5678',
    phone: '02-123-4567',
    fax: '02-123-4568',
    email: 'gd.hong@hanbit.co.kr',
    website: 'https://hanbit.co.kr',
    address: '서울특별시 중구 세종대로 110',
    memo: '',
    extra: [],
    createdAt: '2026-10-06T01:00:00.000Z',
    updatedAt: '2026-10-06T01:00:00.000Z',
    sync: {},
    ...over,
  };
}
