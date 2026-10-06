// 온디바이스 문자 인식 네이티브 모듈 (Android). 웹·Expo Go 처럼 모듈이 없는 환경에서는 null.
import { requireOptionalNativeModule } from 'expo';

export interface OcrLine {
  text: string;
  /** ML Kit 이 묶은 문단 번호 */
  block: number;
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface OcrResult {
  text: string;
  lines: OcrLine[];
  width: number;
  height: number;
}

interface CardOcrNative {
  recognizeAsync(uri: string): Promise<OcrResult>;
}

const native = requireOptionalNativeModule<CardOcrNative>('CardOcr');

export const isOnDeviceOcrAvailable = native != null;

export function recognizeText(uri: string): Promise<OcrResult> {
  if (!native) {
    return Promise.reject(new Error('이 기기에서는 무료 인식을 쓸 수 없습니다 (안드로이드 설치 앱에서만 동작).'));
  }
  return native.recognizeAsync(uri);
}
