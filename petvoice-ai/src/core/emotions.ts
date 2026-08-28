import type { EmotionKey, PetType } from './types';

export interface EmotionMeta {
  key: EmotionKey;
  /** 번역 키 (`emotion.playful`). 라벨 문자열은 UI 가 만든다. */
  labelKey: string;
  emoji: string;
  /** 감정 막대/뱃지 색 */
  color: string;
  /** 긍정·중립·부정 — 다이어리 추세 계산에 사용 */
  tone: 'positive' | 'neutral' | 'negative';
}

function meta(key: EmotionKey, emoji: string, color: string, tone: EmotionMeta['tone']): EmotionMeta {
  return { key, labelKey: `emotion.${key}`, emoji, color, tone };
}

const META: Record<EmotionKey, EmotionMeta> = {
  happy: meta('happy', '😊', '#FFB627', 'positive'),
  playful: meta('playful', '🎾', '#FF8A3D', 'positive'),
  affection: meta('affection', '💗', '#FF6FA5', 'positive'),
  attentionSeeking: meta('attentionSeeking', '🙋', '#F2A65A', 'neutral'),
  curious: meta('curious', '👀', '#5BC0BE', 'neutral'),
  relaxed: meta('relaxed', '😌', '#7BC950', 'positive'),
  hungry: meta('hungry', '🍚', '#D9A441', 'neutral'),
  anxiety: meta('anxiety', '😰', '#6C7BE0', 'negative'),
  fear: meta('fear', '😨', '#5A6ACF', 'negative'),
  alert: meta('alert', '⚠️', '#8E7CC3', 'negative'),
  territorial: meta('territorial', '🚧', '#A2708A', 'negative'),
  anger: meta('anger', '😤', '#E0524A', 'negative'),
  pain: meta('pain', '🤕', '#C62828', 'negative'),
  sad: meta('sad', '😢', '#5F7C8A', 'negative'),
};

export const EMOTION_KEYS = Object.keys(META) as EmotionKey[];

export function emotionMeta(key: EmotionKey): EmotionMeta {
  return META[key];
}

export function isEmotionKey(value: unknown): value is EmotionKey {
  return typeof value === 'string' && Object.prototype.hasOwnProperty.call(META, value);
}

/**
 * 모델이 `PLAYFUL`, `attention_seeking`, `관심요구` 처럼 제각각 돌려줘도
 * 내부 표준 키로 맞춰 준다. 못 알아보면 null.
 */
export function normalizeEmotionKey(raw: unknown): EmotionKey | null {
  if (typeof raw !== 'string') return null;
  const cleaned = raw.trim();
  if (!cleaned) return null;
  if (isEmotionKey(cleaned)) return cleaned;

  // snake_case / SCREAMING_SNAKE / kebab-case → camelCase
  const camel = cleaned
    .toLowerCase()
    .replace(/[\s_-]+(.)/g, (_, c: string) => c.toUpperCase())
    .replace(/[\s_-]+$/, '');
  if (isEmotionKey(camel)) return camel;

  return ALIASES[cleaned.toLowerCase()] ?? ALIASES[camel.toLowerCase()] ?? null;
}

/** 모델이 자주 뱉는 동의어 · 한국어/일본어 표현 흡수 */
const ALIASES: Record<string, EmotionKey> = {
  joy: 'happy',
  joyful: 'happy',
  excited: 'playful',
  excitement: 'playful',
  play: 'playful',
  love: 'affection',
  affectionate: 'affection',
  attention: 'attentionSeeking',
  needy: 'attentionSeeking',
  demanding: 'attentionSeeking',
  curiosity: 'curious',
  calm: 'relaxed',
  relaxation: 'relaxed',
  content: 'relaxed',
  hunger: 'hungry',
  anxious: 'anxiety',
  stress: 'anxiety',
  stressed: 'anxiety',
  separationanxiety: 'anxiety',
  afraid: 'fear',
  scared: 'fear',
  fearful: 'fear',
  vigilance: 'alert',
  vigilant: 'alert',
  wary: 'alert',
  guarding: 'territorial',
  territory: 'territorial',
  angry: 'anger',
  irritation: 'anger',
  aggression: 'anger',
  aggressive: 'anger',
  discomfort: 'pain',
  hurt: 'pain',
  painful: 'pain',
  sadness: 'sad',
  lonely: 'sad',
  loneliness: 'sad',
  depressed: 'sad',
  행복: 'happy',
  기쁨: 'happy',
  신남: 'playful',
  놀이: 'playful',
  애정: 'affection',
  관심요구: 'attentionSeeking',
  호기심: 'curious',
  편안: 'relaxed',
  편안함: 'relaxed',
  배고픔: 'hungry',
  불안: 'anxiety',
  두려움: 'fear',
  공포: 'fear',
  경계: 'alert',
  영역: 'territorial',
  분노: 'anger',
  짜증: 'anger',
  통증: 'pain',
  아픔: 'pain',
  슬픔: 'sad',
  외로움: 'sad',
  喜び: 'happy',
  遊びたい: 'playful',
  甘え: 'affection',
  不安: 'anxiety',
  恐怖: 'fear',
  警戒: 'alert',
  怒り: 'anger',
  痛み: 'pain',
  寂しい: 'sad',
  空腹: 'hungry',
};

/**
 * 상황 맥락에 붙는 의미 태그.
 * 문구는 언어마다 다르지만 규칙(분리불안 판정 등)은 같아야 하므로,
 * 이상 징후 로직은 **번역된 문장이 아니라 이 태그**를 본다.
 */
export type ContextTag =
  | 'separation'
  | 'reunion'
  | 'meal'
  | 'walk'
  | 'stranger'
  | 'social'
  | 'night'
  | 'vet'
  | 'petting'
  | 'litter'
  | 'window'
  | 'carrier';

export interface ContextPreset {
  /** 번역 키 (`context.beforeLeaving`) */
  key: string;
  tags: ContextTag[];
}

function preset(key: string, ...tags: ContextTag[]): ContextPreset {
  return { key: `context.${key}`, tags };
}

/** 상황 맥락 프리셋 — 홈 화면 칩으로 노출 */
export const CONTEXT_PRESETS: Record<PetType, ContextPreset[]> = {
  DOG: [
    preset('beforeLeaving', 'separation'),
    preset('afterReturn', 'reunion'),
    preset('beforeMeal', 'meal'),
    preset('afterMeal', 'meal'),
    preset('beforeWalk', 'walk'),
    preset('strangerVisit', 'stranger'),
    preset('meetingDog', 'social'),
    preset('homeAlone', 'separation'),
    preset('beforeSleep', 'night'),
    preset('afterVet', 'vet'),
  ],
  CAT: [
    preset('atFoodBowl', 'meal'),
    preset('cryingAtDawn', 'night'),
    preset('afterLitter', 'litter'),
    preset('strangerVisit', 'stranger'),
    preset('lookingOutside', 'window'),
    preset('whilePetting', 'petting'),
    preset('meetingCat', 'social'),
    preset('intoCarrier', 'carrier', 'vet'),
    preset('homeAlone', 'separation'),
    preset('afterVet', 'vet'),
  ],
};

/** 번역 키로 프리셋을 되찾는다 (저장된 기록에서 태그를 복원할 때) */
export function presetByKey(key: string): ContextPreset | null {
  for (const list of Object.values(CONTEXT_PRESETS)) {
    const found = list.find((p) => p.key === key);
    if (found) return found;
  }
  return null;
}

export const PET_LABEL_KEY: Record<PetType, string> = {
  DOG: 'pet.dog',
  CAT: 'pet.cat',
};
