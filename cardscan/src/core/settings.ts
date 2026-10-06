// 앱 설정 모델 — 저장 방식(AsyncStorage/SecureStore)과 분리해 기본값·검증만 둔다.
import { CardKind, ConnectorId } from './types';

export interface ConnectorBase {
  enabled: boolean;
  /** 이 구분의 명함만 이 시스템으로 보낸다 (예: 거래처만 ERP 로) */
  kinds: CardKind[];
}

export interface Settings {
  ocr: {
    /** Supabase Edge Function 주소 — https://<project>.supabase.co/functions/v1/scan-card */
    endpoint: string;
    /** Supabase anon/publishable key (선택 — 게이트웨이가 요구할 때만) */
    anonKey: string;
    /** 서버 함수의 APP_SHARED_SECRET 과 같은 값 */
    appSecret: string;
  };
  /** 인식 결과가 충분하면 확인 화면 없이 바로 저장·연동 */
  autoSave: boolean;
  /** 촬영 화면의 기본 구분 */
  defaultKind: CardKind;
  connectors: {
    contacts: ConnectorBase;
    webhook: ConnectorBase & { url: string; secret: string };
    sheets: ConnectorBase & { url: string; secret: string };
    hubspot: ConnectorBase & { token: string };
    slack: ConnectorBase & { url: string };
  };
}

const ALL_KINDS: CardKind[] = ['customer', 'partner', 'other'];

export const DEFAULT_SETTINGS: Settings = {
  ocr: { endpoint: '', anonKey: '', appSecret: '' },
  autoSave: true,
  defaultKind: 'customer',
  connectors: {
    contacts: { enabled: true, kinds: [...ALL_KINDS] },
    webhook: { enabled: false, kinds: [...ALL_KINDS], url: '', secret: '' },
    sheets: { enabled: false, kinds: [...ALL_KINDS], url: '', secret: '' },
    hubspot: { enabled: false, kinds: ['customer'], token: '' },
    slack: { enabled: false, kinds: [...ALL_KINDS], url: '' },
  },
};

export const CONNECTOR_LABEL: Record<ConnectorId, string> = {
  contacts: '휴대폰 연락처',
  webhook: '웹훅 (ERP·그룹웨어·Zapier·Make·n8n)',
  sheets: '구글 시트',
  hubspot: 'HubSpot CRM',
  slack: '슬랙 알림',
};

export const CONNECTOR_ORDER: ConnectorId[] = ['contacts', 'sheets', 'hubspot', 'webhook', 'slack'];

/** SecureStore 로 따로 보관할 비밀값 경로 */
export const SECRET_PATHS = [
  'ocr.anonKey',
  'ocr.appSecret',
  'connectors.webhook.secret',
  'connectors.sheets.secret',
  'connectors.hubspot.token',
  'connectors.slack.url',
] as const;
export type SecretPath = (typeof SECRET_PATHS)[number];

export function getPath(obj: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((o, k) => (o && typeof o === 'object' ? (o as Record<string, unknown>)[k] : undefined), obj);
}

export function setPath<T>(obj: T, path: string, value: unknown): T {
  const keys = path.split('.');
  const clone = JSON.parse(JSON.stringify(obj)) as Record<string, unknown>;
  let cur = clone;
  for (const k of keys.slice(0, -1)) {
    cur[k] = { ...(cur[k] as Record<string, unknown>) };
    cur = cur[k] as Record<string, unknown>;
  }
  cur[keys[keys.length - 1]] = value;
  return clone as T;
}

/** 저장돼 있던 (구버전일 수 있는) 설정을 기본값 위에 덮어써서 빠진 키를 채운다. */
export function mergeSettings(saved: unknown): Settings {
  const s = (saved && typeof saved === 'object' ? saved : {}) as Partial<Settings>;
  const base: Settings = JSON.parse(JSON.stringify(DEFAULT_SETTINGS));
  const connectors = { ...base.connectors };
  for (const id of Object.keys(connectors) as ConnectorId[]) {
    const savedConn = (s.connectors as Record<string, unknown> | undefined)?.[id];
    if (savedConn && typeof savedConn === 'object') {
      (connectors as Record<string, unknown>)[id] = { ...connectors[id], ...(savedConn as object) };
    }
  }
  return {
    ...base,
    ...s,
    ocr: { ...base.ocr, ...(s.ocr ?? {}) },
    connectors,
  };
}

/** 연동 설정이 실제로 동작할 수 있는 상태인지 — 화면 표시와 동기화 대상 선정에 같이 쓴다. */
export function connectorReady(settings: Settings, id: ConnectorId): boolean {
  const c = settings.connectors;
  switch (id) {
    case 'contacts':
      return c.contacts.enabled;
    case 'webhook':
      return c.webhook.enabled && /^https:\/\//.test(c.webhook.url);
    case 'sheets':
      return c.sheets.enabled && /^https:\/\/script\.google\.com\//.test(c.sheets.url);
    case 'hubspot':
      return c.hubspot.enabled && c.hubspot.token.length > 10;
    case 'slack':
      return c.slack.enabled && /^https:\/\/hooks\.slack\.com\//.test(c.slack.url);
  }
}

export function connectorTargets(settings: Settings, kind: CardKind): ConnectorId[] {
  return CONNECTOR_ORDER.filter((id) => connectorReady(settings, id) && settings.connectors[id].kinds.includes(kind));
}
