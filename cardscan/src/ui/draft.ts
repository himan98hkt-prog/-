// 촬영 → 확인 화면 사이에 넘기는 임시 데이터. 라우트 파라미터에 큰 값을 싣지 않으려고 메모리에 둔다.
import { CardFields, CardKind } from '../core/types';

export interface Draft {
  fields: CardFields;
  kind: CardKind;
  extra: string[];
  imageUri?: string;
  backImageUri?: string;
  note?: string;
  error?: string;
}

let current: Draft | null = null;

export function setDraft(d: Draft) {
  current = d;
}

export function takeDraft(): Draft | null {
  return current;
}

export function clearDraft() {
  current = null;
}
