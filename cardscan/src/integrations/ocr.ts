// 명함 사진 → 필드.
// - 무료 모드(device, 기본): 휴대폰 안의 Google ML Kit 한국어 OCR → 규칙 분석(core/cardParser). 인터넷·요금 없음.
// - 유료 모드(direct): 앱이 Anthropic Messages API 를 직접 호출. 공식 TypeScript SDK 는 React Native 를
//   지원하지 않아 REST 로 부르되, 요청 본문·응답 해석은 서버 함수와 같은 코드(buildCardRequest/parseCardResponse)를 쓴다.
// - 서버 모드(server): supabase/functions/scan-card 경유 — API 키를 휴대폰에 두지 않는다.
import { sanitizeFields } from '../core/normalize';
import { parseCardText, OcrLineInput } from '../core/cardParser';
import { effectiveOcrMode, Settings } from '../core/settings';
import { CardFields } from '../core/types';
import { buildCardRequest, ExtractError, FALLBACK_BETA, MODEL, parseCardResponse } from '../../supabase/functions/scan-card/extract';
import { Fetch } from './http';

export interface ScanResult {
  fields: CardFields;
  extra: string[];
  /** 명함 뒷면/영문면 등 서버가 판단한 참고 사항 */
  note?: string;
}

export interface CapturedForOcr {
  /** 휴대폰 안의 JPEG 파일 경로 (무료 인식) */
  uri: string;
  /** 같은 사진의 base64 (유료 인식 전송용) */
  base64: string;
}

export interface OcrDeps {
  fetch?: Fetch;
  /** 온디바이스 OCR (modules/card-ocr) — 테스트에서는 가짜를 넣는다 */
  recognize?: (uri: string) => Promise<{ lines: OcrLineInput[] }>;
}

const API = 'https://api.anthropic.com/v1';
const API_HEADERS = (apiKey: string) => ({
  'x-api-key': apiKey,
  'anthropic-version': '2023-06-01',
  'content-type': 'application/json',
});

function apiErrorMessage(status: number, detail?: string): string {
  if (status === 401) return 'API 키가 올바르지 않습니다. 설정에서 키를 다시 확인하세요.';
  if (status === 403) return 'API 키에 이 모델 사용 권한이 없습니다.';
  if (status === 429) return '요청이 많습니다. 잠시 후 다시 시도하세요.';
  if (status === 400 && detail && /credit|balance/i.test(detail)) return 'Anthropic 계정의 크레딧이 부족합니다. console.anthropic.com 에서 충전하세요.';
  if (status >= 500) return '인식 서비스가 일시적으로 바쁩니다. 잠시 후 다시 시도하세요.';
  return `인식 서비스 오류 (HTTP ${status})${detail ? ` — ${detail}` : ''}`;
}

const toResult = (fields: unknown, extra: unknown, note: unknown): ScanResult => ({
  fields: sanitizeFields(fields),
  extra: Array.isArray(extra) ? extra.filter((x): x is string => typeof x === 'string').slice(0, 20) : [],
  note: typeof note === 'string' && note ? note : undefined,
});

async function scanDirect(base64Jpeg: string, apiKey: string, fetchImpl: Fetch): Promise<ScanResult> {
  const res = await fetchImpl(`${API}/messages`, {
    method: 'POST',
    headers: { ...API_HEADERS(apiKey), 'anthropic-beta': FALLBACK_BETA },
    body: JSON.stringify(buildCardRequest(base64Jpeg, 'image/jpeg')),
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(apiErrorMessage(res.status, data?.error?.message));
  let r;
  try {
    r = parseCardResponse(data ?? {});
  } catch (e) {
    throw new Error(e instanceof ExtractError ? e.message : '인식 결과를 해석하지 못했습니다');
  }
  if (!r.isBusinessCard) throw new Error('명함이 아닌 사진으로 보입니다. 명함이 화면에 꽉 차게 다시 찍어 주세요.');
  return toResult(r.fields, r.extra, r.note);
}

async function scanViaServer(base64Jpeg: string, settings: Settings, fetchImpl: Fetch): Promise<ScanResult> {
  const { endpoint, anonKey, appSecret } = settings.ocr;
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
  return toResult(data.fields, data.extra, data.note);
}

export async function scanCardImage(img: CapturedForOcr, settings: Settings, deps: OcrDeps = {}): Promise<ScanResult> {
  const fetchImpl = deps.fetch ?? fetch;
  const mode = effectiveOcrMode(settings);
  if (mode === 'direct') return scanDirect(img.base64, settings.ocr.apiKey, fetchImpl);
  if (mode === 'server') return scanViaServer(img.base64, settings, fetchImpl);

  if (!deps.recognize) throw new Error('이 기기에서는 무료 인식을 쓸 수 없습니다 (안드로이드 설치 앱에서만 동작).');
  const { lines } = await deps.recognize(img.uri);
  if (!lines.length) throw new Error('글자를 찾지 못했습니다. 명함이 화면에 꽉 차고 초점이 맞게 다시 찍어 주세요.');
  const parsed = parseCardText(lines);
  // 규칙 분석 결과도 같은 정리 규칙(번호 하이픈·이메일 소문자)을 거친다
  return toResult(parsed.fields, parsed.extra, undefined);
}

/** 설정 화면의 "연결 확인" — 토큰을 쓰지 않는 요청으로 키·서버를 점검한다. */
export async function checkOcr(settings: Settings, fetchImpl: Fetch = fetch): Promise<void> {
  const o = settings.ocr;
  if (o.mode === 'device') return;
  if (o.mode === 'direct') {
    if (!o.apiKey.startsWith('sk-ant-')) throw new Error('Anthropic API 키는 sk-ant- 로 시작합니다.');
    // 모델 정보 조회는 과금되지 않는다
    const res = await fetchImpl(`${API}/models/${MODEL}`, { headers: API_HEADERS(o.apiKey) });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(apiErrorMessage(res.status, data?.error?.message));
    }
    return;
  }
  if (!/^https:\/\//.test(o.endpoint)) throw new Error('서버 주소는 https:// 로 시작해야 합니다.');
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (o.anonKey) {
    headers.Authorization = `Bearer ${o.anonKey}`;
    headers.apikey = o.anonKey;
  }
  if (o.appSecret) headers['x-app-secret'] = o.appSecret;
  const res = await fetchImpl(o.endpoint, { method: 'POST', headers, body: JSON.stringify({ ping: true }) });
  if (!res.ok) throw new Error(`HTTP ${res.status} ${(await res.text()).slice(0, 200)}`);
}
