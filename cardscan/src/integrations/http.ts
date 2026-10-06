// HTTP 기반 연동 — fetch 를 주입받아 단위 테스트에서 가짜 응답으로 검증한다.
import { toHubSpotProperties, toSheetRow, toSlackMessage, toWebhookPayload, SHEET_HEADERS } from '../core/mapping';
import { t } from '../i18n/core';
import { Settings } from '../core/settings';
import { BusinessCard, SyncStatus } from '../core/types';

export type Fetch = typeof fetch;

export interface ConnectorContext {
  settings: Settings;
  fetch: Fetch;
  /** 이 연동으로 이전에 보낸 기록 — 있으면 새로 만들지 않고 갱신한다 */
  previous?: SyncStatus;
}

export interface ConnectorResult {
  remoteId?: string;
  message?: string;
}

export type Connector = (card: BusinessCard, ctx: ConnectorContext) => Promise<ConnectorResult>;

async function readError(res: Response): Promise<string> {
  let body = '';
  try {
    body = (await res.text()).slice(0, 300);
  } catch {
    // 본문을 못 읽어도 상태 코드만으로 충분하다
  }
  return `HTTP ${res.status}${body ? ` — ${body}` : ''}`;
}

export const webhookConnector: Connector = async (card, { settings, fetch, previous }) => {
  const { url, secret } = settings.connectors.webhook;
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (secret) headers['X-CardScan-Secret'] = secret;
  const event = previous?.state === 'ok' ? 'card.updated' : 'card.created';
  const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify(toWebhookPayload(card, event)) });
  if (!res.ok) throw new Error(await readError(res));
  return { remoteId: card.id };
};

/** Google Apps Script 웹 앱(docs/google-sheets.gs)에 행 추가/갱신 */
export const sheetsConnector: Connector = async (card, { settings, fetch }) => {
  const { url, secret } = settings.connectors.sheets;
  // Apps Script 는 Content-Type: application/json 이면 CORS 사전요청 문제를 일으킬 수 있어 text/plain 으로 보낸다
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'text/plain;charset=utf-8' },
    body: JSON.stringify({ secret, id: card.id, headers: SHEET_HEADERS, row: toSheetRow(card) }),
  });
  if (!res.ok) throw new Error(await readError(res));
  const text = await res.text();
  let data: { ok?: boolean; error?: string; row?: number } = {};
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error(t('구글 시트 응답을 읽을 수 없습니다. 웹 앱 배포 시 "액세스 권한: 모든 사용자"인지 확인하세요.'));
  }
  if (!data.ok) throw new Error(data.error || t('구글 시트 저장 실패'));
  return { remoteId: card.id, message: data.row ? t('{1}행', { 1: data.row }) : undefined };
};

const HUBSPOT = 'https://api.hubapi.com/crm/v3/objects/contacts';

export const hubspotConnector: Connector = async (card, { settings, fetch, previous }) => {
  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${settings.connectors.hubspot.token}` };
  const body = JSON.stringify({ properties: toHubSpotProperties(card) });

  const patch = async (id: string): Promise<ConnectorResult> => {
    const res = await fetch(`${HUBSPOT}/${encodeURIComponent(id)}`, { method: 'PATCH', headers, body });
    if (!res.ok) throw new Error(await readError(res));
    return { remoteId: id, message: t('기존 연락처 갱신') };
  };

  if (previous?.remoteId) {
    try {
      return await patch(previous.remoteId);
    } catch (e) {
      // HubSpot 에서 지워진 경우엔 아래에서 새로 만든다
      if (!String((e as Error).message).startsWith('HTTP 404')) throw e;
    }
  }

  const res = await fetch(HUBSPOT, { method: 'POST', headers, body });
  if (res.status === 409) {
    // 같은 이메일의 연락처가 이미 있음 → "Existing ID: 123" 을 찾아 갱신
    const text = await res.text();
    const m = text.match(/Existing ID:\s*(\d+)/i);
    if (m) return patch(m[1]);
    throw new Error(`HTTP 409 — ${text.slice(0, 300)}`);
  }
  if (!res.ok) throw new Error(await readError(res));
  const data = (await res.json()) as { id?: string };
  return { remoteId: data.id };
};

/** 슬랙은 알림용 — 처음 등록될 때만 보낸다 */
export const slackConnector: Connector = async (card, { settings, fetch, previous }) => {
  if (previous?.state === 'ok') return { remoteId: previous.remoteId, message: t('이미 알림 보냄') };
  const res = await fetch(settings.connectors.slack.url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(toSlackMessage(card)),
  });
  if (!res.ok) throw new Error(await readError(res));
  return { remoteId: 'sent' };
};
