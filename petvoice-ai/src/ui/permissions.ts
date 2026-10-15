import { Alert, Linking } from 'react-native';
import type { Translator } from '../i18n/useT';

/**
 * Google Play 정책: 카메라/마이크/갤러리/알림은 **권한이 필요한 시점에**
 * 왜 필요한지 먼저 설명하고 나서 시스템 권한을 요청해야 한다.
 * 모든 권한 요청은 이 함수를 거친다.
 */
export type PermissionKind = 'mic' | 'camera' | 'photos' | 'notifications';

export interface PermissionResult {
  granted: boolean;
  canAskAgain?: boolean;
}

/** 용도 설명 팝업. 사용자가 '계속'을 누르면 true */
export function explainPermission(kind: PermissionKind, tr: Translator): Promise<boolean> {
  return new Promise((resolve) => {
    Alert.alert(tr.t(`permissions.${kind}.title`), tr.t(`permissions.${kind}.message`), [
      { text: tr.t('common.later'), style: 'cancel', onPress: () => resolve(false) },
      { text: tr.t('common.continue'), onPress: () => resolve(true) },
    ]);
  });
}

/**
 * 설명 → 시스템 권한 요청 → 거부 시 설정 안내까지 한 번에.
 * `requester` 는 expo-av / expo-camera / expo-image-picker / expo-notifications 의 요청 함수.
 */
export async function requestWithRationale(
  kind: PermissionKind,
  requester: () => Promise<PermissionResult>,
  tr: Translator,
): Promise<boolean> {
  const proceed = await explainPermission(kind, tr);
  if (!proceed) return false;

  const result = await requester();
  if (result.granted) return true;

  if (result.canAskAgain === false) {
    Alert.alert(tr.t('permissions.deniedTitle'), tr.t('permissions.deniedMessage'), [
      { text: tr.t('common.close'), style: 'cancel' },
      { text: tr.t('common.openSettings'), onPress: () => void Linking.openSettings() },
    ]);
  }
  return false;
}
