// 명함첩 정리 — 초성 검색, 정렬, 그룹·즐겨찾기 필터, 회사별 묶기, 팔로업, 재촬영 병합(경력 이력).
// 화면과 저장소에 의존하지 않는 순수 함수만 둔다.
import { phoneDigits } from './normalize';
import { BusinessCard, CardFields, CardKind, CareerEntry } from './types';

// ── 초성 검색 ────────────────────────────────────────────────────────────────

const CHOSUNG = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ';

/** "홍길동" → "ㅎㄱㄷ" (한글 외 문자는 그대로) */
export function toChosung(s: string): string {
  let out = '';
  for (const ch of s) {
    const code = ch.charCodeAt(0) - 0xac00;
    out += code >= 0 && code < 11172 ? CHOSUNG[Math.floor(code / 588)] : ch;
  }
  return out;
}

const isChosungQuery = (q: string) => /^[ㄱ-ㅎ\s]+$/.test(q);

function searchableText(c: BusinessCard): string {
  return [
    c.name, c.nameEn, c.company, c.department, c.title, c.email, c.memo, c.address, c.website,
    ...(c.tags ?? []), ...(c.notes ?? []).map((n) => n.text), ...(c.history ?? []).map((h) => `${h.company} ${h.title}`),
  ]
    .join(' ')
    .toLowerCase();
}

/** 이름·회사·부서·직책·이메일·메모·그룹·미팅기록·이전 회사, 번호 일부, 초성(ㅎㄱㄷ) 검색 */
export function matchesQuery(card: BusinessCard, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const digits = q.replace(/\D/g, '');
  if (digits.length >= 3 && /^[\d\s+-]+$/.test(q)) {
    return [card.mobile, card.phone, card.fax].some((p) => phoneDigits(p).includes(digits) || p.replace(/\D/g, '').includes(digits));
  }
  if (isChosungQuery(q)) {
    const target = toChosung([card.name, card.company, card.department, card.title].join(' ')).replace(/\s/g, '');
    return target.includes(q.replace(/\s/g, ''));
  }
  const hay = searchableText(card);
  return q.split(/\s+/).every((t) => hay.includes(t));
}

// ── 정렬·필터 ────────────────────────────────────────────────────────────────

export type SortKey = 'recent' | 'name' | 'company' | 'updated';

export const SORT_LABEL: Record<SortKey, string> = {
  recent: '최근 등록순',
  updated: '최근 수정순',
  name: '이름순',
  company: '회사순',
};

const ko = (a: string, b: string) => a.localeCompare(b, 'ko');

export function sortCards(cards: BusinessCard[], key: SortKey): BusinessCard[] {
  const list = [...cards];
  switch (key) {
    case 'name':
      return list.sort((a, b) => ko(a.name || a.nameEn || '힣', b.name || b.nameEn || '힣'));
    case 'company':
      // (주)·주식회사 같은 법인 표기는 빼고 비교 — '(주)한빛상사' 와 '한빛상사' 가 나란히
      return list.sort((a, b) => ko(companyKey(a.company) || '힣', companyKey(b.company) || '힣') || ko(a.name, b.name));
    case 'updated':
      return list.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    default:
      return list.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  }
}

export interface CardFilter {
  query?: string;
  kind?: CardKind | 'all';
  favoritesOnly?: boolean;
  tag?: string | null;
  sort?: SortKey;
}

export function filterCards(cards: BusinessCard[], f: CardFilter): BusinessCard[] {
  const filtered = cards.filter(
    (c) =>
      (!f.kind || f.kind === 'all' || c.kind === f.kind) &&
      (!f.favoritesOnly || c.favorite) &&
      (!f.tag || (c.tags ?? []).includes(f.tag)) &&
      matchesQuery(c, f.query ?? ''),
  );
  // 즐겨찾기는 항상 위로
  return sortCards(filtered, f.sort ?? 'recent').sort((a, b) => Number(!!b.favorite) - Number(!!a.favorite));
}

/** 쓰이고 있는 그룹 이름과 개수 (많은 순) */
export function allTags(cards: BusinessCard[]): { tag: string; count: number }[] {
  const m = new Map<string, number>();
  for (const c of cards) for (const t of c.tags ?? []) m.set(t, (m.get(t) ?? 0) + 1);
  return [...m.entries()].map(([tag, count]) => ({ tag, count })).sort((a, b) => b.count - a.count || ko(a.tag, b.tag));
}

