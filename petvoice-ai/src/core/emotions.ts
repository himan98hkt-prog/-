import type { EmotionKey, PetType } from './types';

export interface EmotionMeta {
  key: EmotionKey;
  /** 한국어 라벨 */
  label: string;
  emoji: string;
  /** 감정 막대/뱃지 색 */
  color: string;
  /** 긍정·중립·부정 — 다이어리 추세 계산에 사용 */
  tone: 'positive' | 'neutral' | 'negative';
}

const META: Record<EmotionKey, EmotionMeta> = {
  happy: { key: 'happy', label: '행복', emoji: '😊', color: '#FFB627', tone: 'positive' },
  playful: { key: 'playful', label: '신남·놀고싶음', emoji: '🎾', color: '#FF8A3D', tone: 'positive' },
  affection: { key: 'affection', label: '애정 표현', emoji: '💗', color: '#FF6FA5', tone: 'positive' },
  attentionSeeking: { key: 'attentionSeeking', label: '관심 요구', emoji: '🙋', color: '#F2A65A', tone: 'neutral' },
  curious: { key: 'curious', label: '호기심', emoji: '👀', color: '#5BC0BE', tone: 'neutral' },
  relaxed: { key: 'relaxed', label: '편안함', emoji: '😌', color: '#7BC950', tone: 'positive' },
  hungry: { key: 'hungry', label: '배고픔', emoji: '🍚', color: '#D9A441', tone: 'neutral' },
  anxiety: { key: 'anxiety', label: '불안', emoji: '😰', color: '#6C7BE0', tone: 'negative' },
  fear: { key: 'fear', label: '두려움', emoji: '😨', color: '#5A6ACF', tone: 'negative' },
  alert: { key: 'alert', label: '경계', emoji: '⚠️', color: '#8E7CC3', tone: 'negative' },
  territorial: { key: 'territorial', label: '영역 방어', emoji: '🚧', color: '#A2708A', tone: 'negative' },
  anger: { key: 'anger', label: '분노·짜증', emoji: '😤', color: '#E0524A', tone: 'negative' },
  pain: { key: 'pain', label: '통증 호소', emoji: '🤕', color: '#C62828', tone: 'negative' },
  sad: { key: 'sad', label: '외로움·우울', emoji: '😢', color: '#5F7C8A', tone: 'negative' },
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

/** 모델이 자주 뱉는 동의어 · 한국어 표현 흡수 */
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
};

/** 상황 맥락 프리셋 — 홈 화면 칩으로 노출 */
export const CONTEXT_PRESETS: Record<PetType, string[]> = {
  DOG: [
    '외출 직전',
    '보호자 귀가 직후',
    '식사 전',
    '식사 후',
    '산책 준비 중',
    '낯선 사람 방문',
    '다른 개를 만남',
    '혼자 집에 있을 때',
    '잠자기 전',
    '병원 다녀온 뒤',
  ],
  CAT: [
    '밥그릇 앞',
    '새벽에 울 때',
    '화장실 다녀온 뒤',
    '낯선 사람 방문',
    '창밖을 볼 때',
    '쓰다듬는 중',
    '다른 고양이를 만남',
    '이동장에 넣을 때',
    '혼자 집에 있을 때',
    '병원 다녀온 뒤',
  ],
};

export const PET_LABEL: Record<PetType, string> = { DOG: '강아지', CAT: '고양이' };
