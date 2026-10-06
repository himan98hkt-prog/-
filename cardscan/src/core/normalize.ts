// 명함 데이터 정리 — OCR 결과의 표기 흔들림을 잡아 연락처/CRM 에 같은 모양으로 들어가게 한다.
import { CardFields, EMPTY_FIELDS } from './types';

/** 숫자만 남긴다. +82 국가번호는 국내 표기(0으로 시작)로 바꾼다. */
export function phoneDigits(raw: string): string {
  let d = (raw || '').replace(/[^\d+]/g, '');
  if (d.startsWith('+82')) d = '0' + d.slice(3).replace(/^0/, '');
  // '+' 없이 82 로 시작 — 국내 번호는 0·1 로 시작하므로 뒤가 올바른 국내 번호일 때만 국가번호로 본다
  else if (/^82(0?(2|[3-6][1-5]|1[016789]|70|80|50[2-8])\d{7,8})$/.test(d)) d = '0' + d.slice(2).replace(/^0/, '');
  return d.replace(/\+/g, '');
}

/**
 * 국내 전화번호를 하이픈 표기로 맞춘다.
 * 010-1234-5678 · 02-123-4567 · 031-1234-5678 · 1588-1234 · 0505-123-4567
 * 형식을 알 수 없으면 원문을 그대로 둔다(내선 번호 등 정보 손실 방지).
 */
export function formatKoreanPhone(raw: string): string {
  const src = (raw || '').trim();
  if (!src) return '';
  // 내선(ext, 내선, #)은 떼어 두었다가 뒤에 다시 붙인다
  const extMatch = src.match(/\s*(?:ext\.?|내선|#|\(내\))\s*(\d+)\s*\)?$/i);
  const ext = extMatch ? ` (내선 ${extMatch[1]})` : '';
  const body = extMatch ? src.slice(0, extMatch.index) : src;
  const d = phoneDigits(body);

  let out: string | null = null;
  if (/^01[016789]\d{7,8}$/.test(d)) {
    out = d.length === 10 ? `${d.slice(0, 3)}-${d.slice(3, 6)}-${d.slice(6)}` : `${d.slice(0, 3)}-${d.slice(3, 7)}-${d.slice(7)}`;
  } else if (/^02\d{7,8}$/.test(d)) {
    out = d.length === 9 ? `02-${d.slice(2, 5)}-${d.slice(5)}` : `02-${d.slice(2, 6)}-${d.slice(6)}`;
  } else if (/^050[2-8]\d{7,8}$/.test(d)) {
    out = d.length === 11 ? `${d.slice(0, 4)}-${d.slice(4, 7)}-${d.slice(7)}` : `${d.slice(0, 4)}-${d.slice(4, 8)}-${d.slice(8)}`;
  } else if (/^0[3-7]\d\d{7,8}$/.test(d)) {
    out = d.length === 10 ? `${d.slice(0, 3)}-${d.slice(3, 6)}-${d.slice(6)}` : `${d.slice(0, 3)}-${d.slice(3, 7)}-${d.slice(7)}`;
  } else if (/^1[5-9]\d{6}$/.test(d)) {
    out = `${d.slice(0, 4)}-${d.slice(4)}`;
  }
  return out ? out + ext : src;
}

/** 국제 표기(+82) — HubSpot 등 해외 CRM 은 이 형태를 잘 인식한다. */
export function toE164Korea(raw: string): string {
  const d = phoneDigits(raw);
  if (!/^0\d{8,10}$/.test(d)) return raw.trim();
  return '+82' + d.slice(1);
}

const TWO_CHAR_SURNAMES = ['남궁', '선우', '제갈', '황보', '독고', '사공', '서문', '동방', '어금', '망절', '소봉'];

/** 한국식 이름을 성/이름으로 나눈다. 영문 이름은 마지막 단어를 성으로 본다. */
export function splitName(full: string): { family: string; given: string } {
  const name = (full || '').trim().replace(/\s+/g, ' ');
  if (!name) return { family: '', given: '' };
  if (/^[가-힣]+$/.test(name)) {
    if (name.length >= 4 && TWO_CHAR_SURNAMES.includes(name.slice(0, 2))) {
      return { family: name.slice(0, 2), given: name.slice(2) };
    }
    if (name.length === 1) return { family: name, given: '' };
    return { family: name.slice(0, 1), given: name.slice(1) };
  }
  // "홍 길동" 처럼 띄어 쓴 한글
  if (/^[가-힣]+ [가-힣]+$/.test(name)) {
    const [family, given] = name.split(' ');
    return { family, given };
  }
  const parts = name.split(' ');
  if (parts.length === 1) return { family: '', given: name };
  return { family: parts[parts.length - 1], given: parts.slice(0, -1).join(' ') };
}

export function normalizeEmail(raw: string): string {
  const e = (raw || '').trim().replace(/\s+/g, '').replace(/^mailto:/i, '');
  return e.toLowerCase();
}

export function normalizeWebsite(raw: string): string {
  const w = (raw || '').trim().replace(/\s+/g, '');
  if (!w) return '';
  if (/^https?:\/\//i.test(w)) return w;
  return 'https://' + w.replace(/^\/+/, '');
}

export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/** OCR 서버 응답(신뢰할 수 없는 JSON)을 앱 필드로 정리한다. */
export function sanitizeFields(input: unknown): CardFields {
  const src = (input && typeof input === 'object' ? input : {}) as Record<string, unknown>;
  const str = (k: string) => (typeof src[k] === 'string' ? (src[k] as string).trim() : '');
  const out: CardFields = { ...EMPTY_FIELDS };
  out.name = str('name');
  out.nameEn = str('nameEn') || str('name_en');
  out.company = str('company');
  out.department = str('department');
  out.title = str('title');
  out.mobile = formatKoreanPhone(str('mobile'));
  out.phone = formatKoreanPhone(str('phone'));
  out.fax = formatKoreanPhone(str('fax'));
  out.email = normalizeEmail(str('email'));
  out.website = normalizeWebsite(str('website'));
  out.address = str('address');
  out.memo = str('memo');
  // 휴대폰이 전화 칸에 들어온 경우 바로잡는다
  if (!out.mobile && /^01[016789]-/.test(out.phone)) {
    out.mobile = out.phone;
    out.phone = '';
  }
  return out;
}

/** 자동 저장해도 될 만큼 핵심 정보가 읽혔는지 */
export function isConfidentEnough(f: CardFields): boolean {
  const hasName = f.name.length >= 2;
  const hasReach = phoneDigits(f.mobile).length >= 9 || phoneDigits(f.phone).length >= 9 || isValidEmail(f.email);
  return hasName && hasReach;
}
