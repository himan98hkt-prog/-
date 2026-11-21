// 명함 사진 보관 — 휴대폰 앱: 앱 문서 폴더의 JPEG 파일. (웹은 images.web.ts)
import { useMemo } from 'react';
import { Directory, File, Paths } from 'expo-file-system';

function imageDir(): Directory {
  const dir = new Directory(Paths.document, 'cards');
  if (!dir.exists) dir.create({ intermediates: true });
  return dir;
}

/** 카메라 임시 파일은 OS 가 지울 수 있으므로 앱 문서 폴더로 옮겨 둔다. */
export async function persistImage(tempUri: string, key: string): Promise<string> {
  const dest = new File(imageDir(), `${key}.jpg`);
  if (dest.exists) dest.delete();
  await new File(tempUri).copy(dest);
  return dest.uri;
}

export function deleteImage(uri?: string) {
  if (!uri) return;
  try {
    const f = new File(uri);
    if (f.exists) f.delete();
  } catch {
    // 이미 없으면 무시
  }
}

/** 화면에 띄울 주소 — 앱에서는 파일 경로를 그대로 쓴다 */
export function useImageUri(uri?: string): string | undefined {
  return useMemo(() => uri, [uri]);
}
