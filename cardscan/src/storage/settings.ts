// 설정 저장 — 일반 값은 AsyncStorage, 토큰·비밀키는 기기 보안 저장소(Keychain/Keystore)에 따로 둔다.
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { DEFAULT_SETTINGS, getPath, mergeSettings, SECRET_PATHS, setPath, Settings } from '../core/settings';

const KEY = 'cardscan:settings:v1';
const secretKey = (path: string) => `cardscan.${path}`; // SecureStore 키는 영숫자 . - _ 만 허용
// 웹 미리보기에는 보안 저장소가 없어 비밀값도 일반 저장소에 둔다 (휴대폰 앱에서는 항상 SecureStore)
const useSecure = Platform.OS !== 'web';

export async function loadSettings(): Promise<Settings> {
  let settings = DEFAULT_SETTINGS;
  try {
    const raw = await AsyncStorage.getItem(KEY);
    settings = mergeSettings(raw ? JSON.parse(raw) : {});
  } catch {
    settings = mergeSettings({});
  }
  if (!useSecure) return settings;
  for (const path of SECRET_PATHS) {
    const v = await SecureStore.getItemAsync(secretKey(path));
    if (v != null) settings = setPath(settings, path, v);
  }
  return settings;
}

export async function saveSettings(settings: Settings): Promise<void> {
  if (!useSecure) return AsyncStorage.setItem(KEY, JSON.stringify(settings));
  let plain = settings;
  for (const path of SECRET_PATHS) {
    const v = String(getPath(settings, path) ?? '');
    if (v) await SecureStore.setItemAsync(secretKey(path), v);
    else await SecureStore.deleteItemAsync(secretKey(path));
    plain = setPath(plain, path, '');
  }
  await AsyncStorage.setItem(KEY, JSON.stringify(plain));
}
