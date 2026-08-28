import { startOfDay, startOfNextDay } from './date';
import { msg, type Message } from './message';
import type { Subscription } from './types';

/** 수익 모델: 무료는 하루 3회, 프로는 무제한 */
export const FREE_DAILY_LIMIT = 3;
/** 스토어에서 가격을 못 받아왔을 때 보여 줄 기본값 */
export const PRO_PRICE_KRW = 3900;
export const PRO_YEARLY_PRICE_KRW = 29000;

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
  /** 화면에 뿌릴 안내 문구의 번역 참조 */
  label: Message;
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
      label: msg('quota.proUnlimited', { used }),
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
        ? msg('quota.freeRemaining', { remaining, limit: FREE_DAILY_LIMIT })
        : msg('quota.freeExhausted', { resetsAt }),
  };
}

/** 프로 전용 기능 목록 — 페이월 화면과 잠금 뱃지가 같은 소스를 쓰도록 */
export const PRO_FEATURES = ['unlimited', 'weekly', 'themes', 'multipet', 'backup', 'precise'] as const;
export type ProFeature = (typeof PRO_FEATURES)[number];

/** 무료 사용자가 등록할 수 있는 반려동물 수 */
export const FREE_PET_LIMIT = 1;

export function canAddPet(petCount: number, sub: Subscription | undefined, now = Date.now()): boolean {
  return isProActive(sub, now) || petCount < FREE_PET_LIMIT;
}
