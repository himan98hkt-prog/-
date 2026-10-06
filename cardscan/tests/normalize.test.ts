import { describe, expect, it } from 'vitest';
import { formatKoreanPhone, isConfidentEnough, normalizeWebsite, phoneDigits, sanitizeFields, splitName, toE164Korea } from '../src/core/normalize';

describe('formatKoreanPhone', () => {
  it.each([
    ['01012345678', '010-1234-5678'],
    ['010 1234 5678', '010-1234-5678'],
    ['010.1234.5678', '010-1234-5678'],
    ['+82 10-1234-5678', '010-1234-5678'],
    ['+82 (0)10 1234 5678', '010-1234-5678'],
    ['0111234567', '011-123-4567'],
    ['0212345678', '02-1234-5678'],
    ['021234567', '02-123-4567'],
    ['+82-2-1234-5678', '02-1234-5678'],
    ['82 10 1234 5678', '010-1234-5678'],
    ['82-10-1234-5678', '010-1234-5678'],
    ['82-2-123-4567', '02-123-4567'],
    ['82 31 765 4321', '031-765-4321'],
    ['0311234567', '031-123-4567'],
    ['03112345678', '031-1234-5678'],
    ['07012345678', '070-1234-5678'],
    ['15881234', '1588-1234'],
    ['05051234567', '0505-123-4567'],
    ['02-1234-5678 ext. 205', '02-1234-5678 (내선 205)'],
    ['02-1234-5678 (내선 7)', '02-1234-5678 (내선 7)'],
  ])('%s → %s', (raw, expected) => {
    expect(formatKoreanPhone(raw)).toBe(expected);
  });

  it('알 수 없는 형식(해외 번호)은 원문 유지', () => {
    expect(formatKoreanPhone('+1 415 555 0100')).toBe('+1 415 555 0100');
    expect(formatKoreanPhone('')).toBe('');
  });
});

describe('phone helpers', () => {
  it('phoneDigits 는 +82 를 0 으로 바꾼다', () => {
    expect(phoneDigits('+82 10-1234-5678')).toBe('01012345678');
  });
  it('toE164Korea', () => {
    expect(toE164Korea('010-1234-5678')).toBe('+821012345678');
    expect(toE164Korea('02-123-4567')).toBe('+8221234567');
  });
});

describe('splitName', () => {
  it.each([
    ['홍길동', '홍', '길동'],
    ['남궁민수', '남궁', '민수'],
    ['선우은숙', '선우', '은숙'],
    ['남궁', '남', '궁'], // 두 글자면 외자 이름으로 본다
    ['이 순신', '이', '순신'],
    ['Gildong Hong', 'Hong', 'Gildong'],
    ['Mary Jane Watson', 'Watson', 'Mary Jane'],
    ['Cher', '', 'Cher'],
    ['', '', ''],
  ])('%s', (full, family, given) => {
    expect(splitName(full)).toEqual({ family, given });
  });
});

describe('sanitizeFields', () => {
  it('신뢰할 수 없는 응답을 정리한다', () => {
    const f = sanitizeFields({
      name: ' 김철수 ',
      name_en: 'Chulsoo Kim',
      company: '(주)테스트',
      mobile: '010 9876 5432',
      phone: 123, // 문자열이 아니면 버린다
      email: ' Kim@Test.CO.KR ',
      website: 'www.test.co.kr',
      evil: '<script>',
    });
    expect(f.name).toBe('김철수');
    expect(f.nameEn).toBe('Chulsoo Kim');
    expect(f.mobile).toBe('010-9876-5432');
    expect(f.phone).toBe('');
    expect(f.email).toBe('kim@test.co.kr');
    expect(f.website).toBe('https://www.test.co.kr');
    expect(f).not.toHaveProperty('evil');
  });

  it('전화 칸에 들어온 휴대폰 번호를 휴대폰 칸으로 옮긴다', () => {
    const f = sanitizeFields({ name: '박', phone: '01011112222' });
    expect(f.mobile).toBe('010-1111-2222');
    expect(f.phone).toBe('');
  });

  it('객체가 아니면 빈 필드', () => {
    expect(sanitizeFields(null).name).toBe('');
    expect(sanitizeFields('x').email).toBe('');
  });
});

describe('isConfidentEnough', () => {
  const base = sanitizeFields({});
  it('이름 + 연락 수단이 있어야 자동 저장', () => {
    expect(isConfidentEnough({ ...base, name: '홍길동', mobile: '010-1234-5678' })).toBe(true);
    expect(isConfidentEnough({ ...base, name: '홍길동', email: 'a@b.co' })).toBe(true);
    expect(isConfidentEnough({ ...base, name: '홍길동' })).toBe(false);
    expect(isConfidentEnough({ ...base, mobile: '010-1234-5678' })).toBe(false);
    expect(isConfidentEnough({ ...base, name: '홍길동', email: 'not-an-email' })).toBe(false);
  });
});

describe('normalizeWebsite', () => {
  it('스킴을 붙이고 기존 스킴은 유지', () => {
    expect(normalizeWebsite('example.com')).toBe('https://example.com');
    expect(normalizeWebsite('http://example.com')).toBe('http://example.com');
    expect(normalizeWebsite('')).toBe('');
  });
});
