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

/** 사용자에게 보여 줄 문구의 번역 키. 실제 문장은 UI 가 만든다. */
export function userMessageKey(error: unknown): string {
  const code: ApiErrorCode = error instanceof ApiError ? error.code : 'unknown';
  return `errors.${code}`;
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
