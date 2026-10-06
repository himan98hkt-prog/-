// 엑셀(CSV)·백업 파일 만들기/공유, 백업 불러오기 — 카톡·메일·드라이브로 바로 보낼 수 있게 공유 창을 연다.
import * as DocumentPicker from 'expo-document-picker';
import { File, Paths } from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import { makeBackup, parseBackup, toCsv } from '../core/exportData';
import { todayStr } from '../core/organize';
import { BusinessCard } from '../core/types';

async function shareText(filename: string, text: string, mimeType: string, dialogTitle: string) {
  const file = new File(Paths.cache, filename);
  if (file.exists) file.delete();
  file.create();
  file.write(text);
  if (!(await Sharing.isAvailableAsync())) throw new Error('이 기기에서는 파일 공유를 쓸 수 없습니다');
  await Sharing.shareAsync(file.uri, { mimeType, dialogTitle });
}

/** 엑셀에서 바로 열리는 명함 목록 (CSV) */
export async function shareCsv(cards: BusinessCard[]) {
  await shareText(`명함스캔-${todayStr()}-${cards.length}명.csv`, toCsv(cards), 'text/csv', '명함 목록 내보내기');
}

/** 휴대폰을 바꾸거나 초기화할 때를 위한 백업 (사진 제외) */
export async function shareBackup(cards: BusinessCard[]) {
  const backup = makeBackup(cards, new Date().toISOString());
  await shareText(`명함스캔-백업-${todayStr()}.json`, JSON.stringify(backup), 'application/json', '명함 백업 저장');
}

/** 백업 파일을 골라 명함 목록으로 (취소하면 null) */
export async function pickBackup(): Promise<BusinessCard[] | null> {
  const res = await DocumentPicker.getDocumentAsync({ type: ['application/json', 'text/plain', '*/*'], copyToCacheDirectory: true });
  if (res.canceled || !res.assets?.length) return null;
  const text = await new File(res.assets[0].uri).text();
  return parseBackup(text);
}
