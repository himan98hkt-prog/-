/** 화면이 분기할 수 있도록 실패 원인을 코드로 구분한다. */
export type ApiErrorCode =
  | 'network'
  | 'timeout'
  | 'unauthorized'
  | 'quota'
  | 'rate_limited'
  | 'unsupported_media'
  | 'server'
  | 'parse'
  | 'unknown';

export class ApiError extends Error {
  constructor(
    readonly code: ApiErrorCode,
    message: string,
    readonly status?: number,
    readonly retryable = false,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const MESSAGES: Record<ApiErrorCode, string> = {
  network: '인터넷 연결을 확인해 주세요.',
  timeout: '분석이 오래 걸리고 있어요. 잠시 후 다시 시도해 주세요.',
  unauthorized: '로그인이 만료됐어요. 앱을 다시 열어 주세요.',
  quota: '오늘 무료 분석을 모두 사용했어요.',
  rate_limited: '요청이 너무 잦아요. 잠시 후 다시 시도해 주세요.',
  unsupported_media: '이 파일은 분석할 수 없어요. 다시 녹음하거나 촬영해 주세요.',
  server: '분석 서버에 문제가 있어요. 잠시 후 다시 시도해 주세요.',
  parse: '분석 결과를 읽지 못했어요. 한 번만 더 시도해 주세요.',
  unknown: '알 수 없는 오류가 발생했어요.',
};

/** 사용자에게 보여줄 문구 (기술 용어 없이) */
export function userMessage(error: unknown): string {
  if (error instanceof ApiError) return MESSAGES[error.code];
  return MESSAGES.unknown;
}

/** HTTP 상태 → 에러 코드 */
export function codeFromStatus(status: number): ApiErrorCode {
  if (status === 401 || status === 403) return 'unauthorized';
  if (status === 402) return 'quota';
  if (status === 413 || status === 415) return 'unsupported_media';
  if (status === 429) return 'rate_limited';
  if (status >= 500) return 'server';
  return 'unknown';
}
