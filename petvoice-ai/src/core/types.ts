import type { ContextTag } from './emotions';
import type { Message } from './message';

/**
 * PetVoice AI - 공용 타입 정의
 *
 * 이 파일을 포함한 `src/core/*` 전체는 React Native / Expo 에 의존하지 않는
 * 순수 TypeScript 입니다. 덕분에 노드 환경에서 그대로 단위 테스트할 수 있고,
 * 나중에 웹·서버로 로직을 옮겨도 재사용됩니다.
 */

export type PetType = 'DOG' | 'CAT';

/** 지원 언어 */
export type Locale = 'ko' | 'en' | 'ja';

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
  /** 사용자에게 보여 줄 상황 문구 (분석 당시 언어) */
  context: string;
  /** 프리셋에서 골랐다면 그 번역 키 — 언어를 바꿔도 다시 번역할 수 있게 */
  contextKey?: string;
  /** 언어와 무관한 의미 태그. 이상 징후 규칙이 보는 값. */
  contextTags?: ContextTag[];
  /** 결과 화면·포토카드에 쓰는 로컬 사진 URI */
  mediaUri?: string;
  /** 다시 들어 볼 수 있는 녹음 파일 URI (소리 분석일 때) */
  audioUri?: string;
  result: AnalysisResult;
  /** 분석 시점에 계산해 둔 이상 징후 판정 */
  health: HealthAssessment;
  /** 녹음 중 측정한 음량(dBFS) — 파형 표시에 쓴다 */
  levels?: number[];
  /** 정밀 분석이면 종합한 횟수 */
  shotCount?: number;
  /** 사용자가 남긴 정확도 피드백 */
  feedback?: 'up' | 'down';
}

/** 이상 징후 판정 결과 */
export interface HealthAssessment {
  level: HealthLevel;
  /** 왜 그렇게 판단했는지. 번역 참조이거나, 모델이 쓴 문장 그대로. */
  reasons: Message[];
  /** 보호자가 지금 할 수 있는 조치 */
  tips: Message[];
}

/** 구독을 산 스토어. `dev` 는 개발 빌드에서 상태만 바꾼 경우 */
export type SubscriptionStore = 'play' | 'appstore' | 'dev';

/**
 * 구독 상태.
 * 스토어(Play/App Store)가 알려 주는 생애주기를 그대로 옮겼다.
 * - `grace`   : 결제 실패 후 유예 기간 — 기능은 계속 열어 준다
 * - `on_hold` : 유예 기간도 지난 상태 — 기능 잠금
 * - `paused`  : 사용자가 일시정지 (Play 전용)
 * - `pending` : 느린 결제 수단으로 승인 대기
 */
export type SubscriptionState =
  | 'active'
  | 'grace'
  | 'on_hold'
  | 'paused'
  | 'canceled'
  | 'expired'
  | 'pending'
  | 'none';

/** 구독 상태 */
export interface Subscription {
  pro: boolean;
  /** 프로 만료 시각 (ms). 무료 사용자면 undefined */
  expiresAt?: number;
  /** 어느 스토어에서 산 구독인지 */
  store?: SubscriptionStore;
  /** 구매한 상품 ID */
  productId?: string;
  /** 자동 갱신이 켜져 있는지 (해지 예약이면 false) */
  autoRenewing?: boolean;
  /** 스토어가 알려 준 생애주기 상태 */
  state?: SubscriptionState;
  /** 서버 검증과 마지막으로 맞춘 시각 (ms) */
  verifiedAt?: number;
}
