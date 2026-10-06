// 앱 설정 모델 — 저장 방식(AsyncStorage/SecureStore)과 분리해 기본값·검증만 둔다.
import { CardFields, CardKind, ConnectorId, EMPTY_FIELDS } from './types';

export interface ConnectorBase {
  enabled: boolean;
  /** 이 구분의 명함만 이 시스템으로 보낸다 (예: 거래처만 ERP 로) */
  kinds: CardKind[];
}

export interface Settings {
  ocr: {
    /**
     * device: 휴대폰 안에서 인식 (Google ML Kit + 규칙 분석) — 무료·오프라인, 기본값
     * direct: Claude API 직접 호출 — 유료(장당 소액), 흐리거나 디자인이 복잡한 명함에 더 정확
     * server: 내 서버(Supabase Edge Function) 경유 Claude — 유료, 키를 휴대폰에 두지 않음
     */
    mode: 'device' | 'direct' | 'server';
    /** direct 모드의 Anthropic API 키 (기기 보안 저장소에 보관) */
    apiKey: string;
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
  /**
   * 휴대폰 연락처에 저장할 이름 모양 — 전화가 오면 기본 전화 앱에 회사·직책이 함께 뜬다.
   * name: 홍길동 / company: 홍길동 (한빛상사) / companyTitle: 홍길동 (한빛상사 팀장)
   */
  contactName: 'name' | 'company' | 'companyTitle';
  /** 팔로업 날짜 아침 9시에 알림 */
  followUpNotify: boolean;
  /** 행사·모임 태그 — 켜 두면 이후 찍는 명함마다 자동으로 붙는다 (예: 2026 코엑스 전시회) */
  scanTag: string;
  /** 연속 촬영 — 저장하자마자 다음 명함 촬영 화면을 바로 연다 */
  continuousScan: boolean;
  /** 내 명함 — QR·공유용 */
  myCard: CardFields;
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
  ocr: { mode: 'device', apiKey: '', endpoint: '', anonKey: '', appSecret: '' },
  autoSave: true,
  defaultKind: 'customer',
  contactName: 'company',
  followUpNotify: true,
  scanTag: '',
  continuousScan: false,
  myCard: { ...EMPTY_FIELDS },
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
  'ocr.apiKey',
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
    ocr: {
      ...base.ocr,
      // 간편 모드가 생기기 전 버전에서 서버 주소를 넣어 둔 사용자는 서버 모드를 유지
      ...(s.ocr && !('mode' in s.ocr) && (s.ocr as { endpoint?: string }).endpoint ? { mode: 'server' as const } : {}),
      ...(s.ocr ?? {}),
    },
    connectors,
    myCard: { ...base.myCard, ...((s.myCard as object | undefined) ?? {}) },
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

/**
 * 이 기기에서 자동 전송이 안 되는 연동. 웹(아이폰 홈 화면 웹앱)은 연락처에 직접 쓸 수 없고,
 * HubSpot·슬랙은 브라우저 보안(CORS) 때문에 직접 호출이 막혀 있다 — 앱 시작 시 ui/platform 이 설정.
 */
let unavailable = new Set<ConnectorId>();
export function setUnavailableConnectors(ids: ConnectorId[]) {
  unavailable = new Set(ids);
}
export function connectorAvailable(id: ConnectorId): boolean {
  return !unavailable.has(id);
}

export function connectorTargets(settings: Settings, kind: CardKind): ConnectorId[] {
  return CONNECTOR_ORDER.filter((id) => connectorAvailable(id) && connectorReady(settings, id) && settings.connectors[id].kinds.includes(kind));
}

/** 실제로 쓸 인식 방식 — 유료 모드를 골랐어도 키가 없으면 무료(기기) 인식으로 동작 */
export function effectiveOcrMode(settings: Settings): Settings['ocr']['mode'] {
  const o = settings.ocr;
  if (o.mode === 'direct' && !o.apiKey.startsWith('sk-ant-')) return 'device';
  if (o.mode === 'server' && !(/^https:\/\//.test(o.endpoint) && o.appSecret)) return 'device';
  return o.mode;
}
