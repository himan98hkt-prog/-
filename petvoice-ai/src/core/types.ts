/**
 * PetVoice AI - 공용 타입 정의
 *
 * 이 파일을 포함한 `src/core/*` 전체는 React Native / Expo 에 의존하지 않는
 * 순수 TypeScript 입니다. 덕분에 노드 환경에서 그대로 단위 테스트할 수 있고,
 * 나중에 웹·서버로 로직을 옮겨도 재사용됩니다.
 */

export type PetType = 'DOG' | 'CAT';

/** 분석 입력 매체 종류 */
export type MediaType = 'audio/m4a' | 'audio/mp4' | 'image/jpeg' | 'image/png';

/** 감정 키 (Gemini 응답의 emotionScores 키와 1:1 대응) */
export type EmotionKey =
  | 'happy'
  | 'playful'
  | 'affection'
  | 'attentionSeeking'
  | 'curious'
  | 'relaxed'
  | 'hungry'
  | 'anxiety'
  | 'fear'
  | 'alert'
  | 'territorial'
  | 'anger'
  | 'pain'
  | 'sad';

/** 감정 점수 (키 → 0~100 정수) */
export type EmotionScores = Partial<Record<EmotionKey, number>>;

/** 이상 징후 심각도 */
export type HealthLevel = 'none' | 'watch' | 'vet';

/** Gemini 가 돌려준 분석 결과를 정규화한 형태 */
export interface AnalysisResult {
  /** 반려동물 1인칭 말풍선 대사 */
  petVoiceMessage: string;
  /** 가장 확률이 높은 감정 */
  primaryEmotion: EmotionKey;
  /** 상위 3개 감정, 합이 100 이 되도록 정규화됨 */
  emotionScores: EmotionScores;
  /** 동물행동학적 원인 분석 */
  behaviorAnalysis: string;
  /** 보호자 행동 가이드 */
  actionGuide: string;
  /** 모델이 직접 이상 징후를 지목한 경우 (선택) */
  healthAlert?: string;
}

/** 반려동물 프로필 */
export interface PetProfile {
  id: string;
  name: string;
  type: PetType;
  /** 견종/묘종 (선택) */
  breed?: string;
  /** 나이(개월). 모르면 undefined */
  ageMonths?: number;
  /** 로컬 사진 URI (선택) */
  photoUri?: string;
  createdAt: number;
}

/** 저장되는 분석 히스토리 한 건 */
export interface AnalysisEntry {
  id: string;
  petId: string;
  createdAt: number;
  /** 어떤 매체로 분석했는지 */
  mediaKind: 'audio' | 'image';
  /** 사용자가 고른 상황 맥락 */
  context: string;
  /** 결과 화면·포토카드에 쓰는 로컬 사진/녹음 URI */
  mediaUri?: string;
  result: AnalysisResult;
  /** 분석 시점에 계산해 둔 이상 징후 판정 */
  health: HealthAssessment;
}

/** 이상 징후 판정 결과 */
export interface HealthAssessment {
  level: HealthLevel;
  /** 왜 그렇게 판단했는지 (사용자에게 그대로 보여줌) */
  reasons: string[];
  /** 보호자가 지금 할 수 있는 조치 */
  tips: string[];
}

/** 구독 상태 */
export interface Subscription {
  pro: boolean;
  /** 프로 만료 시각 (ms). 무료 사용자면 undefined */
  expiresAt?: number;
}
