import { describe, expect, it } from 'vitest';
import { assessHealth, assessHistoryRisk } from '../src/core/health';
import type { AnalysisEntry, AnalysisResult } from '../src/core/types';

function result(over: Partial<AnalysisResult> = {}): AnalysisResult {
  return {
    petVoiceMessage: '심심해!',
    primaryEmotion: 'playful',
    emotionScores: { playful: 80, curious: 15, relaxed: 5 },
    behaviorAnalysis: '경쾌한 짧은 발성이 반복됩니다.',
    actionGuide: '놀아 주세요.',
    ...over,
  };
}

function entry(over: Partial<AnalysisEntry>): AnalysisEntry {
  return {
    id: 'x',
    petId: 'p',
    createdAt: Date.now(),
    mediaKind: 'audio',
    context: '',
    result: result(),
    health: { level: 'none', reasons: [], tips: [] },
    ...over,
  };
}

describe('assessHealth', () => {
  it('평범한 놀이 신호는 아무 경고도 내지 않는다', () => {
    expect(assessHealth(result(), 'DOG').level).toBe('none');
  });

  it('통증 점수가 임계값을 넘으면 병원 방문을 권한다', () => {
    const assessment = assessHealth(
      result({ emotionScores: { pain: 45, anxiety: 35, fear: 20 }, primaryEmotion: 'pain' }),
      'DOG',
    );
    expect(assessment.level).toBe('vet');
    expect(assessment.tips.join(' ')).toContain('동물병원');
  });

  it('모델이 healthAlert 를 주면 그대로 근거에 싣고 병원 단계로 올린다', () => {
    const assessment = assessHealth(result({ healthAlert: '지속적인 기침이 확인됩니다.' }), 'CAT');
    expect(assessment.level).toBe('vet');
    expect(assessment.reasons).toContain('지속적인 기침이 확인됩니다.');
  });

  it('행동 분석 문장에 의학적 신호가 있으면 잡아낸다', () => {
    const assessment = assessHealth(
      result({ behaviorAnalysis: '뒷다리를 절뚝이며 일어서기 힘들어합니다.' }),
      'DOG',
    );
    expect(assessment.level).toBe('vet');
    expect(assessment.reasons.some((r) => r.includes('보행 이상'))).toBe(true);
  });

  it('외출 맥락의 높은 불안은 분리불안으로 안내한다', () => {
    const assessment = assessHealth(
      result({ emotionScores: { anxiety: 62, sad: 26, attentionSeeking: 12 }, primaryEmotion: 'anxiety' }),
      'DOG',
      '외출 직전',
    );
    expect(assessment.level).toBe('watch');
    expect(assessment.reasons.join(' ')).toContain('분리불안');
    expect(assessment.tips.join(' ')).toContain('외출');
  });

  it('부정 감정이 과반을 크게 넘으면 관찰 단계로 올린다', () => {
    const assessment = assessHealth(
      result({ emotionScores: { alert: 40, territorial: 35, curious: 25 }, primaryEmotion: 'alert' }),
      'CAT',
    );
    expect(assessment.level).toBe('watch');
  });

  it('종에 맞는 팁을 준다', () => {
    const cat = assessHealth(result({ emotionScores: { anxiety: 60, sad: 30, fear: 10 } }), 'CAT');
    expect(cat.tips.join(' ')).toContain('캣타워');
  });
});

describe('assessHistoryRisk', () => {
  const now = Date.UTC(2026, 7, 28, 12);
  const day = 24 * 60 * 60 * 1000;

  it('기록이 없으면 배너를 띄우지 않는다', () => {
    expect(assessHistoryRisk([], now)).toBeNull();
  });

  it('병원 권고가 2회 이상이면 강한 경고', () => {
    const entries = [
      entry({ createdAt: now - day, health: { level: 'vet', reasons: [], tips: [] } }),
      entry({ createdAt: now - 2 * day, health: { level: 'vet', reasons: [], tips: [] } }),
    ];
    expect(assessHistoryRisk(entries, now)?.level).toBe('vet');
  });

  it('불안 신호가 3회 이상 반복되면 행동 교정을 권한다', () => {
    const anxious = result({ emotionScores: { anxiety: 60, sad: 30, fear: 10 }, primaryEmotion: 'anxiety' });
    const entries = [0, 1, 2].map((i) => entry({ createdAt: now - i * day, result: anxious }));
    const risk = assessHistoryRisk(entries, now);
    expect(risk?.level).toBe('watch');
    expect(risk?.message).toContain('분리불안');
  });

  it('7일 밖의 기록은 세지 않는다', () => {
    const entries = [
      entry({ createdAt: now - 10 * day, health: { level: 'vet', reasons: [], tips: [] } }),
      entry({ createdAt: now - 12 * day, health: { level: 'vet', reasons: [], tips: [] } }),
    ];
    expect(assessHistoryRisk(entries, now)).toBeNull();
  });
});
