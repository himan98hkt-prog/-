import { normalizeScores, sortedEmotions } from './analysis';
import type { AnalysisResult, EmotionKey, EmotionScores } from './types';

/**
 * 정밀 분석 — 연속으로 받은 결과 여러 개를 하나로 합친다.
 *
 * 3초 한 번은 우연이 섞인다. 짖음 한 번의 끝자락만 잡히거나, 하필 조용한 구간이거나.
 * 여러 번 듣고 평균을 내면 한 번의 잡음이 결과 전체를 흔들지 못한다.
 *
 * 합치는 방식:
 * - 감정 점수는 평균 낸 뒤 다시 상위 3개·합 100 으로 정규화한다
 * - 말풍선과 설명은 **종합 1위 감정을 가장 강하게 본 회차**의 것을 쓴다.
 *   평균 문장을 만들 수는 없으니, 결론과 가장 잘 맞는 회차를 대표로 세우는 편이 자연스럽다
 * - 이상 징후는 하나라도 잡혔으면 살린다 (놓치는 쪽이 더 위험하다)
 */
export function aggregateResults(results: AnalysisResult[]): AnalysisResult {
  if (results.length === 0) throw new Error('합칠 결과가 없습니다.');
  if (results.length === 1) return results[0];

  const totals: Record<string, number> = {};
  for (const result of results) {
    for (const [key, value] of Object.entries(result.emotionScores)) {
      totals[key] = (totals[key] ?? 0) + (value ?? 0);
    }
  }

  const emotionScores: EmotionScores = normalizeScores(
    Object.fromEntries(Object.entries(totals).map(([key, sum]) => [key, sum / results.length])),
  );

  const ranked = sortedEmotions(emotionScores);
  const primaryEmotion: EmotionKey = ranked[0]?.key ?? results[0].primaryEmotion;

  // 종합 1위 감정을 가장 높게 본 회차를 대표로
  const representative = results.reduce((best, current) => {
    const score = current.emotionScores[primaryEmotion] ?? 0;
    const bestScore = best.emotionScores[primaryEmotion] ?? 0;
    return score > bestScore ? current : best;
  }, results[0]);

  // 이상 징후는 한 번이라도 언급됐으면 남긴다
  const healthAlert = results.map((r) => r.healthAlert).find((alert) => alert && alert.trim());

  return {
    petVoiceMessage: representative.petVoiceMessage,
    primaryEmotion,
    emotionScores,
    behaviorAnalysis: representative.behaviorAnalysis,
    actionGuide: representative.actionGuide,
    ...(healthAlert ? { healthAlert } : {}),
  };
}

/** 정밀 분석에서 연속으로 녹음할 횟수 */
export const PRECISE_SHOT_COUNT = 3;

/** 회차별 결과가 얼마나 일치했는지 (0~100). 낮으면 상황이 계속 바뀌었다는 뜻 */
export function agreementScore(results: AnalysisResult[]): number {
  if (results.length < 2) return 100;
  const primaries = results.map((r) => r.primaryEmotion);
  const counts = new Map<string, number>();
  for (const key of primaries) counts.set(key, (counts.get(key) ?? 0) + 1);
  const top = Math.max(...counts.values());
  return Math.round((top / results.length) * 100);
}
