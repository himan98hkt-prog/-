// 엑셀(CSV) 내보내기와 백업/복원 — 리멤버는 엑셀 내보내기가 유료지만 여기서는 무료·오프라인.
import { KIND_LABEL, BusinessCard, CardKind } from './types';
import { t } from '../i18n/core';

export const CSV_HEADERS = [
  '구분', '즐겨찾기', '이름', '영문이름', '회사', '부서', '직책', '휴대폰', '전화', '팩스', '이메일', '웹사이트', '주소',
  '그룹', '팔로업', '메모', '미팅기록', '이전 소속', '등록일', '수정일',
] as const;

function cell(v: string): string {
  // 엑셀이 수식으로 실행하지 않게 =, +, -, @ 로 시작하는 글은 앞에 ' 를 붙인다 (CSV 주입 방지)
  let s = v ?? '';
  if (/^[=+\-@]/.test(s)) s = `'${s}`;
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** 전화번호는 엑셀이 숫자로 바꿔 앞의 0 을 지우지 않게 ="010-…" 텍스트 수식으로 */
const phoneCell = (p: string) => (p ? `"=""${p.replace(/"/g, '')}"""` : '');

/** 엑셀에서 바로 열리는 CSV (UTF-8 BOM — 한글 깨짐 방지) */
export function toCsv(cards: BusinessCard[]): string {
  const rows = cards.map((c) =>
    [
      cell(t(KIND_LABEL[c.kind])),
      cell(c.favorite ? '★' : ''),
      cell(c.name), cell(c.nameEn), cell(c.company), cell(c.department), cell(c.title),
      phoneCell(c.mobile), phoneCell(c.phone), phoneCell(c.fax),
      cell(c.email), cell(c.website), cell(c.address),
      cell((c.tags ?? []).join(', ')),
      cell(c.followUp ?? ''),
      cell(c.memo),
      cell((c.notes ?? []).map((n) => `[${n.at.slice(0, 10)}] ${n.text}`).join('\n')),
      cell((c.history ?? []).map((h) => `${[h.company, h.title].filter(Boolean).join(' ')} (~${h.until.slice(0, 10)})`).join('\n')),
      cell(c.createdAt.slice(0, 10)),
      cell(c.updatedAt.slice(0, 10)),
    ].join(','),
  );
  return '\ufeff' + [CSV_HEADERS.map((h) => cell(t(h))).join(','), ...rows].join('\r\n');
}

// ── 백업 ────────────────────────────────────────────────────────────────────

export const BACKUP_APP = 'cardscan';
export const BACKUP_VERSION = 1;

export interface Backup {
  app: typeof BACKUP_APP;
  version: number;
  exportedAt: string;
  cards: BusinessCard[];
}

/** 명함 데이터 백업 (사진·연동 비밀키는 제외 — 파일을 가볍고 안전하게) */
export function makeBackup(cards: BusinessCard[], now: string): Backup {
  return {
    app: BACKUP_APP,
    version: BACKUP_VERSION,
    exportedAt: now,
    cards: cards.map(({ imageUri: _i, backImageUri: _b, ...c }) => ({ ...c, sync: {} })),
  };
}

const KINDS: CardKind[] = ['customer', 'partner', 'other'];
const str = (v: unknown) => (typeof v === 'string' ? v : '');

/** 백업 파일 검증 — 모르는 형식이면 오류 */
export function parseBackup(text: string): BusinessCard[] {
  let data: Partial<Backup>;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error('백업 파일을 읽을 수 없습니다 (JSON 아님)');
  }
  if (data?.app !== BACKUP_APP || !Array.isArray(data.cards)) throw new Error(t('명함스캔 백업 파일이 아닙니다'));
  return data.cards
    .filter((c): c is BusinessCard => !!c && typeof c === 'object' && typeof (c as BusinessCard).id === 'string')
    .map((c) => ({
      ...c,
      kind: KINDS.includes(c.kind) ? c.kind : 'other',
      name: str(c.name), nameEn: str(c.nameEn), company: str(c.company), department: str(c.department), title: str(c.title),
      mobile: str(c.mobile), phone: str(c.phone), fax: str(c.fax), email: str(c.email), website: str(c.website),
      address: str(c.address), memo: str(c.memo),
      createdAt: str(c.createdAt) || new Date(0).toISOString(),
      updatedAt: str(c.updatedAt) || str(c.createdAt) || new Date(0).toISOString(),
      extra: Array.isArray(c.extra) ? c.extra.filter((x) => typeof x === 'string') : [],
      sync: {},
    }));
}

/** 복원: 없는 명함은 추가, 같은 id 는 더 최근에 수정된 쪽을 남긴다 (사진은 기기에 있던 것 유지) */
export function mergeBackup(current: BusinessCard[], incoming: BusinessCard[]): { cards: BusinessCard[]; added: number; updated: number } {
  const byId = new Map(current.map((c) => [c.id, c]));
  let added = 0;
  let updated = 0;
  for (const c of incoming) {
    const mine = byId.get(c.id);
    if (!mine) {
      byId.set(c.id, c);
      added++;
    } else if (c.updatedAt > mine.updatedAt) {
      byId.set(c.id, { ...c, imageUri: mine.imageUri, backImageUri: mine.backImageUri, sync: mine.sync });
      updated++;
    }
  }
  return { cards: [...byId.values()], added, updated };
}
