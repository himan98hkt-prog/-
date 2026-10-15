import { describe, expect, it } from 'vitest';
import {
  AnalysisParseError,
  clampMessage,
  normalizeScores,
  parseAnalysis,
  sortedEmotions,
} from '../src/core/analysis';

const VALID = {
  petVoiceMessage: '엄마 나 지금 너무 심심해! 얼른 공 던져줘!',
  primaryEmotion: 'PLAYFUL',
  emotionScores: { playful: 75, attentionSeeking: 20, anxiety: 5 },
  behaviorAnalysis: '경쾌하고 높은 톤의 짧은 짖음.',
  actionGuide: '터그 놀이를 해 주세요.',
};

describe('normalizeScores', () => {
  it('상위 3개만 남기고 합을 100으로 맞춘다', () => {
    const scores = normalizeScores({ playful: 40, anxiety: 30, happy: 20, sad: 10, pain: 5 });
    expect(Object.keys(scores)).toHaveLength(3);
    expect(Object.values(scores).reduce((a, b) => a + (b ?? 0), 0)).toBe(100);
  });

  it('합이 100이 아닌 값도 비율을 유지하며 정규화한다', () => {
    const scores = normalizeScores({ playful: 6, anxiety: 3, happy: 1 });
    expect(scores).toEqual({ playful: 60, anxiety: 30, happy: 10 });
  });

  it('반올림 잔여분을 소수부가 큰 쪽에 배분해 합 100을 보장한다', () => {
    const scores = normalizeScores({ playful: 1, anxiety: 1, happy: 1 });
    expect(Object.values(scores).reduce((a, b) => a + (b ?? 0), 0)).toBe(100);
  });

  it('모델이 보낸 별칭·대문자 키를 표준 키로 흡수한다', () => {
    const scores = normalizeScores({ JOY: 50, separation_anxiety: 30, 'attention-seeking': 20 });
    expect(Object.keys(scores).sort()).toEqual(['anxiety', 'attentionSeeking', 'happy']);
  });

  it('모르는 키와 0 이하 값은 버린다', () => {
    expect(normalizeScores({ vibes: 90, playful: 10, anxiety: 0, sad: -5 })).toEqual({ playful: 100 });
  });

  it('쓸 수 있는 감정이 없으면 빈 객체', () => {
    expect(normalizeScores({ vibes: 90 })).toEqual({});
    expect(normalizeScores(null)).toEqual({});
  });
});

describe('parseAnalysis', () => {
  it('정상 응답을 정규화한다', () => {
    const result = parseAnalysis(VALID);
    expect(result.primaryEmotion).toBe('playful');
    expect(result.emotionScores).toEqual({ playful: 75, attentionSeeking: 20, anxiety: 5 });
    expect(result.petVoiceMessage).toContain('심심해');
  });

  it('```json 펜스와 앞뒤 잡담이 섞인 문자열도 읽는다', () => {
    const raw = `물론이죠!\n\`\`\`json\n${JSON.stringify(VALID)}\n\`\`\`\n도움이 되었길 바랍니다.`;
    expect(parseAnalysis(raw).primaryEmotion).toBe('playful');
  });

  it('primaryEmotion 이 점수표에 없으면 1위 감정으로 교정한다', () => {
    const result = parseAnalysis({ ...VALID, primaryEmotion: 'pain' });
    expect(result.primaryEmotion).toBe('playful');
  });

  it('말풍선이 비면 호출부가 준 대체 문구를 쓴다', () => {
    const result = parseAnalysis(
      { ...VALID, petVoiceMessage: '   ' },
      { messageFor: (emotion) => `fallback:${emotion}` },
    );
    expect(result.petVoiceMessage).toBe('fallback:playful');
  });

  it('설명이 비면 대체 문구로 채운다', () => {
    const result = parseAnalysis(
      { ...VALID, behaviorAnalysis: '', actionGuide: '' },
      { behavior: '설명 없음', action: '지켜봐 주세요' },
    );
    expect(result.behaviorAnalysis).toBe('설명 없음');
    expect(result.actionGuide).toBe('지켜봐 주세요');
  });

  it('감정 점수를 하나도 못 읽으면 실패로 처리한다', () => {
    expect(() => parseAnalysis({ ...VALID, emotionScores: { unknown: 100 } })).toThrow(AnalysisParseError);
  });

  it('JSON 이 아니면 실패로 처리한다', () => {
    expect(() => parseAnalysis('죄송합니다, 분석할 수 없습니다.')).toThrow(AnalysisParseError);
  });

  it('healthAlert 가 비어 있으면 필드를 만들지 않는다', () => {
    expect(parseAnalysis({ ...VALID, healthAlert: '' }).healthAlert).toBeUndefined();
    expect(parseAnalysis({ ...VALID, healthAlert: '통증 확인 필요' }).healthAlert).toBe('통증 확인 필요');
  });
});

describe('clampMessage / sortedEmotions', () => {
  it('긴 말풍선은 잘라 낸다', () => {
    const long = '가'.repeat(120);
    expect(clampMessage(long).length).toBeLessThanOrEqual(60);
    expect(clampMessage(long).endsWith('…')).toBe(true);
  });

  it('감정을 점수 내림차순으로 정렬한다', () => {
    expect(sortedEmotions({ anxiety: 20, playful: 70, sad: 10 }).map((e) => e.key)).toEqual([
      'playful',
      'anxiety',
      'sad',
    ]);
  });
});
