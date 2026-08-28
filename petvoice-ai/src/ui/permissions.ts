import { Alert, Linking } from 'react-native';

/**
 * Google Play 정책: 카메라/마이크/갤러리는 **권한이 필요한 시점에**
 * 왜 필요한지 먼저 설명하고 나서 시스템 권한을 요청해야 한다.
 * 모든 권한 요청은 이 함수를 거친다.
 */
export type PermissionKind = 'mic' | 'camera' | 'photos';

const COPY: Record<PermissionKind, { title: string; message: string }> = {
  mic: {
    title: '마이크 권한이 필요해요',
    message:
      '반려동물의 울음소리를 3초간 녹음해 감정을 분석하는 데만 사용합니다.\n녹음 파일은 분석 후 기기 안에만 남고, 분석 목적 외에는 사용하지 않습니다.',
  },
  camera: {
    title: '카메라 권한이 필요해요',
    message:
      '반려동물의 자세와 표정을 촬영해 행동을 분석하는 데만 사용합니다.\n촬영한 사진은 분석과 포토카드 만들기에만 쓰입니다.',
  },
  photos: {
    title: '사진 접근 권한이 필요해요',
    message: '이미 찍어 둔 반려동물 사진으로 분석하거나 포토카드를 만들기 위해 사용합니다.',
  },
};

export interface PermissionResult {
  granted: boolean;
  canAskAgain?: boolean;
}

/** 용도 설명 팝업. 사용자가 '계속'을 누르면 true */
export function explainPermission(kind: PermissionKind): Promise<boolean> {
  const copy = COPY[kind];
  return new Promise((resolve) => {
    Alert.alert(copy.title, copy.message, [
      { text: '나중에', style: 'cancel', onPress: () => resolve(false) },
      { text: '계속', onPress: () => resolve(true) },
    ]);
  });
}

/**
 * 설명 → 시스템 권한 요청 → 거부 시 설정 안내까지 한 번에.
 * `requester` 는 expo-av / expo-camera / expo-image-picker 의 요청 함수.
 */
export async function requestWithRationale(
  kind: PermissionKind,
  requester: () => Promise<PermissionResult>,
): Promise<boolean> {
  const proceed = await explainPermission(kind);
  if (!proceed) return false;

  const result = await requester();
  if (result.granted) return true;

  if (result.canAskAgain === false) {
    Alert.alert(
      '권한이 꺼져 있어요',
      '기기 설정에서 권한을 켜면 바로 사용할 수 있습니다.',
      [
        { text: '닫기', style: 'cancel' },
        { text: '설정 열기', onPress: () => void Linking.openSettings() },
      ],
    );
  }
  return false;
}
