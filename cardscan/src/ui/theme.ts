// 디자인 토큰 — "Ink & Gold": 깊은 잉크 네이비 + 골드 포인트 + 회사별 고유 그라데이션.
import { Platform, TextStyle } from 'react-native';
import { CardKind } from '../core/types';

export const T = {
  ink: '#0B1530',
  ink2: '#14214A',
  ink3: '#22305F',
  gold: '#D4AF6A',
  goldDeep: '#B08A45',
  goldSoft: '#F6EEDC',
  bg: '#F3F4F8',
  surface: '#FFFFFF',
  text: '#0E1426',
  sub: '#6B7385',
  faint: '#A3A9B8',
  line: '#E7E9F0',
  primary: '#3B5BFD',
  primarySoft: '#EEF1FF',
  ok: '#16A34A',
  warn: '#E08A00',
  err: '#E5484D',
  errSoft: '#FDECEC',
  kind: { customer: '#3B5BFD', partner: '#8B5CF6', other: '#64748B' } as Record<CardKind, string>,
};

/** Pretendard (앱에 내장, Android 에서는 weight 로 굵기 선택) */
export const FONT = Platform.select({ android: 'Pretendard', default: undefined });

export const type = (size: number, weight: TextStyle['fontWeight'] = '400', color: string = T.text): TextStyle => ({
  fontFamily: FONT,
  fontSize: size,
  fontWeight: weight,
  color,
  // 한글이 답답하지 않도록 살짝 넉넉한 줄간격
  lineHeight: Math.round(size * 1.4),
});

export const shadow = (level: 1 | 2 | 3 = 1) =>
  ({
    1: { shadowColor: '#0B1530', shadowOpacity: 0.06, shadowRadius: 10, shadowOffset: { width: 0, height: 3 }, elevation: 2 },
    2: { shadowColor: '#0B1530', shadowOpacity: 0.12, shadowRadius: 18, shadowOffset: { width: 0, height: 8 }, elevation: 6 },
    3: { shadowColor: '#0B1530', shadowOpacity: 0.28, shadowRadius: 28, shadowOffset: { width: 0, height: 14 }, elevation: 14 },
  })[level];

export const RADIUS = { sm: 10, md: 14, lg: 20, xl: 28 };

/** 회사마다 고정된 고급 그라데이션 — 같은 회사는 늘 같은 색이라 목록에서 한눈에 알아본다 */
export const CARD_GRADIENTS: [string, string][] = [
  ['#0B1530', '#2B3F86'], // 잉크
  ['#1E3A8A', '#3B82F6'], // 사파이어
  ['#3B0764', '#8B5CF6'], // 자수정
  ['#064E3B', '#10B981'], // 에메랄드
  ['#7C2D12', '#F59E0B'], // 앰버
  ['#831843', '#F472B6'], // 로즈
  ['#134E4A', '#2DD4BF'], // 틸
  ['#0F0F14', '#3F3F4A'], // 블랙 메탈
  ['#4C0519', '#E11D48'], // 루비
  ['#172554', '#0EA5E9'], // 오션
];

export function hashString(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function gradientFor(key: string): [string, string] {
  if (!key.trim()) return CARD_GRADIENTS[0];
  return CARD_GRADIENTS[hashString(key.trim()) % CARD_GRADIENTS.length];
}

/** 아바타 글자 — 한글 이름은 성, 영문은 이니셜 두 글자 */
export function monogram(name: string, fallback = ''): string {
  const n = (name || fallback).trim();
  if (!n) return '·';
  if (/^[가-힣]/.test(n)) return n[0];
  const words = n.split(/\s+/).filter(Boolean);
  return ((words[0]?.[0] ?? '') + (words[1]?.[0] ?? '')).toUpperCase() || n[0];
}
