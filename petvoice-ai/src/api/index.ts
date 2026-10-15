import { isConfigured, SUPABASE_ANON_KEY, SUPABASE_URL } from './config';
import { analyzeDemo } from './demo';
import { analyzeDirect } from './directGemini';
import { getTestKey } from './testKey';
import {
  analyzePetMedia,
  requestWeeklyReport,
  type AnalyzeInput,
  type AnalyzeOutput,
  type ProxyConfig,
  type WeeklyReport,
} from './proxy';
import { getAccessToken } from './supabase';

function proxyConfig(): ProxyConfig {
  return { supabaseUrl: SUPABASE_URL, anonKey: SUPABASE_ANON_KEY, getAccessToken };
}

/**
 * 분석 경로 결정.
 *
 * 1. 서버(프록시)가 설정돼 있으면 언제나 그쪽 — 출시 구조다
 * 2. 아니면, 테스트 빌드에서 사용자가 자기 키를 넣어 뒀다면 직접 호출
 * 3. 둘 다 아니면 데모 응답 (화면 흐름만 확인용)
 */
export async function analyze(input: AnalyzeInput): Promise<AnalyzeOutput> {
  if (isConfigured) return analyzePetMedia(proxyConfig(), input);

  const testKey = await getTestKey();
  if (testKey) return analyzeDirect(input, testKey);

  return analyzeDemo(input);
}

export async function weeklyReport(
  pet: AnalyzeInput['pet'],
  digest: string,
  locale: AnalyzeInput['locale'],
): Promise<WeeklyReport | null> {
  if (!isConfigured) return null;
  return requestWeeklyReport(proxyConfig(), pet, digest, locale);
}

export { isConfigured };
export type { AnalyzeOutput, WeeklyReport };
