/**
 * 분석에 쓸 모델 후보를 우선순위대로.
 *
 * 서버가 앞에서부터 시도하고, 모델이 없거나(404) 거절당하면 다음으로 내려간다.
 * 이렇게 두면 구글이 모델을 갈아치워도 앱을 새로 배포하지 않아도 되고,
 * 과부하로 한 모델이 막혀도 분석이 통째로 실패하지 않는다.
 */
export const MODEL_CHAIN = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash'] as const;

export type ModelName = (typeof MODEL_CHAIN)[number];
