import { EMOTION_KEYS, PET_LABEL } from './emotions';
import type { MediaType, PetProfile } from './types';

export interface PromptInput {
  pet: Pick<PetProfile, 'name' | 'type' | 'breed' | 'ageMonths'>;
  mediaType: MediaType;
  /** 사용자가 고른/입력한 상황 맥락 */
  context: string;
}

/** 프록시가 그대로 Gemini `responseSchema` 로 넘기는 JSON 스키마 */
export const RESPONSE_SCHEMA = {
  type: 'object',
  properties: {
    petVoiceMessage: { type: 'string' },
    primaryEmotion: { type: 'string', enum: EMOTION_KEYS },
    emotionScores: {
      type: 'object',
      properties: Object.fromEntries(EMOTION_KEYS.map((k) => [k, { type: 'integer' }])),
    },
    behaviorAnalysis: { type: 'string' },
    actionGuide: { type: 'string' },
    healthAlert: { type: 'string' },
  },
  required: ['petVoiceMessage', 'primaryEmotion', 'emotionScores', 'behaviorAnalysis', 'actionGuide'],
} as const;

function ageText(ageMonths?: number): string {
  if (ageMonths == null || !Number.isFinite(ageMonths) || ageMonths < 0) return '나이 미상';
  if (ageMonths < 12) return `${Math.round(ageMonths)}개월령`;
  const years = Math.floor(ageMonths / 12);
  const months = Math.round(ageMonths % 12);
  return months ? `${years}살 ${months}개월` : `${years}살`;
}

/**
 * 멀티모달 분석 프롬프트.
 *
 * 개발지시서의 프롬프트를 기반으로, 실제 서비스에서 문제가 됐던 지점을 보강했다.
 * - 감정 키를 열거해 모델이 매번 다른 이름을 만들어 내지 않게 고정
 * - 진단 단정을 막고 "병원에서 확인" 표현을 쓰도록 안전 가드
 * - 말풍선은 SNS 공유용이라 길이를 못박음 (40자 이내, 이모지 최대 1개)
 */
export function buildPrompt({ pet, mediaType, context }: PromptInput): string {
  const isAudio = mediaType.startsWith('audio');
  const mediaLabel = isAudio ? '울음소리/짖는 소리' : '행동/자세 사진';
  const petLabel = PET_LABEL[pet.type];
  const profile = [pet.breed?.trim(), ageText(pet.ageMonths)].filter(Boolean).join(' · ');
  const petName = pet.name?.trim() || (pet.type === 'DOG' ? '우리 강아지' : '우리 고양이');
  const situation = context.trim() || '특별한 상황 설명 없음';

  return `당신은 20년 경력의 반려동물 행동 교정 전문가(수의행동의학 전문)입니다.
제공된 ${petLabel}("${petName}", ${profile})의 ${mediaLabel}와 상황 맥락("${situation}")을 면밀히 분석하세요.

[분석 원칙]
1. ${petName}의 입장에서 귀엽고 솔직한 1인칭 독백 메시지를 작성하세요. 40자 이내, 이모지는 최대 1개, 보호자를 "엄마/아빠"로 부르지 말고 "너"나 호칭 없이 말하세요.
2. 주요 감정 3가지와 확률(퍼센트 정수)을 산출하고, 세 값의 합이 정확히 100이 되게 하세요.
3. 동물행동학적 원인 분석과 보호자가 즉시 취해야 할 행동 가이드를 제시하세요.
4. 통증·질병이 의심되면 healthAlert 에 근거를 적되, 확정 진단은 내리지 말고 "수의사 확인이 필요하다"는 표현을 쓰세요.
5. ${isAudio ? '소리가 반려동물 울음이 아니거나 너무 작아' : '사진에 반려동물이 보이지 않아'} 판단이 어려우면 behaviorAnalysis 에 그 사실을 밝히고 emotionScores 를 낮은 확신도로 채우세요.

[emotionScores 에 사용할 수 있는 키 — 이 목록 밖의 키는 쓰지 마세요]
${EMOTION_KEYS.join(', ')}

[JSON 응답 포맷]
{
  "petVoiceMessage": "지금 너무 심심해! 얼른 공 던져줘!",
  "primaryEmotion": "playful",
  "emotionScores": { "playful": 75, "attentionSeeking": 20, "anxiety": 5 },
  "behaviorAnalysis": "경쾌하고 높은 톤의 짧은 짖음과 꼬리가 수평 이상으로 흔들리는 상태로, 놀이와 교감을 강하게 요구하고 있습니다.",
  "actionGuide": "터그 놀이나 노즈워크 장난감으로 에너지를 발산시켜 주시면 좋습니다.",
  "healthAlert": ""
}

모든 문장은 한국어 존댓말로, JSON 외의 텍스트는 절대 출력하지 마세요.`;
}

/** 주간 행동 리포트(Pro) 생성용 프롬프트 */
export function buildWeeklyReportPrompt(petName: string, petType: PetProfile['type'], digest: string): string {
  return `당신은 20년 경력의 반려동물 행동 교정 전문가입니다.
아래는 최근 7일간 ${PET_LABEL[petType]} "${petName}"의 감정 분석 기록 요약입니다.

${digest}

이 기록을 바탕으로 주간 행동 리포트를 작성하세요.
- headline: 이번 주를 한 문장으로 요약 (30자 이내)
- trend: 감정 변화 추세와 그 원인 추정 (2~3문장)
- concern: 주의 깊게 볼 지점. 없으면 빈 문자열
- todo: 보호자가 다음 주에 실천할 구체적 행동 3가지 (문자열 배열)

JSON 으로만 답하세요:
{ "headline": "", "trend": "", "concern": "", "todo": ["", "", ""] }`;
}
