// 앱에서 쓰는 다국어 입구 — 휴대폰 언어 감지 포함
import { getLocales } from 'expo-localization';
import { LangSetting, resolveLang, setLang } from './core';

export { getLang, t } from './core';
export type { Lang, LangSetting } from './core';

export function deviceLanguageCode(): string | null {
  try {
    return getLocales()[0]?.languageCode ?? null;
  } catch {
    return null;
  }
}

/** 휴대폰 지역 (US, GB, KR …) — 명함 전화번호 해석에 쓴다 */
export function deviceRegion(): string | undefined {
  try {
    return getLocales()[0]?.regionCode ?? undefined;
  } catch {
    return undefined;
  }
}

/** 설정·휴대폰 언어로 앱 언어를 정해 적용하고 돌려준다 */
export function applyLanguage(setting: LangSetting | undefined) {
  const lang = resolveLang(setting, deviceLanguageCode());
  setLang(lang);
  return lang;
}

// 첫 화면부터 휴대폰 언어로 (설정을 불러오면 다시 맞춘다)
applyLanguage('auto');
