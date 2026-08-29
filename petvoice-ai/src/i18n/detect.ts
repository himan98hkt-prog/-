import { NativeModules, Platform } from 'react-native';
import type { Locale } from '../core/types';
import { DEFAULT_LOCALE, pickLocale } from './index';

/**
 * 기기 언어 감지.
 *
 * expo-localization 이 있으면 그걸 쓰고, 없으면 React Native 가 노출하는
 * 네이티브 설정에서 읽는다. 둘 다 실패하면 한국어.
 * (감지 실패로 앱이 죽는 것보다 기본값으로 뜨는 편이 낫다)
 */
export function detectDeviceLocale(): Locale {
  const tags = deviceLanguageTags();
  return tags.length > 0 ? pickLocale(tags) : DEFAULT_LOCALE;
}

function deviceLanguageTags(): string[] {
  try {
    const localization = require('expo-localization') as {
      getLocales?: () => { languageTag?: string; languageCode?: string }[];
    };
    const locales = localization.getLocales?.() ?? [];
    const tags = locales.map((l) => l.languageTag ?? l.languageCode ?? '').filter(Boolean);
    if (tags.length > 0) return tags;
  } catch {
    // expo-localization 이 없는 환경은 아래로
  }

  try {
    if (Platform.OS === 'ios') {
      const settings = (NativeModules as { SettingsManager?: { settings?: Record<string, unknown> } })
        .SettingsManager;
      const languages = settings?.settings?.AppleLanguages as string[] | undefined;
      if (languages?.length) return languages;
      const locale = settings?.settings?.AppleLocale as string | undefined;
      if (locale) return [locale];
    } else {
      const i18n = (NativeModules as { I18nManager?: { localeIdentifier?: string } }).I18nManager;
      if (i18n?.localeIdentifier) return [i18n.localeIdentifier];
    }
  } catch {
    // 무시
  }

  return [];
}
