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
  scanDocumentAsync(pageLimit: number): Promise<string[]>;
}

const native = requireOptionalNativeModule<CardOcrNative>('CardOcr');

export const isOnDeviceOcrAvailable = native != null;

export function recognizeText(uri: string): Promise<OcrResult> {
  if (!native) {
    return Promise.reject(new Error('이 기기에서는 무료 인식을 쓸 수 없습니다 (안드로이드 설치 앱에서만 동작).'));
  }
  return native.recognizeAsync(uri);
}

/** 웹에서는 인식 엔진을 미리 받는다 — 앱(ML Kit)은 모델이 내장돼 있어 할 일 없음 */
export function warmUpOcr(): void {}

export const isDocumentScannerAvailable = native != null;

/**
 * Google 문서 스캐너로 명함 촬영 (테두리 자동 인식·원근 보정). pageLimit=2 면 앞·뒷면.
 * 취소하면 빈 배열. Play 서비스가 없는 기기 등에서는 오류 — 호출하는 쪽이 일반 카메라로 대체한다.
 */
export function scanDocument(pageLimit: 1 | 2): Promise<string[]> {
  if (!native) return Promise.reject(new Error('문서 스캐너를 쓸 수 없습니다'));
  return native.scanDocumentAsync(pageLimit);
}
