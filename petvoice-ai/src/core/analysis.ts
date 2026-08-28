import { emotionMeta, normalizeEmotionKey } from './emotions';
import type { AnalysisResult, EmotionKey, EmotionScores } from './types';

/** 모델 응답을 쓸 수 없을 때 던진다. 화면에서는 "다시 시도" 안내로 이어진다. */
export class AnalysisParseError extends Error {
  constructor(message: string, readonly raw?: string) {
    super(message);
    this.name = 'AnalysisParseError';
  }
}

/** 결과 화면에 최대 몇 개의 감정을 보여줄지 (지시서: 주요 감정 3가지) */
export const TOP_EMOTION_COUNT = 3;

/**
 * `responseMimeType: application/json` 을 줘도 모델은 가끔
 * ```json 펜스나 앞뒤 설명을 붙인다. 실제로 쓸 수 있는 JSON 조각만 잘라 낸다.
 */
function extractJson(text: string): string {
  const trimmed = text.trim();
  const fence = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const body = (fence ? fence[1] : trimmed).trim();
  const start = body.indexOf('{');
  const end = body.lastIndexOf('}');
  if (start === -1 || end === -1 || end <= start) {
    throw new AnalysisParseError('모델 응답에서 JSON 을 찾지 못했습니다.', text);
  }
  return body.slice(start, end + 1);
}

function asText(value: unknown): string {
  if (typeof value !== 'string') return '';
  return value.replace(/\s+/g, ' ').trim();
}

/**
 * 상위 N개 감정만 남기고 합이 정확히 100 이 되도록 정수 보정한다.
 * (최대잔여법 — 반올림 오차가 한쪽으로 몰리지 않는다)
 */
export function normalizeScores(raw: unknown, topN = TOP_EMOTION_COUNT): EmotionScores {
  if (!raw || typeof raw !== 'object') return {};

  const merged = new Map<EmotionKey, number>();
  for (const [rawKey, rawValue] of Object.entries(raw as Record<string, unknown>)) {
    const key = normalizeEmotionKey(rawKey);
    if (!key) continue;
    const num = typeof rawValue === 'number' ? rawValue : Number(rawValue);
    if (!Number.isFinite(num) || num <= 0) continue;
    // 같은 감정으로 접히는 키가 둘 이상이면 큰 값을 채택
    merged.set(key, Math.max(merged.get(key) ?? 0, Math.min(100, num)));
  }
  if (merged.size === 0) return {};

  const top = [...merged.entries()].sort((a, b) => b[1] - a[1]).slice(0, Math.max(1, topN));
  const total = top.reduce((sum, [, v]) => sum + v, 0);
  if (total <= 0) return {};

  const exact = top.map(([key, value]) => ({ key, exact: (value / total) * 100 }));
  const floored = exact.map((e) => ({ ...e, floor: Math.floor(e.exact) }));
  let remainder = 100 - floored.reduce((sum, e) => sum + e.floor, 0);

  const byFraction = [...floored].sort((a, b) => b.exact - b.floor - (a.exact - a.floor));
  for (const entry of byFraction) {
    if (remainder <= 0) break;
    entry.floor += 1;
    remainder -= 1;
  }

  const out: EmotionScores = {};
  for (const { key, floor } of floored) out[key] = floor;
  return out;
}

/** 점수 내림차순 정렬된 배열 — 화면·리포트에서 순서를 매번 다시 계산하지 않도록 */
export function sortedEmotions(scores: EmotionScores): { key: EmotionKey; score: number }[] {
  return (Object.entries(scores) as [EmotionKey, number][])
    .filter(([, v]) => Number.isFinite(v) && v > 0)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([key, score]) => ({ key, score }));
}

/** 모델이 말풍선을 비워 보냈을 때 감정만으로 최소한의 대사를 만든다. */
function fallbackMessage(primary: EmotionKey): string {
  const canned: Partial<Record<EmotionKey, string>> = {
    happy: '지금 기분 최고야!',
    playful: '심심해! 같이 놀자!',
    affection: '옆에 있어줘서 좋아.',
    attentionSeeking: '나 좀 봐줘, 여기야!',
    curious: '저거 뭐야? 궁금해!',
    relaxed: '이대로 계속 쉬고 싶어.',
    hungry: '배고파… 밥 언제 줘?',
    anxiety: '조금 불안해, 곁에 있어줘.',
    fear: '무서워… 여기 있기 싫어.',
    alert: '뭔가 이상해, 내가 지킬게.',
    territorial: '여긴 내 자리야!',
    anger: '지금은 건드리지 말아줘.',
    pain: '어딘가 아파, 봐줄래?',
    sad: '혼자라 심심하고 외로워.',
  };
  return canned[primary] ?? `${emotionMeta(primary).label} 상태예요.`;
}

/** 말풍선이 길면 포토카드에서 넘치므로 안전 길이로 자른다. */
export function clampMessage(message: string, max = 60): string {
  const text = asText(message);
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1).trimEnd()}…`;
}

/**
 * 프록시가 돌려준 원본(문자열 또는 이미 파싱된 객체)을 화면이 믿고 쓸 수 있는
 * `AnalysisResult` 로 정규화한다.
 */
export function parseAnalysis(raw: unknown): AnalysisResult {
  let data: unknown = raw;

  if (typeof raw === 'string') {
    const json = extractJson(raw);
    try {
      data = JSON.parse(json);
    } catch {
      throw new AnalysisParseError('모델 응답 JSON 파싱에 실패했습니다.', raw);
    }
  }

  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new AnalysisParseError('모델 응답이 객체가 아닙니다.');
  }
  const obj = data as Record<string, unknown>;

  const emotionScores = normalizeScores(obj.emotionScores);
  const ranked = sortedEmotions(emotionScores);
  if (ranked.length === 0) {
    throw new AnalysisParseError('감정 점수를 하나도 해석하지 못했습니다.');
  }

  // primaryEmotion 이 없거나 점수표에 없는 감정을 가리키면 1위 감정으로 교정한다.
  const declared = normalizeEmotionKey(obj.primaryEmotion);
  const primaryEmotion = declared && emotionScores[declared] != null ? declared : ranked[0].key;

  const message = clampMessage(asText(obj.petVoiceMessage)) || fallbackMessage(primaryEmotion);
  const healthAlert = asText(obj.healthAlert);

  return {
    petVoiceMessage: message,
    primaryEmotion,
    emotionScores,
    behaviorAnalysis:
      asText(obj.behaviorAnalysis) || '행동 근거를 충분히 설명받지 못했어요. 조금 더 또렷한 소리나 사진으로 다시 시도해 보세요.',
    actionGuide: asText(obj.actionGuide) || '평소와 다른 점이 있는지 잠시 지켜봐 주세요.',
    ...(healthAlert ? { healthAlert } : {}),
  };
}
