import { EMOTION_KEYS } from './emotions';
import type { Locale, MediaType, PetProfile } from './types';

export interface PromptInput {
  pet: Pick<PetProfile, 'name' | 'type' | 'breed' | 'ageMonths'>;
  mediaType: MediaType;
  /** 사용자가 고른/입력한 상황 맥락 (이미 사용자 언어) */
  context: string;
  /** 결과를 어떤 언어로 받을지 */
  locale: Locale;
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

/**
 * 지시문은 한국어 하나로 유지하고, **출력 언어만** 지시로 바꾼다.
 * 언어별 템플릿을 따로 두면 셋이 서로 어긋나기 시작하는데,
 * 튜닝된 프롬프트가 갈라지는 쪽이 손해가 크다고 봤다.
 */
const LANGUAGE_NAME: Record<Locale, string> = {
  ko: '한국어',
  en: '영어(English)',
  ja: '일본어(日本語)',
};

const PET_WORD: Record<PetProfile['type'], string> = { DOG: '강아지', CAT: '고양이' };

/**
 * 품종별 행동 특성.
 * 같은 소리도 품종에 따라 해석이 달라진다 — 이 한 줄이 분석을 눈에 띄게 구체적으로 만든다.
 * 키는 소문자 부분 일치로 찾는다 (사용자가 "포메"라고만 적어도 걸리게).
 */
const BREED_NOTES: { match: RegExp; note: string }[] = [
  { match: /포메|pomeranian/i, note: '경계성 짖음과 요구성 발성이 잦은 품종입니다.' },
  { match: /말티|maltese/i, note: '분리불안 발생률이 높고 고음 발성이 특징입니다.' },
  { match: /푸들|poodle/i, note: '지능이 높아 지루함에서 오는 요구 행동이 많습니다.' },
  { match: /치와와|chihuahua/i, note: '방어적 경계심이 강해 위협 신호를 크게 표현합니다.' },
  { match: /시바|shiba/i, note: '독립성이 강하고 불쾌감을 높은 비명성 발성으로 표현합니다.' },
  { match: /진돗|jindo/i, note: '영역성과 낯가림이 강한 편입니다.' },
  { match: /비글|beagle/i, note: '후각 자극에 반응한 하울링이 잦습니다.' },
  { match: /리트리버|retriever/i, note: '사회성이 높아 놀이·관심 요구 발성이 주를 이룹니다.' },
  { match: /웰시코기|corgi/i, note: '목축 본능으로 움직이는 대상에 짖는 경향이 있습니다.' },
  { match: /닥스|dachshund/i, note: '경계 짖음이 많고 허리 통증 관련 신호를 주의해야 합니다.' },
  {
    match: /시츄|shih ?tzu|퍼그|pug|불독|bulldog/i,
    note: '단두종이라 호흡음이 평소에도 거칠 수 있어 호흡기 신호 판단에 주의가 필요합니다.',
  },
  { match: /코숏|코리안숏헤어|korean short/i, note: '개체차가 크지만 대체로 경계심이 뚜렷합니다.' },
  { match: /샴|siamese/i, note: '발성이 매우 잦고 요구 표현이 분명한 품종입니다.' },
  { match: /페르시안|persian/i, note: '활동량이 낮아 평소보다 잦은 발성은 불편 신호일 수 있습니다.' },
  {
    match: /러시안블루|russian blue/i,
    note: '낯선 자극에 민감하고 조용한 편이라 발성 자체가 신호일 수 있습니다.',
  },
  { match: /벵갈|bengal/i, note: '활동 요구량이 매우 높아 에너지 미발산이 문제 행동으로 이어집니다.' },
  { match: /먼치킨|munchkin/i, note: '관절 부담이 있어 움직임 관련 통증 신호를 살펴야 합니다.' },
];

function breedNote(breed?: string): string | null {
  if (!breed?.trim()) return null;
  return BREED_NOTES.find((entry) => entry.match.test(breed))?.note ?? null;
}

/** 나이대별 주의점 */
function ageNote(type: PetProfile['type'], ageMonths?: number): string | null {
  if (ageMonths == null || !Number.isFinite(ageMonths) || ageMonths < 0) return null;
  if (ageMonths < 6) return '사회화 시기라 새로운 자극에 과도하게 반응할 수 있습니다.';
  if (ageMonths < 18) return '에너지 요구량이 큰 시기로, 미발산이 문제 행동으로 이어지기 쉽습니다.';
  const seniorFrom = type === 'DOG' ? 96 : 132;
  if (ageMonths >= seniorFrom) {
    return '노령기입니다. 밤 울음·방향 감각 저하는 인지기능장애(CDS)나 통증 신호일 수 있으니 특히 주의해서 보세요.';
  }
  return null;
}

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
 * - 말풍선은 SNS 공유용이라 길이를 못박음
 * - 품종·나이 특성을 주입해 같은 소리도 맥락에 맞게 읽도록 함
 */
export function buildPrompt({ pet, mediaType, context, locale }: PromptInput): string {
  const isAudio = mediaType.startsWith('audio');
  const mediaLabel = isAudio ? '울음소리/짖는 소리' : '행동/자세 사진';
  const petLabel = PET_WORD[pet.type];
  const profile = [pet.breed?.trim(), ageText(pet.ageMonths)].filter(Boolean).join(' · ');
  const petName = pet.name?.trim() || petLabel;
  const situation = context.trim() || '특별한 상황 설명 없음';
  const language = LANGUAGE_NAME[locale];

  const notes = [breedNote(pet.breed), ageNote(pet.type, pet.ageMonths)].filter(Boolean);
  const knowledge = notes.length
    ? `\n[이 아이에 대해 알려진 특성]\n${notes.map((n) => `- ${n}`).join('\n')}\n`
    : '';

  return `당신은 20년 경력의 반려동물 행동 교정 전문가(수의행동의학 전문)입니다.
출력하는 모든 문장은 반드시 ${language}로 작성하세요.

제공된 ${petLabel}("${petName}", ${profile})의 ${mediaLabel}와 상황 맥락("${situation}")을 면밀히 분석하세요.
${knowledge}
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
  "petVoiceMessage": "...",
  "primaryEmotion": "playful",
  "emotionScores": { "playful": 75, "attentionSeeking": 20, "anxiety": 5 },
  "behaviorAnalysis": "...",
  "actionGuide": "...",
  "healthAlert": ""
}

JSON 외의 텍스트는 절대 출력하지 마세요. 다시 강조합니다 — 모든 문장은 ${language}로 작성하세요.`;
}

/** 주간 행동 리포트(Pro) 생성용 프롬프트 */
export function buildWeeklyReportPrompt(
  petName: string,
  petType: PetProfile['type'],
  digest: string,
  locale: Locale,
): string {
  return `당신은 20년 경력의 반려동물 행동 교정 전문가입니다.
출력하는 모든 문장은 반드시 ${LANGUAGE_NAME[locale]}로 작성하세요.

아래는 최근 7일간 ${PET_WORD[petType]} "${petName}"의 감정 분석 기록 요약입니다.

${digest}

이 기록을 바탕으로 주간 행동 리포트를 작성하세요.
- headline: 이번 주를 한 문장으로 요약 (30자 이내)
- trend: 감정 변화 추세와 그 원인 추정 (2~3문장)
- concern: 주의 깊게 볼 지점. 없으면 빈 문자열
- todo: 보호자가 다음 주에 실천할 구체적 행동 3가지 (문자열 배열)

JSON 으로만 답하세요:
{ "headline": "", "trend": "", "concern": "", "todo": ["", "", ""] }`;
}
