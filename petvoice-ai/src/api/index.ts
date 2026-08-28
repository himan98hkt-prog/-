import { isConfigured, SUPABASE_ANON_KEY, SUPABASE_URL } from './config';
import { analyzeDemo } from './demo';
import { analyzePetMedia, requestWeeklyReport, type AnalyzeInput, type AnalyzeOutput, type ProxyConfig, type WeeklyReport } from './proxy';
import { getAccessToken } from './supabase';

function proxyConfig(): ProxyConfig {
  return { supabaseUrl: SUPABASE_URL, anonKey: SUPABASE_ANON_KEY, getAccessToken };
}

/** Supabase 가 설정돼 있으면 실제 프록시, 아니면 데모 응답 */
export async function analyze(input: AnalyzeInput): Promise<AnalyzeOutput> {
  if (!isConfigured) return analyzeDemo(input);
  return analyzePetMedia(proxyConfig(), input);
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
