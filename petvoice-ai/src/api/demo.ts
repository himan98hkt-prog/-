import { parseAnalysis } from '../core/analysis';
import { assessHealth } from '../core/health';
import type { AnalyzeInput, AnalyzeOutput } from './proxy';

/**
 * Supabase 설정 전에도 앱 전체 흐름(녹음 → 분석 → 결과 → 포토카드 → 히스토리)을
 * 그대로 돌려 보기 위한 데모 응답. 상황 맥락에 따라 다른 결과를 낸다.
 */
const SAMPLES: { match: RegExp; payload: Record<string, unknown> }[] = [
  {
    match: /외출|혼자|출근|집을 비/,
    payload: {
      petVoiceMessage: '가지 마… 나 혼자 두고 어디 가?',
      primaryEmotion: 'anxiety',
      emotionScores: { anxiety: 62, sad: 26, attentionSeeking: 12 },
      behaviorAnalysis:
        '보호자의 외출 준비 신호(가방·열쇠 소리)에 반응해 높은 톤의 연속 발성이 나타납니다. 분리 상황에 대한 예기 불안 패턴입니다.',
      actionGuide: '외출 준비 동작을 하루 여러 번 반복하되 나가지 않는 연습으로 신호의 의미를 희석해 주세요.',
    },
  },
  {
    match: /밥|식사|배고/,
    payload: {
      petVoiceMessage: '밥! 밥! 지금 당장 밥 주세요!',
      primaryEmotion: 'hungry',
      emotionScores: { hungry: 58, attentionSeeking: 30, playful: 12 },
      behaviorAnalysis: '짧고 반복적인 고음 발성과 보호자·밥그릇 사이를 오가는 이동이 함께 나타나는 전형적인 요구 행동입니다.',
      actionGuide: '급여 시간을 고정하고, 조를 때 바로 주기보다 조용해진 뒤 주면 요구성 발성이 줄어듭니다.',
    },
  },
  {
    match: /낯선|손님|방문/,
    payload: {
      petVoiceMessage: '누구야! 여긴 우리 집이라고!',
      primaryEmotion: 'alert',
      emotionScores: { alert: 48, territorial: 34, fear: 18 },
      behaviorAnalysis: '낮고 굵은 톤의 연속 짖음과 앞으로 쏠린 체중은 영역 방어와 경계가 섞인 상태를 뜻합니다.',
      actionGuide: '손님이 눈을 맞추지 않고 옆으로 지나가게 하고, 아이가 스스로 다가오면 간식을 주세요.',
    },
  },
  {
    match: /병원|아프|절뚝/,
    payload: {
      petVoiceMessage: '여기 좀 아파… 살살 만져줘.',
      primaryEmotion: 'pain',
      emotionScores: { pain: 46, anxiety: 34, fear: 20 },
      behaviorAnalysis: '평소보다 낮고 끊기는 신음성 발성이 반복되며 특정 부위를 보호하려는 자세가 관찰됩니다.',
      actionGuide: '만졌을 때 반응하는 부위를 확인하고 무리한 촉진은 피하세요.',
      healthAlert: '통증 관련 발성이 반복되고 있어 수의사 확인이 필요합니다.',
    },
  },
];

const DEFAULT_PAYLOAD = {
  petVoiceMessage: '심심해! 지금 나랑 놀아줄 수 있어?',
  primaryEmotion: 'playful',
  emotionScores: { playful: 71, attentionSeeking: 22, curious: 7 },
  behaviorAnalysis:
    '경쾌하고 높은 톤의 짧은 발성이 일정 간격으로 반복되고 있어, 놀이와 교감을 요구하는 상태로 보입니다.',
  actionGuide: '터그 놀이나 노즈워크로 5~10분 정도 에너지를 발산시켜 주세요.',
};

/** 실제 네트워크 지연을 흉내 내 로딩 UI 를 검증할 수 있게 한다. */
export async function analyzeDemo(input: AnalyzeInput, delayMs = 1400): Promise<AnalyzeOutput> {
  await new Promise((resolve) => setTimeout(resolve, delayMs));
  const payload = SAMPLES.find((s) => s.match.test(input.context))?.payload ?? DEFAULT_PAYLOAD;
  const result = parseAnalysis(payload);
  return { result, health: assessHealth(result, input.pet.type, input.context) };
}
