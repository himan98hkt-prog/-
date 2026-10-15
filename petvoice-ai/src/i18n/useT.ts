import { useCallback, useMemo } from 'react';
import type { Message } from '../core/message';
import type { RelativeTime } from '../core/date';
import type { Locale } from '../core/types';
import { usePetStore } from '../store/usePetStore';
import {
  formatDate,
  formatDateTime,
  formatDuration,
  formatMessage,
  formatRelative,
  translate,
  type Params,
} from './index';

export interface Translator {
  locale: Locale;
  /** 키로 번역 */
  t: (key: string, params?: Params) => string;
  /** 코어가 준 Message 로 번역 */
  m: (message: Message) => string;
  date: (ts: number) => string;
  dateTime: (ts: number) => string;
  relative: (rel: RelativeTime) => string;
  duration: (ms: number) => string;
}

/** 화면에서 쓰는 번역 진입점. 언어를 바꾸면 구독 중인 화면이 다시 그려진다. */
export function useT(): Translator {
  const locale = usePetStore((s) => s.locale);

  const t = useCallback((key: string, params?: Params) => translate(locale, key, params), [locale]);

  return useMemo(
    () => ({
      locale,
      t,
      m: (message: Message) => formatMessage(locale, message),
      date: (ts: number) => formatDate(ts, locale),
      dateTime: (ts: number) => formatDateTime(ts, locale),
      relative: (rel: RelativeTime) => formatRelative(rel, locale),
      duration: (ms: number) => formatDuration(ms, locale),
    }),
    [locale, t],
  );
}
