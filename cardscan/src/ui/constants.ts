// 화면 사이에 공유하는 상수

import { t } from '../i18n';

/** 여러 장 등록에서 인식이 애매했던 명함에 붙는 그룹 (앱 언어로: 확인필요 / To review) */
export const REVIEW_TAG = '확인필요';
export const reviewTag = () => t(REVIEW_TAG);
/** 두 언어의 확인필요 그룹 — 최근 태그 추천에서 뺀다 */
export const isReviewTag = (tag: string) => tag === REVIEW_TAG || tag === t(REVIEW_TAG, undefined, 'en');

/** 개인정보처리방침 (아이폰 웹앱과 같은 GitHub Pages 사이트, cardscan/store/privacy-policy.html) */
export const PRIVACY_URL = 'https://himan98hkt-prog.github.io/-/privacy.html';

/** 문의·오류 신고 (GitHub 이슈) */
export const SUPPORT_URL = 'https://github.com/himan98hkt-prog/-/issues';
