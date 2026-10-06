// 명함 사진 받기 — 문서 스캐너(테두리 자동·원근 보정) → 안 되면 일반 카메라, 앨범 한 장/여러 장.
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import * as ImagePicker from 'expo-image-picker';
import { isDocumentScannerAvailable, scanDocument } from '../../modules/card-ocr';

export interface CapturedImage {
  uri: string;
  base64: string;
}

export interface CapturedCard {
  front: CapturedImage;
  /** 뒷면(영문면 등) — 앞·뒷면 촬영을 켰을 때만 */
  back?: CapturedImage;
}

const PICK_OPTIONS: ImagePicker.ImagePickerOptions = {
  mediaTypes: ['images'],
  // 기본 자르기 화면으로 명함 테두리에 맞출 수 있게 한다
  allowsEditing: true,
  quality: 1,
};

/** 문서 스캐너가 실패했던 기기는 다음부터 바로 일반 카메라로 */
let scannerBroken = false;

export async function captureCard(source: 'camera' | 'library', withBack = false): Promise<CapturedCard | null> {
  if (source === 'camera' && isDocumentScannerAvailable && !scannerBroken) {
    try {
      const pages = await scanDocument(withBack ? 2 : 1);
      if (!pages.length) return null; // 사용자가 취소
      const front = await prepareImage(pages[0]);
      const back = pages[1] ? await prepareImage(pages[1]) : undefined;
      return { front, back };
    } catch {
      scannerBroken = true; // Play 서비스 없음 등 — 일반 카메라로 계속
    }
  }
  if (source === 'camera') {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) throw new Error('카메라 권한이 필요합니다. 설정에서 카메라 접근을 허용하세요.');
  }
  const result =
    source === 'camera' ? await ImagePicker.launchCameraAsync(PICK_OPTIONS) : await ImagePicker.launchImageLibraryAsync(PICK_OPTIONS);
  if (result.canceled || !result.assets?.length) return null;
  return { front: await prepareImage(result.assets[0].uri, result.assets[0].width) };
}

/** 앨범에서 명함 사진 여러 장을 한 번에 (최대 50장) — 쌓여 있던 명함을 한꺼번에 등록 */
export async function pickManyCards(): Promise<string[]> {
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'],
    allowsMultipleSelection: true,
    selectionLimit: 50,
    orderedSelection: true,
    quality: 1,
  });
  if (result.canceled) return [];
  return result.assets.map((a) => a.uri);
}

/** 긴 변 1600px JPEG — 글자 인식에 충분하고 보관 용량은 수백 KB 수준 */
export async function prepareImage(uri: string, width?: number): Promise<CapturedImage> {
  const ctx = ImageManipulator.manipulate(uri);
  if (!width || width > 1600) ctx.resize({ width: 1600 });
  const ref = await ctx.renderAsync();
  const saved = await ref.saveAsync({ base64: true, compress: 0.8, format: SaveFormat.JPEG });
  if (!saved.base64) throw new Error('이미지 변환에 실패했습니다');
  return { uri: saved.uri, base64: saved.base64 };
}
