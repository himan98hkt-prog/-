import { describe, expect, it } from 'vitest';
import { agreementScore, aggregateResults, PRECISE_SHOT_COUNT } from '../src/core/aggregate';
import type { AnalysisResult } from '../src/core/types';

function result(over: Partial<AnalysisResult>): AnalysisResult {
  return {
    petVoiceMessage: '기본 대사',
    primaryEmotion: 'playful',
    emotionScores: { playful: 70, curious: 20, happy: 10 },
    behaviorAnalysis: '기본 분석',
    actionGuide: '기본 가이드',
    ...over,
  };
}

describe('aggregateResults', () => {
  it('하나뿐이면 그대로 돌려준다', () => {
    const only = result({});
    expect(aggregateResults([only])).toBe(only);
  });

  it('빈 배열은 거부한다', () => {
    expect(() => aggregateResults([])).toThrow();
  });

  it('감정 점수를 평균 내고 합 100 을 유지한다', () => {
    const merged = aggregateResults([
      result({ emotionScores: { playful: 90, curious: 10 } }),
      result({ emotionScores: { playful: 30, anxiety: 70 }, primaryEmotion: 'anxiety' }),
    ]);
    expect(Object.values(merged.emotionScores).reduce((a, b) => a + (b ?? 0), 0)).toBe(100);
    expect(merged.emotionScores.playful).toBeGreaterThan(0);
    expect(merged.emotionScores.anxiety).toBeGreaterThan(0);
  });

  it('한 번의 튀는 결과가 전체를 뒤집지 못한다', () => {
    const merged = aggregateResults([
      result({ emotionScores: { playful: 80, curious: 20 } }),
      result({ emotionScores: { playful: 75, curious: 25 } }),
      result({ emotionScores: { anxiety: 90, fear: 10 }, primaryEmotion: 'anxiety' }),
    ]);
    expect(merged.primaryEmotion).toBe('playful');
  });

  it('종합 1위 감정을 가장 강하게 본 회차의 문장을 대표로 쓴다', () => {
    const merged = aggregateResults([
      result({ emotionScores: { playful: 60, curious: 40 }, petVoiceMessage: '약한 회차' }),
      result({ emotionScores: { playful: 95, curious: 5 }, petVoiceMessage: '강한 회차', behaviorAnalysis: '강한 분석' }),
    ]);
    expect(merged.petVoiceMessage).toBe('강한 회차');
    expect(merged.behaviorAnalysis).toBe('강한 분석');
  });

  it('이상 징후는 한 번이라도 잡혔으면 살린다', () => {
    const merged = aggregateResults([
      result({}),
      result({ healthAlert: '기침이 반복됩니다.' }),
      result({}),
    ]);
    expect(merged.healthAlert).toBe('기침이 반복됩니다.');
  });

  it('아무도 이상 징후를 말하지 않으면 필드를 만들지 않는다', () => {
    expect(aggregateResults([result({}), result({})]).healthAlert).toBeUndefined();
  });
});

describe('agreementScore', () => {
  it('전부 같은 감정이면 100', () => {
    expect(agreementScore([result({}), result({}), result({})])).toBe(100);
  });

  it('갈리면 낮아진다', () => {
    const score = agreementScore([
      result({ primaryEmotion: 'playful' }),
      result({ primaryEmotion: 'anxiety' }),
      result({ primaryEmotion: 'anxiety' }),
    ]);
    expect(score).toBe(67);
  });

  it('한 번뿐이면 비교할 게 없다', () => {
    expect(agreementScore([result({})])).toBe(100);
  });

  it('정밀 분석 횟수는 3회', () => {
    expect(PRECISE_SHOT_COUNT).toBe(3);
  });
});
