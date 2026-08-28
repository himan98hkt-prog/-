import { durationKo, startOfDay, startOfNextDay } from './date';
import type { Subscription } from './types';

/** 수익 모델: 무료는 하루 3회, 프로는 무제한 */
export const FREE_DAILY_LIMIT = 3;
export const PRO_PRICE_KRW = 3900;

export interface QuotaState {
  isPro: boolean;
  /** 오늘 사용한 횟수 */
  used: number;
  /** 무료 한도. 프로는 null(무제한) */
  limit: number | null;
  /** 남은 횟수. 프로는 null */
  remaining: number | null;
  canAnalyze: boolean;
  /** 무료 횟수가 초기화되는 시각 */
  resetsAt: number;
  /** 화면에 그대로 뿌리는 안내 문구 */
  label: string;
}

export function isProActive(sub: Subscription | undefined, now = Date.now()): boolean {
  if (!sub?.pro) return false;
  if (sub.expiresAt == null) return true;
  return sub.expiresAt > now;
}

/**
 * 오늘 남은 분석 횟수를 계산한다.
 * `timestamps` 는 분석 히스토리의 createdAt 목록 (정렬 여부 무관).
 */
export function quotaState(timestamps: number[], sub: Subscription | undefined, now = Date.now()): QuotaState {
  const pro = isProActive(sub, now);
  const todayStart = startOfDay(now);
  const resetsAt = startOfNextDay(now);
  const used = timestamps.filter((ts) => ts >= todayStart && ts <= now).length;

  if (pro) {
    return {
      isPro: true,
      used,
      limit: null,
      remaining: null,
      canAnalyze: true,
      resetsAt,
      label: `프로 · 무제한 분석 (오늘 ${used}회)`,
    };
  }

  const remaining = Math.max(0, FREE_DAILY_LIMIT - used);
  return {
    isPro: false,
    used,
    limit: FREE_DAILY_LIMIT,
    remaining,
    canAnalyze: remaining > 0,
    resetsAt,
    label:
      remaining > 0
        ? `오늘 무료 분석 ${remaining}/${FREE_DAILY_LIMIT}회 남음`
        : `오늘 무료 분석을 모두 썼어요 · ${durationKo(resetsAt - now)} 뒤 초기화`,
  };
}

/** 프로 전용 기능 목록 — 페이월 화면과 잠금 뱃지가 같은 소스를 쓰도록 */
export const PRO_FEATURES = [
  { key: 'unlimited', title: '무제한 분석', desc: '하루 3회 제한 없이 언제든 분석해요.' },
  { key: 'weekly', title: '주간 행동 리포트', desc: '일주일 감정 변화와 다음 주 실천 과제를 정리해 드려요.' },
  { key: 'themes', title: '캐릭터 말풍선 테마', desc: '인스타용 포토카드 테마 전부 잠금 해제.' },
  { key: 'multipet', title: '반려동물 무제한 등록', desc: '무료는 1마리, 프로는 여러 마리를 각각 기록해요.' },
] as const;

/** 무료 사용자가 등록할 수 있는 반려동물 수 */
export const FREE_PET_LIMIT = 1;

export function canAddPet(petCount: number, sub: Subscription | undefined, now = Date.now()): boolean {
  return isProActive(sub, now) || petCount < FREE_PET_LIMIT;
}
