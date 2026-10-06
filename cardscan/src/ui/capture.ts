// 카메라/앨범에서 명함 사진을 받아 인식 서버에 보낼 크기로 줄인다.
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import * as ImagePicker from 'expo-image-picker';

export interface CapturedImage {
  uri: string;
  base64: string;
}

const PICK_OPTIONS: ImagePicker.ImagePickerOptions = {
  mediaTypes: ['images'],
  // 기본 자르기 화면으로 명함 테두리에 맞출 수 있게 한다
  allowsEditing: true,
  quality: 1,
};

export async function captureCard(source: 'camera' | 'library'): Promise<CapturedImage | null> {
  if (source === 'camera') {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) throw new Error('카메라 권한이 필요합니다. 설정에서 카메라 접근을 허용하세요.');
  }
  const result =
    source === 'camera' ? await ImagePicker.launchCameraAsync(PICK_OPTIONS) : await ImagePicker.launchImageLibraryAsync(PICK_OPTIONS);
  if (result.canceled || !result.assets?.length) return null;
  return prepareImage(result.assets[0].uri, result.assets[0].width);
}

/** 긴 변 1600px JPEG — 글자 인식에 충분하고 업로드는 수백 KB 수준 */
export async function prepareImage(uri: string, width?: number): Promise<CapturedImage> {
  const ctx = ImageManipulator.manipulate(uri);
  if (width && width > 1600) ctx.resize({ width: 1600 });
  const ref = await ctx.renderAsync();
  const saved = await ref.saveAsync({ base64: true, compress: 0.8, format: SaveFormat.JPEG });
  if (!saved.base64) throw new Error('이미지 변환에 실패했습니다');
  return { uri: saved.uri, base64: saved.base64 };
}
