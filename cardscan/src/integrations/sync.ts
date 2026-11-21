// 한 장의 명함을 설정된 모든 시스템에 보낸다. 하나가 실패해도 나머지는 계속 진행한다.
import { connectorTargets, Settings } from '../core/settings';
import { t } from '../i18n/core';
import { BusinessCard, ConnectorId, SyncStatus } from '../core/types';
import { Connector, Fetch, hubspotConnector, sheetsConnector, slackConnector, webhookConnector } from './http';

export type ConnectorMap = Record<ConnectorId, Connector>;

export const HTTP_CONNECTORS: Omit<ConnectorMap, 'contacts'> = {
  webhook: webhookConnector,
  sheets: sheetsConnector,
  hubspot: hubspotConnector,
  slack: slackConnector,
};

export interface SyncOptions {
  settings: Settings;
  connectors: ConnectorMap;
  fetch: Fetch;
  /** 특정 연동만 다시 보낼 때 (재시도 버튼) */
  only?: ConnectorId[];
  now?: () => string;
}

export async function syncCard(card: BusinessCard, opts: SyncOptions): Promise<BusinessCard['sync']> {
  const now = opts.now ?? (() => new Date().toISOString());
  let targets = connectorTargets(opts.settings, card.kind);
  if (opts.only) targets = targets.filter((t) => opts.only!.includes(t));

  const results = await Promise.allSettled(
    targets.map((id) =>
      opts.connectors[id](card, { settings: opts.settings, fetch: opts.fetch, previous: card.sync[id] }),
    ),
  );

  const sync: BusinessCard['sync'] = { ...card.sync };
  results.forEach((r, i) => {
    const id = targets[i];
    const prev = card.sync[id];
    const status: SyncStatus =
      r.status === 'fulfilled'
        ? { state: 'ok', at: now(), remoteId: r.value.remoteId ?? prev?.remoteId, message: r.value.message }
        : { state: 'error', at: now(), remoteId: prev?.remoteId, message: errorText(r.reason) };
    sync[id] = status;
  });
  return sync;
}

function errorText(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e);
  if (/Network request failed|Failed to fetch/i.test(msg)) return t('네트워크 연결 실패 — 나중에 자동으로 다시 보냅니다');
  return msg;
}

/** 실패했거나 아직 안 보낸 연동이 있는 명함 (앱이 다시 열릴 때 재전송 대상) */
export function pendingTargets(card: BusinessCard, settings: Settings): ConnectorId[] {
  return connectorTargets(settings, card.kind).filter((id) => card.sync[id]?.state !== 'ok');
}
