import { splitDuration, type RelativeTime } from '../core/date';
import { isRaw, type Message } from '../core/message';
import type { Locale } from '../core/types';
import { en } from './en';
import { ja } from './ja';
import { ko, type TranslationKey } from './ko';

export type { TranslationKey };

export const LOCALES: { key: Locale; label: string }[] = [
  { key: 'ko', label: '한국어' },
  { key: 'en', label: 'English' },
  { key: 'ja', label: '日本語' },
];

const DICTS: Record<Locale, Record<string, string>> = { ko, en, ja };

export const DEFAULT_LOCALE: Locale = 'ko';

export function isLocale(value: unknown): value is Locale {
  return value === 'ko' || value === 'en' || value === 'ja';
}

/** 기기 언어에서 지원 언어를 고른다. 못 고르면 한국어. */
export function pickLocale(tags: readonly string[]): Locale {
  for (const tag of tags) {
    const base = tag.toLowerCase().split('-')[0];
    if (isLocale(base)) return base;
  }
  return DEFAULT_LOCALE;
}

export type Params = Record<string, string | number>;

/**
 * 문자열 하나를 번역한다.
 *
 * 파라미터에 두 가지 약속이 있다.
 * - 값이 `@` 로 시작하면 그 자체가 번역 키다 (예: 감정 이름을 문장에 끼워 넣을 때)
 * - 이름이 `until` 이면 날짜로, `resetsAt` 이면 지금부터 남은 시간으로 포맷한다
 */
export function translate(locale: Locale, key: string, params?: Params): string {
  const dict = DICTS[locale] ?? DICTS[DEFAULT_LOCALE];
  const template = dict[key] ?? DICTS[DEFAULT_LOCALE][key];
  if (template == null) return key; // 키를 그대로 노출해서 빠진 번역이 눈에 띄게 한다
  if (!params) return template;

  return template.replace(/\{(\w+)\}/g, (whole, name: string) => {
    if (!(name in params)) return whole;
    const value = params[name];

    if (typeof value === 'string' && value.startsWith('@')) {
      return translate(locale, value.slice(1));
    }
    if (name === 'until' && typeof value === 'number') return formatDate(value, locale);
    if (name === 'resetsAt' && typeof value === 'number') return formatDuration(value - Date.now(), locale);
    if (name === 'when' && typeof value === 'number') return formatDateTime(value, locale);
    return String(value);
  });
}

/** 코어가 돌려준 Message 를 문장으로. 모델이 쓴 문장(raw)은 그대로 통과시킨다. */
export function formatMessage(locale: Locale, message: Message): string {
  return isRaw(message) ? message.text : translate(locale, message.key, message.params);
}

const INTL_TAG: Record<Locale, string> = { ko: 'ko-KR', en: 'en-US', ja: 'ja-JP' };

function intlFormat(ts: number, locale: Locale, options: Intl.DateTimeFormatOptions): string | null {
  try {
    return new Intl.DateTimeFormat(INTL_TAG[locale], options).format(new Date(ts));
  } catch {
    return null; // Intl 이 축소된 런타임 대비
  }
}

export function formatDate(ts: number, locale: Locale): string {
  const formatted = intlFormat(ts, locale, { year: 'numeric', month: 'long', day: 'numeric' });
  if (formatted) return formatted;
  const d = new Date(ts);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function formatDateTime(ts: number, locale: Locale): string {
  const formatted = intlFormat(ts, locale, {
    month: 'long',
    day: 'numeric',
    weekday: 'short',
    hour: 'numeric',
    minute: '2-digit',
  });
  return formatted ?? formatDate(ts, locale);
}

/** 상대 시각 구조체를 문장으로 */
export function formatRelative(rel: RelativeTime, locale: Locale): string {
  switch (rel.kind) {
    case 'justNow':
      return translate(locale, 'time.justNow');
    case 'minutes':
      return translate(locale, 'time.minutesAgo', { value: rel.value });
    case 'hours':
      return translate(locale, 'time.hoursAgo', { value: rel.value });
    case 'yesterday':
      return translate(locale, 'time.yesterday');
    case 'days':
      return translate(locale, 'time.daysAgo', { value: rel.value });
    case 'date':
      return formatDate(rel.ts, locale);
  }
}

export function formatDuration(ms: number, locale: Locale): string {
  if (ms <= 0) return translate(locale, 'duration.soon');
  const { hours, minutes } = splitDuration(ms);
  if (hours === 0) return translate(locale, 'duration.minutes', { minutes });
  if (minutes === 0) return translate(locale, 'duration.hours', { hours });
  return translate(locale, 'duration.hoursMinutes', { hours, minutes });
}

/** 감정·상황처럼 "키 하나 → 라벨" 이 필요한 곳에서 쓰는 얇은 헬퍼 */
export function labelOf(locale: Locale, key: string): string {
  return translate(locale, key);
}
