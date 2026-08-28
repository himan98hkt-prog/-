import { emotionMeta } from './emotions';
import type { EmotionKey } from './types';

/**
 * SNS 공유용 포토카드.
 *
 * 실제 캡처는 `react-native-view-shot` 이 하지만, **어디에 무엇을 어떤 크기로 그릴지**는
 * 전부 여기서 계산한다. 레이아웃이 순수 함수라 테스트로 고정할 수 있고,
 * 나중에 서버 사이드 렌더링(OG 이미지)으로 재사용하기도 쉽다.
 */

export interface CardTheme {
  key: string;
  name: string;
  /** 프로 구독자 전용 테마인지 */
  pro: boolean;
  bubbleBg: string;
  bubbleText: string;
  /** 뱃지·테두리 강조색 */
  accent: string;
  /** 사진 위에 깔 어두운 그라데이션 세기 0~1 */
  scrim: number;
  /** 말풍선 모서리 스타일 */
  shape: 'round' | 'cloud' | 'sharp';
}

export const CARD_THEMES: CardTheme[] = [
  { key: 'classic', name: '클래식 화이트', pro: false, bubbleBg: '#FFFFFF', bubbleText: '#1F2430', accent: '#FF8A3D', scrim: 0.35, shape: 'round' },
  { key: 'night', name: '나이트 블랙', pro: false, bubbleBg: 'rgba(20,22,30,0.88)', bubbleText: '#FFFFFF', accent: '#FFB627', scrim: 0.45, shape: 'round' },
  { key: 'peach', name: '피치 하트', pro: true, bubbleBg: '#FFE3EC', bubbleText: '#8A2F52', accent: '#FF6FA5', scrim: 0.25, shape: 'cloud' },
  { key: 'mint', name: '민트 크림', pro: true, bubbleBg: '#DFF6F0', bubbleText: '#14544B', accent: '#5BC0BE', scrim: 0.25, shape: 'cloud' },
  { key: 'comic', name: '코믹 만화', pro: true, bubbleBg: '#FFF7D6', bubbleText: '#232323', accent: '#232323', scrim: 0.2, shape: 'sharp' },
  { key: 'retro', name: '레트로 필름', pro: true, bubbleBg: 'rgba(255,248,231,0.92)', bubbleText: '#4A3B2A', accent: '#C2703D', scrim: 0.4, shape: 'sharp' },
];

export const DEFAULT_THEME_KEY = 'classic';

export function themeByKey(key: string): CardTheme {
  return CARD_THEMES.find((t) => t.key === key) ?? CARD_THEMES[0];
}

/** 구독 상태에 따라 쓸 수 있는 테마만 (프로 테마는 잠금 표시용으로 같이 반환) */
export function themesFor(isPro: boolean): { theme: CardTheme; locked: boolean }[] {
  return CARD_THEMES.map((theme) => ({ theme, locked: theme.pro && !isPro }));
}

/** 잠긴 테마를 고른 상태로 저장돼 있어도 무료 사용자에게는 기본 테마로 되돌린다. */
export function resolveTheme(key: string, isPro: boolean): CardTheme {
  const theme = themeByKey(key);
  return theme.pro && !isPro ? themeByKey(DEFAULT_THEME_KEY) : theme;
}

/**
 * 공백 우선, 없으면 글자 단위로 줄바꿈.
 * 한국어는 어절 단위가 자연스러워 공백을 먼저 본다.
 */
export function wrapText(text: string, maxCharsPerLine: number): string[] {
  const clean = text.replace(/\s+/g, ' ').trim();
  if (!clean) return [];
  if (maxCharsPerLine <= 0) return [clean];

  const lines: string[] = [];
  let current = '';

  for (const word of clean.split(' ')) {
    let token = word;
    // 한 어절이 한 줄보다 길면 강제로 쪼갠다
    while (token.length > maxCharsPerLine) {
      if (current) {
        lines.push(current);
        current = '';
      }
      lines.push(token.slice(0, maxCharsPerLine));
      token = token.slice(maxCharsPerLine);
    }
    if (!current) current = token;
    else if (current.length + 1 + token.length <= maxCharsPerLine) current = `${current} ${token}`;
    else {
      lines.push(current);
      current = token;
    }
  }
  if (current) lines.push(current);
  return lines;
}

export interface CardLayoutInput {
  width: number;
  /** 지정하지 않으면 4:5 인스타 비율 */
  height?: number;
  message: string;
  emotion: EmotionKey;
  themeKey?: string;
  isPro?: boolean;
  petName?: string;
}

export interface CardLayout {
  width: number;
  height: number;
  theme: CardTheme;
  bubble: { x: number; y: number; width: number; height: number; radius: number };
  /** 말풍선 꼬리 꼭짓점 (사진 속 반려동물 쪽을 향함) */
  tail: { x: number; y: number; size: number };
  fontSize: number;
  lineHeight: number;
  lines: string[];
  badge: { label: string; emoji: string; color: string; x: number; y: number };
  /** 하단 워터마크 위치 */
  watermark: { x: number; y: number; text: string };
}

/** 인스타 피드에 맞는 4:5 비율 */
export const CARD_ASPECT = 5 / 4;

/**
 * 카드 안의 모든 좌표를 계산한다. 폭만 주면 나머지는 비율로 결정된다.
 */
export function layoutPhotoCard({
  width,
  height = Math.round(width * CARD_ASPECT),
  message,
  emotion,
  themeKey = DEFAULT_THEME_KEY,
  isPro = false,
  petName,
}: CardLayoutInput): CardLayout {
  const theme = resolveTheme(themeKey, isPro);
  const scale = width / 320;
  const padding = Math.round(16 * scale);

  const text = message.replace(/\s+/g, ' ').trim();
  // 글자 수가 많을수록 폰트를 줄여 3줄 안에 들어오게 한다
  const baseSize = text.length <= 16 ? 25 : text.length <= 28 ? 21 : text.length <= 44 ? 18 : 16;
  const fontSize = Math.max(12, Math.round(baseSize * scale));
  const lineHeight = Math.round(fontSize * 1.38);

  const bubbleWidth = Math.round(width - padding * 2);
  const innerPaddingX = Math.round(14 * scale);
  const innerPaddingY = Math.round(12 * scale);
  // 한글 기준 글자 폭 ≈ 폰트 크기의 1.0배, 라틴/숫자를 섞어도 무리 없는 보수적 추정
  const maxChars = Math.max(6, Math.floor((bubbleWidth - innerPaddingX * 2) / (fontSize * 0.98)));
  const lines = wrapText(text, maxChars);

  const bubbleHeight = lines.length * lineHeight + innerPaddingY * 2;
  const tailSize = Math.round(14 * scale);
  const bubbleY = Math.round(height - padding - tailSize - bubbleHeight - 26 * scale);

  const meta = emotionMeta(emotion);

  return {
    width,
    height,
    theme,
    bubble: {
      x: padding,
      y: bubbleY,
      width: bubbleWidth,
      height: bubbleHeight,
      radius: theme.shape === 'sharp' ? Math.round(6 * scale) : Math.round(20 * scale),
    },
    tail: { x: Math.round(width * 0.28), y: bubbleY + bubbleHeight, size: tailSize },
    fontSize,
    lineHeight,
    lines,
    badge: {
      label: meta.label,
      emoji: meta.emoji,
      color: meta.color,
      x: padding,
      y: padding,
    },
    watermark: {
      x: padding,
      y: Math.round(height - padding - 12 * scale),
      text: petName ? `${petName} · PetVoice AI` : 'PetVoice AI',
    },
  };
}
