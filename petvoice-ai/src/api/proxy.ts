import { parseAnalysis, AnalysisParseError, type ParseFallbacks } from '../core/analysis';
import type { ContextTag } from '../core/emotions';
import { assessHealth } from '../core/health';
import { MODEL_CHAIN } from '../core/models';
import { buildPrompt, buildWeeklyReportPrompt, RESPONSE_SCHEMA } from '../core/prompt';
import type { AnalysisResult, HealthAssessment, Locale, MediaType, PetProfile } from '../core/types';
import { ApiError, codeFromStatus } from './errors';

/**
 * ⚠️ 보안 원칙 (Play Console 심사 항목)
 * 이 파일에는 GEMINI_API_KEY 가 절대 들어오지 않는다.
 * 클라이언트는 사용자 토큰만 들고 Supabase Edge Function 을 부르고,
 * 키는 서버(Edge Function) 환경변수에만 존재한다.
 *
 *  [App] --Bearer user token--> [supabase/functions/gemini-proxy] --GEMINI_API_KEY--> [Gemini]
 */

export interface ProxyConfig {
  /** `https://xxxx.supabase.co` */
  supabaseUrl: string;
  /** 공개 anon 키 (노출돼도 안전한 값) */
  anonKey: string;
  /** 현재 사용자 세션의 access token 을 돌려주는 함수 */
  getAccessToken: () => Promise<string | null>;
  /** 테스트 주입용 */
  fetchImpl?: typeof fetch;
  /** 밀리초. 기본 45초 (오디오 업로드 + 모델 추론) */
  timeoutMs?: number;
}

export interface AnalyzeInput {
  pet: PetProfile;
  mediaBase64: string;
  mediaType: MediaType;
  /** 사용자에게 보여 줄 상황 문구 (사용자 언어) */
  context: string;
  /** 언어와 무관한 의미 태그 — 이상 징후 규칙이 본다 */
  contextTags?: ContextTag[];
  locale: Locale;
  /** 모델이 문장을 비워 보냈을 때 채울 번역된 문구 */
  fallbacks?: ParseFallbacks;
}

export interface AnalyzeOutput {
  result: AnalysisResult;
  health: HealthAssessment;
}

const DEFAULT_TIMEOUT = 45_000;
const MAX_ATTEMPTS = 3;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** 재시도해도 의미 있는 실패인지 */
function retryable(error: unknown): boolean {
  return error instanceof ApiError && error.retryable;
}

async function callProxy(config: ProxyConfig, body: unknown): Promise<string> {
  const fetchImpl = config.fetchImpl ?? globalThis.fetch;
  if (!fetchImpl) throw new ApiError('network', 'fetch 를 사용할 수 없습니다.');

  const token = await config.getAccessToken();
  if (!token) throw new ApiError('unauthorized', '사용자 세션이 없습니다.', 401);

  const endpoint = `${config.supabaseUrl.replace(/\/+$/, '')}/functions/v1/gemini-proxy`;
  const timeoutMs = config.timeoutMs ?? DEFAULT_TIMEOUT;

  let lastError: unknown;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetchImpl(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          apikey: config.anonKey,
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        const code = codeFromStatus(response.status);
        const detail = await response.text().catch(() => '');
        throw new ApiError(code, detail || `HTTP ${response.status}`, response.status, code === 'server');
      }
      return await response.text();
    } catch (error) {
      lastError = error;
      if (error instanceof ApiError) {
        if (!retryable(error) || attempt === MAX_ATTEMPTS) throw error;
      } else if ((error as Error)?.name === 'AbortError') {
        lastError = new ApiError('timeout', '요청 시간이 초과됐습니다.', undefined, true);
        if (attempt === MAX_ATTEMPTS) throw lastError;
      } else {
        lastError = new ApiError('network', (error as Error)?.message ?? '네트워크 오류', undefined, true);
        if (attempt === MAX_ATTEMPTS) throw lastError;
      }
      // 지수 백오프: 0.8s → 1.6s
      await sleep(800 * 2 ** (attempt - 1));
    } finally {
      clearTimeout(timer);
    }
  }
  throw lastError instanceof ApiError ? lastError : new ApiError('unknown', '요청에 실패했습니다.');
}

/** 소리 또는 사진 한 건을 분석한다. */
export async function analyzePetMedia(config: ProxyConfig, input: AnalyzeInput): Promise<AnalyzeOutput> {
  const prompt = buildPrompt({
    pet: input.pet,
    mediaType: input.mediaType,
    context: input.context,
    locale: input.locale,
  });

  const raw = await callProxy(config, {
    task: 'analyze',
    // 서버가 앞에서부터 시도하고 안 되면 다음 모델로 내려간다
    models: MODEL_CHAIN,
    prompt,
    responseSchema: RESPONSE_SCHEMA,
    temperature: 0.4,
    media: { mimeType: input.mediaType, data: input.mediaBase64 },
  });

  let result: AnalysisResult;
  try {
    result = parseAnalysis(raw, input.fallbacks);
  } catch (error) {
    if (error instanceof AnalysisParseError) {
      throw new ApiError('parse', error.message);
    }
    throw error;
  }

  return { result, health: assessHealth(result, input.pet.type, input.contextTags ?? []) };
}

export interface WeeklyReport {
  headline: string;
  trend: string;
  concern: string;
  todo: string[];
}

/** Pro 전용 주간 행동 리포트 */
export async function requestWeeklyReport(
  config: ProxyConfig,
  pet: PetProfile,
  digest: string,
  locale: Locale,
): Promise<WeeklyReport> {
  const raw = await callProxy(config, {
    task: 'weekly',
    models: MODEL_CHAIN,
    prompt: buildWeeklyReportPrompt(pet.name, pet.type, digest, locale),
    temperature: 0.5,
  });

  try {
    const start = raw.indexOf('{');
    const end = raw.lastIndexOf('}');
    const parsed = JSON.parse(raw.slice(start, end + 1)) as Partial<WeeklyReport>;
    return {
      headline: String(parsed.headline ?? '').trim(),
      trend: String(parsed.trend ?? '').trim(),
      concern: String(parsed.concern ?? '').trim(),
      todo: Array.isArray(parsed.todo) ? parsed.todo.map((t) => String(t).trim()).filter(Boolean) : [],
    };
  } catch {
    throw new ApiError('parse', '주간 리포트를 읽지 못했습니다.');
  }
}
