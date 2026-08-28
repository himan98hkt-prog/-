import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';
import * as ImagePicker from 'expo-image-picker';
import { requestWithRationale } from './permissions';

/** 지시서의 '3초 소리 녹음' */
export const RECORD_SECONDS = 3;

/** 5MB 넘는 파일은 프록시에서 거절되므로 미리 막는다. */
export const MAX_BASE64_BYTES = 5 * 1024 * 1024;

export async function toBase64(uri: string): Promise<string> {
  return FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 });
}

export async function fileTooLarge(uri: string): Promise<boolean> {
  const info = await FileSystem.getInfoAsync(uri, { size: true });
  return info.exists && typeof info.size === 'number' && info.size > MAX_BASE64_BYTES;
}

/** 녹음 세션 핸들 */
export interface RecordingHandle {
  stop: () => Promise<string | null>;
}

/** 마이크 권한 설명 → 요청 → 녹음 시작 */
export async function startRecording(): Promise<RecordingHandle | null> {
  const ok = await requestWithRationale('mic', async () => {
    const res = await Audio.requestPermissionsAsync();
    return { granted: res.granted, canAskAgain: res.canAskAgain };
  });
  if (!ok) return null;

  await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });

  const { recording } = await Audio.Recording.createAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);

  let stopped = false;
  return {
    stop: async () => {
      if (stopped) return null;
      stopped = true;
      try {
        await recording.stopAndUnloadAsync();
      } catch {
        // 이미 정지된 경우는 무시
      }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: false });
      return recording.getURI();
    },
  };
}

/** 갤러리에서 반려동물 사진 고르기 */
export async function pickPhoto(): Promise<string | null> {
  const ok = await requestWithRationale('photos', async () => {
    const res = await ImagePicker.requestMediaLibraryPermissionsAsync();
    return { granted: res.granted, canAskAgain: res.canAskAgain };
  });
  if (!ok) return null;

  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ImagePicker.MediaTypeOptions.Images,
    quality: 0.7,
    // 포토카드가 4:5 라 자를 때부터 맞춰 둔다
    allowsEditing: true,
    aspect: [4, 5],
  });
  if (result.canceled) return null;
  return result.assets[0]?.uri ?? null;
}
