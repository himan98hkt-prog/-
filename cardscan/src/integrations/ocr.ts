// 명함 사진 → 필드. 이미지 인식은 서버(supabase/functions/scan-card)에서 Claude 로 하고, 앱은 API 키를 갖지 않는다.
import { sanitizeFields } from '../core/normalize';
import { Settings } from '../core/settings';
import { CardFields } from '../core/types';
import { Fetch } from './http';

export interface ScanResult {
  fields: CardFields;
  extra: string[];
  /** 명함 뒷면/영문면 등 서버가 판단한 참고 사항 */
  note?: string;
}

export class OcrNotConfiguredError extends Error {
  constructor() {
    super('명함 인식 서버가 설정되지 않았습니다. 설정 > 명함 인식에서 서버 주소를 입력하세요.');
  }
}

export async function scanCardImage(base64Jpeg: string, settings: Settings, fetchImpl: Fetch = fetch): Promise<ScanResult> {
  const { endpoint, anonKey, appSecret } = settings.ocr;
  if (!/^https:\/\//.test(endpoint)) throw new OcrNotConfiguredError();

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (anonKey) {
    headers.Authorization = `Bearer ${anonKey}`;
    headers.apikey = anonKey;
  }
  if (appSecret) headers['x-app-secret'] = appSecret;

  const res = await fetchImpl(endpoint, {
    method: 'POST',
    headers,
    body: JSON.stringify({ image: base64Jpeg, mediaType: 'image/jpeg' }),
  });
  const text = await res.text();
  let data: { fields?: unknown; extra?: unknown; note?: unknown; error?: string } = {};
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error(`인식 서버 응답 오류 (HTTP ${res.status})`);
  }
  if (!res.ok || data.error) throw new Error(data.error || `인식 서버 오류 (HTTP ${res.status})`);
  return {
    fields: sanitizeFields(data.fields),
    extra: Array.isArray(data.extra) ? data.extra.filter((x): x is string => typeof x === 'string').slice(0, 20) : [],
    note: typeof data.note === 'string' && data.note ? data.note : undefined,
  };
}
