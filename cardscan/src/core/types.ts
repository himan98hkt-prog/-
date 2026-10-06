// 명함 한 장을 표현하는 앱 내부 모델. 저장소·연동 모듈은 모두 이 타입만 주고받는다.

/** 고객 / 거래처 / 기타 — 연동 대상 시스템을 고르는 기준이 된다. */
export type CardKind = 'customer' | 'partner' | 'other';

export const KIND_LABEL: Record<CardKind, string> = {
  customer: '고객',
  partner: '거래처',
  other: '기타',
};

/** 명함에서 읽어낸 필드. OCR 서버 응답과 수정 화면이 공유한다. */
export interface CardFields {
  name: string;
  nameEn: string;
  company: string;
  department: string;
  title: string;
  mobile: string;
  phone: string;
  fax: string;
  email: string;
  website: string;
  address: string;
  memo: string;
}

export type ConnectorId = 'contacts' | 'webhook' | 'sheets' | 'hubspot' | 'slack';

export type SyncState = 'ok' | 'error' | 'pending';

export interface SyncStatus {
  state: SyncState;
  at: string;
  message?: string;
  /** 연동 시스템 쪽 식별자 (연락처 id, HubSpot contact id 등) — 재전송 시 중복 생성 대신 갱신에 쓴다. */
  remoteId?: string;
}

export interface BusinessCard extends CardFields {
  id: string;
  kind: CardKind;
  createdAt: string;
  updatedAt: string;
  /** 앱 문서 폴더에 복사해 둔 명함 사진 경로 */
  imageUri?: string;
  /** OCR 이 읽은 기타 문구(슬로건, SNS 등) */
  extra: string[];
  sync: Partial<Record<ConnectorId, SyncStatus>>;
}

export const EMPTY_FIELDS: CardFields = {
  name: '',
  nameEn: '',
  company: '',
  department: '',
  title: '',
  mobile: '',
  phone: '',
  fax: '',
  email: '',
  website: '',
  address: '',
  memo: '',
};

export const FIELD_LABEL: Record<keyof CardFields, string> = {
  name: '이름',
  nameEn: '영문 이름',
  company: '회사',
  department: '부서',
  title: '직책',
  mobile: '휴대폰',
  phone: '전화',
  fax: '팩스',
  email: '이메일',
  website: '웹사이트',
  address: '주소',
  memo: '메모',
};
