/**
 * 크래시·오류 보고 (선택).
 *
 * 기기·OS 조합에서만 터지는 문제는 스토어 리뷰로 알게 되면 이미 늦다.
 * 다만 이 앱은 반려동물 사진·녹음을 다루므로 **기본은 꺼짐**이고,
 * 설정에서 켠 사용자만 보낸다. 미디어와 개인 식별 정보는 절대 싣지 않는다.
 *
 * DSN 이 없으면(대부분의 개발 환경) 아무것도 하지 않는다.
 */

type SentryModule = {
  init: (options: Record<string, unknown>) => void;
  captureException: (error: unknown) => void;
  close?: () => Promise<void>;
};

const DSN = process.env.EXPO_PUBLIC_SENTRY_DSN ?? '';

let sentry: SentryModule | null | undefined;
let started = false;

function load(): SentryModule | null {
  if (sentry !== undefined) return sentry;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require('@sentry/react-native') as Partial<SentryModule> | undefined;
    sentry = typeof mod?.init === 'function' ? (mod as SentryModule) : null;
  } catch {
    sentry = null;
  }
  return sentry;
}

/** 사용자가 동의했을 때만 켠다. 동의를 껐다가 켜도 이 함수 하나로 처리된다. */
export function initErrorReporting(enabled: boolean): void {
  if (!enabled || !DSN || started) return;
  const mod = load();
  if (!mod) return;

  mod.init({
    dsn: DSN,
    // 사용자를 식별하지 않는다
    sendDefaultPii: false,
    // 화면 녹화·스크린샷 같은 기능은 켜지 않는다
    attachScreenshot: false,
    attachViewHierarchy: false,
    tracesSampleRate: 0,
  });
  started = true;
}

/** 조용히 삼키면 안 되는 오류를 남긴다 (동의하지 않았으면 아무 일도 하지 않는다) */
export function reportError(error: unknown): void {
  if (!started) return;
  load()?.captureException(error);
}
