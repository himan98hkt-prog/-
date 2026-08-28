import { describe, expect, it } from 'vitest';
import { CONTEXT_PRESETS, EMOTION_KEYS, emotionMeta, isEmotionKey, normalizeEmotionKey } from '../src/core/emotions';

describe('normalizeEmotionKey', () => {
  it('표준 키는 그대로', () => {
    expect(normalizeEmotionKey('playful')).toBe('playful');
  });

  it('대문자·스네이크·케밥 표기를 흡수한다', () => {
    expect(normalizeEmotionKey('PLAYFUL')).toBe('playful');
    expect(normalizeEmotionKey('ATTENTION_SEEKING')).toBe('attentionSeeking');
    expect(normalizeEmotionKey('attention-seeking')).toBe('attentionSeeking');
  });

  it('영어 동의어와 한국어 표현을 흡수한다', () => {
    expect(normalizeEmotionKey('joy')).toBe('happy');
    expect(normalizeEmotionKey('aggressive')).toBe('anger');
    expect(normalizeEmotionKey('불안')).toBe('anxiety');
    expect(normalizeEmotionKey('통증')).toBe('pain');
  });

  it('모르는 값은 null', () => {
    expect(normalizeEmotionKey('vibes')).toBeNull();
    expect(normalizeEmotionKey('')).toBeNull();
    expect(normalizeEmotionKey(42)).toBeNull();
  });
});

describe('감정 메타데이터', () => {
  it('모든 감정에 라벨·이모지·색·톤이 있다', () => {
    for (const key of EMOTION_KEYS) {
      const meta = emotionMeta(key);
      expect(meta.label).toBeTruthy();
      expect(meta.emoji).toBeTruthy();
      expect(meta.color).toMatch(/^#[0-9A-F]{6}$/i);
      expect(['positive', 'neutral', 'negative']).toContain(meta.tone);
    }
  });

  it('isEmotionKey 가 프로토타입 속성에 속지 않는다', () => {
    expect(isEmotionKey('toString')).toBe(false);
    expect(isEmotionKey('constructor')).toBe(false);
  });

  it('강아지와 고양이의 상황 프리셋이 서로 다르다', () => {
    expect(CONTEXT_PRESETS.DOG).not.toEqual(CONTEXT_PRESETS.CAT);
    expect(CONTEXT_PRESETS.DOG.length).toBeGreaterThan(5);
    expect(CONTEXT_PRESETS.CAT.length).toBeGreaterThan(5);
  });
});
