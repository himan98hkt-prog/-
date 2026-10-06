// 다국어 — 한국어 문장 자체를 열쇠로 쓴다 (t('명함 촬영') → 영어 사전에서 찾고, 없으면 한국어 그대로).
// 화면 코드를 읽을 때 무슨 문구인지 바로 보이고, tests/i18n.test.ts 가 영어 번역 누락을 잡아 준다.
import { EN } from './en';

export type Lang = 'ko' | 'en';
/** 설정 값 — auto 는 휴대폰 언어를 따른다 */
export type LangSetting = 'auto' | Lang;

let current: Lang = 'ko';

export function setLang(lang: Lang) {
  current = lang;
}

export function getLang(): Lang {
  return current;
}

/** 휴대폰 언어 코드 → 앱 언어 (한국어가 아니면 영어) */
export function langFromCode(code: string | null | undefined): Lang {
  return code?.toLowerCase().startsWith('ko') ? 'ko' : 'en';
}

export function resolveLang(setting: LangSetting | undefined, deviceCode: string | null | undefined): Lang {
  return setting === 'ko' || setting === 'en' ? setting : langFromCode(deviceCode);
}

/** 번역 — {이름} 자리는 params 로 채운다: t('{n}장 저장', { n: 3 }) */
export function t(ko: string, params?: Record<string, string | number>, lang: Lang = current): string {
  let s = lang === 'en' ? (EN[ko] ?? ko) : ko;
  if (params) for (const [k, v] of Object.entries(params)) s = s.split(`{${k}}`).join(String(v));
  return s;
}
