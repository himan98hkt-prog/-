// 명함 목록 저장 (AsyncStorage — 웹에서는 localStorage). 사진은 storage/images 가 따로 보관한다.
import AsyncStorage from '@react-native-async-storage/async-storage';
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
