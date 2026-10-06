// 명함 목록 저장 (AsyncStorage) + 명함 사진 파일 보관 (앱 문서 폴더)
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Directory, File, Paths } from 'expo-file-system';
import { BusinessCard } from '../core/types';

const KEY = 'cardscan:cards:v1';

export async function loadCards(): Promise<BusinessCard[]> {
  const raw = await AsyncStorage.getItem(KEY);
  if (!raw) return [];
  try {
    const list = JSON.parse(raw);
    return Array.isArray(list) ? (list as BusinessCard[]) : [];
  } catch {
    return [];
  }
}

export async function saveCards(cards: BusinessCard[]): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(cards));
}

function imageDir(): Directory {
  const dir = new Directory(Paths.document, 'cards');
  if (!dir.exists) dir.create({ intermediates: true });
  return dir;
}

/** 카메라 임시 파일은 OS 가 지울 수 있으므로 앱 문서 폴더로 옮겨 둔다. */
export async function persistImage(tempUri: string, cardId: string): Promise<string> {
  const dest = new File(imageDir(), `${cardId}.jpg`);
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