export function normalizeTag(t: string): string {
  return t.replace(/^#/, '').replace(/\s+/g, ' ').trim().slice(0, 20);
}

// ── 회사별 ──────────────────────────────────────────────────────────────────

/** "(주)한빛상사", "주식회사 한빛상사", "한빛상사 Co., Ltd." 를 같은 회사로 */
export function companyKey(company: string): string {
  return company
    .toLowerCase()
    .replace(/\(주\)|㈜|주식회사|\(유\)|유한회사|co\.,?\s*ltd\.?|inc\.?|corp\.?|ltd\.?|llc/g, '')
    .replace(/[\s.,()·-]/g, '');
}

export function groupByCompany(cards: BusinessCard[]): { company: string; cards: BusinessCard[] }[] {
  const m = new Map<string, { company: string; cards: BusinessCard[] }>();
  for (const c of cards) {
    const key = companyKey(c.company) || '(회사 없음)';
    const g = m.get(key) ?? { company: c.company || '(회사 없음)', cards: [] };
    g.cards.push(c);
    m.set(key, g);
  }
  return [...m.values()].sort((a, b) => b.cards.length - a.cards.length || ko(a.company, b.company));
}

/** 같은 회사 사람들 (본인 제외) */
export function colleaguesOf(card: BusinessCard, cards: BusinessCard[]): BusinessCard[] {
  const key = companyKey(card.company);
  if (!key) return [];
  return cards.filter((c) => c.id !== card.id && companyKey(c.company) === key);
}

// ── 팔로업 ──────────────────────────────────────────────────────────────────

export const todayStr = (now = new Date()) =>
  `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

export function addDays(date: string, days: number): string {
  const [y, m, d] = date.split('-').map(Number);
  return todayStr(new Date(y, m - 1, d + days));
}

/** 오늘까지(지난 것 포함) 연락해야 할 명함 — 날짜 이른 순 */
export function dueFollowUps(cards: BusinessCard[], today: string): BusinessCard[] {
  return cards.filter((c) => c.followUp && c.followUp <= today).sort((a, b) => (a.followUp ?? '').localeCompare(b.followUp ?? ''));
}

export function upcomingFollowUps(cards: BusinessCard[], today: string, days = 7): BusinessCard[] {
  const until = addDays(today, days);
  return cards
    .filter((c) => c.followUp && c.followUp > today && c.followUp <= until)
    .sort((a, b) => (a.followUp ?? '').localeCompare(b.followUp ?? ''));
}

// ── 재촬영 병합 ──────────────────────────────────────────────────────────────

const sameOrg = (a: Pick<CardFields, 'company' | 'title'>, b: Pick<CardFields, 'company' | 'title'>) =>
  companyKey(a.company) === companyKey(b.company) && a.title.replace(/\s/g, '') === b.title.replace(/\s/g, '');

/**
 * 같은 사람의 새 명함으로 기존 명함을 갱신한다.
 * - 이번에 읽힌 칸은 새 값으로, 못 읽은 칸은 기존 값 유지
 * - 회사나 직책이 바뀌었으면 이전 소속을 경력 이력에 남기고 메모에 기록 (이직·승진 추적)
 */
export function mergeRescan(
  existing: BusinessCard,
  fields: CardFields,
  now: string,
  newId: () => string,
): { card: BusinessCard; changed: CareerEntry | null } {
  const merged = { ...existing } as BusinessCard;
  for (const k of Object.keys(fields) as (keyof CardFields)[]) if (fields[k] && k !== 'memo') merged[k] = fields[k];
  if (fields.memo) merged.memo = existing.memo ? `${existing.memo}\n${fields.memo}` : fields.memo;

  let changed: CareerEntry | null = null;
  const orgRead = !!(fields.company || fields.title);
  if (orgRead && (existing.company || existing.title) && !sameOrg(existing, merged)) {
    changed = { company: existing.company, department: existing.department, title: existing.title, until: now };
    merged.history = [changed, ...(existing.history ?? [])];
    const from = [existing.company, existing.title].filter(Boolean).join(' ');
    const to = [merged.company, merged.title].filter(Boolean).join(' ');
    merged.notes = [{ id: newId(), at: now, text: `소속 변경: ${from} → ${to}` }, ...(existing.notes ?? [])];
  }
  merged.updatedAt = now;
  return { card: merged, changed };
}

// ── 통계 ────────────────────────────────────────────────────────────────────

export function stats(cards: BusinessCard[], today: string) {
  const month = today.slice(0, 7);
  return {
    total: cards.length,
    thisMonth: cards.filter((c) => c.createdAt.slice(0, 7) === month).length,
    favorites: cards.filter((c) => c.favorite).length,
    companies: new Set(cards.map((c) => companyKey(c.company)).filter(Boolean)).size,
    dueFollowUps: dueFollowUps(cards, today).length,
  };
}
