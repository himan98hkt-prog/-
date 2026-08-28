import { describe, expect, it } from 'vitest';
import { CONTEXT_PRESETS, EMOTION_KEYS, emotionMeta, isEmotionKey, normalizeEmotionKey, presetByKey } from '../src/core/emotions';

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
    expect(normalizeEmotionKey('不安')).toBe('anxiety');
  });

  it('모르는 값은 null', () => {
    expect(normalizeEmotionKey('vibes')).toBeNull();
    expect(normalizeEmotionKey('')).toBeNull();
    expect(normalizeEmotionKey(42)).toBeNull();
  });
});

describe('감정 메타데이터', () => {
  it('모든 감정에 번역 키·이모지·색·톤이 있다', () => {
    for (const key of EMOTION_KEYS) {
      const meta = emotionMeta(key);
      expect(meta.labelKey).toBe(`emotion.${key}`);
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

  it('모든 상황 프리셋에 번역 키와 의미 태그가 붙어 있다', () => {
    for (const list of Object.values(CONTEXT_PRESETS)) {
      for (const item of list) {
        expect(item.key.startsWith('context.')).toBe(true);
        expect(item.tags.length).toBeGreaterThan(0);
      }
    }
  });

  it('혼자 남는 상황에는 separation 태그가 붙는다', () => {
    const alone = CONTEXT_PRESETS.DOG.find((p) => p.key === 'context.homeAlone');
    expect(alone?.tags).toContain('separation');
    expect(presetByKey('context.beforeLeaving')?.tags).toContain('separation');
    expect(presetByKey('context.nope')).toBeNull();
  });
});
