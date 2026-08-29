import { Platform } from 'react-native';

/**
 * 테스트 전용 Gemini 키 보관소.
 *
 * ⚠️ 이건 **제품 구조가 아닙니다.** 출시 앱은 키를 서버(Edge Function)에만 두고
 * 클라이언트는 사용자 토큰만 들고 다닙니다. 그 원칙은 그대로입니다.
 *
 * 다만 "우리 개 짖는 소리를 진짜로 넣어 보고 싶다"를 하려면
 * Supabase 프로젝트 생성 → 스키마 적용 → 함수 4개 배포를 먼저 해야 합니다.
 * 정확도를 한번 재 보려는 사람에게 그 문턱은 너무 높습니다.
 *
 * 그래서 **본인 기기에 본인 키를 직접 넣어** 잠깐 확인해 보는 길을 따로 둡니다.
 * 대신 세 가지로 가둡니다.
 *  1. 빌드 플래그가 켜진 빌드에서만 코드가 살아납니다 (프로덕션 프로필은 끕니다)
 *  2. 키는 번들에 절대 들어가지 않습니다 — 사용자가 실행 중에 입력합니다
 *  3. 기기 보안 저장소에 넣습니다 (AsyncStorage 아님)
 */

/** 테스트 모드가 이 빌드에서 허용되는가. eas.json 의 프로필이 정한다. */
export const DIRECT_KEY_ALLOWED = process.env.EXPO_PUBLIC_ALLOW_DIRECT_KEY === '1';

const STORE_KEY = 'petvoice_test_gemini_key';

type SecureStoreModule = {
  getItemAsync: (key: string) => Promise<string | null>;
  setItemAsync: (key: string, value: string) => Promise<void>;
  deleteItemAsync: (key: string) => Promise<void>;
};

let store: SecureStoreModule | null | undefined;

function secureStore(): SecureStoreModule | null {
  if (store !== undefined) return store;
  if (Platform.OS !== 'android' && Platform.OS !== 'ios') {
    // 웹에는 안전한 보관소가 없다. 키를 평문으로 두느니 기능을 끈다.
    store = null;
    return null;
  }
  try {
    const mod = require('expo-secure-store') as Partial<SecureStoreModule> | undefined;
    store = typeof mod?.getItemAsync === 'function' ? (mod as SecureStoreModule) : null;
  } catch {
    store = null;
  }
  return store;
}

export function isTestKeyUsable(): boolean {
  return DIRECT_KEY_ALLOWED && secureStore() !== null;
}

export async function getTestKey(): Promise<string | null> {
  if (!isTestKeyUsable()) return null;
  try {
    const value = await secureStore()!.getItemAsync(STORE_KEY);
    return value?.trim() || null;
  } catch {
    return null;
  }
}

export async function setTestKey(key: string): Promise<void> {
  const mod = secureStore();
  if (!DIRECT_KEY_ALLOWED || !mod) return;
  const trimmed = key.trim();
  if (trimmed) await mod.setItemAsync(STORE_KEY, trimmed);
  else await mod.deleteItemAsync(STORE_KEY).catch(() => undefined);
}

export async function clearTestKey(): Promise<void> {
  const mod = secureStore();
  if (!mod) return;
  await mod.deleteItemAsync(STORE_KEY).catch(() => undefined);
}

/** 키 전체를 화면에 다시 보여 주지 않는다. 들어 있다는 것만 알린다. */
export function maskKey(key: string): string {
  if (key.length <= 8) return '••••';
  return `${key.slice(0, 4)}••••${key.slice(-4)}`;
}
