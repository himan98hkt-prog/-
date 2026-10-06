import { describe, expect, it, vi } from 'vitest';
import { connectorTargets, DEFAULT_SETTINGS, mergeSettings, Settings, setPath } from '../src/core/settings';
import { hubspotConnector, sheetsConnector, slackConnector, webhookConnector } from '../src/integrations/http';
import { checkOcr, scanCardImage } from '../src/integrations/ocr';
import { effectiveOcrMode } from '../src/core/settings';
import { ConnectorMap, pendingTargets, syncCard } from '../src/integrations/sync';
import { makeCard } from './fixtures';

function settingsWith(patch: (s: Settings) => Settings): Settings {
  return patch(JSON.parse(JSON.stringify(DEFAULT_SETTINGS)));
}

const fullSettings = settingsWith((s) => {
  s.connectors.webhook = { enabled: true, kinds: ['partner'], url: 'https://erp.example.com/hook', secret: 's3' };
  s.connectors.sheets = { enabled: true, kinds: ['customer', 'partner', 'other'], url: 'https://script.google.com/macros/s/x/exec', secret: 'sh' };
  s.connectors.hubspot = { enabled: true, kinds: ['customer'], token: 'pat-na1-xxxxxxxxxxxx' };
  s.connectors.slack = { enabled: true, kinds: ['customer', 'partner'], url: 'https://hooks.slack.com/services/T/B/X' };
  return s;
});

const res = (status: number, body: unknown) =>
  new Response(typeof body === 'string' ? body : JSON.stringify(body), { status });

describe('설정', () => {
  it('구분별로 보낼 시스템이 정해진다', () => {
    expect(connectorTargets(fullSettings, 'customer')).toEqual(['contacts', 'sheets', 'hubspot', 'slack']);
    expect(connectorTargets(fullSettings, 'partner')).toEqual(['contacts', 'sheets', 'webhook', 'slack']);
    expect(connectorTargets(fullSettings, 'other')).toEqual(['contacts', 'sheets']);
  });

  it('주소가 잘못되면 대상에서 빠진다', () => {
    const s = setPath(fullSettings, 'connectors.webhook.url', 'http://insecure');
    expect(connectorTargets(s, 'partner')).not.toContain('webhook');
  });

  it('구버전 설정에 없는 키는 기본값으로 채운다', () => {
    const m = mergeSettings({ autoSave: false, connectors: { webhook: { enabled: true } } });
    expect(m.autoSave).toBe(false);
    expect(m.connectors.webhook.enabled).toBe(true);
    expect(m.connectors.webhook.kinds).toEqual(['customer', 'partner', 'other']);
    expect(m.connectors.slack).toEqual(DEFAULT_SETTINGS.connectors.slack);
    expect(m.ocr.endpoint).toBe('');
    // 행사 태그·연속 촬영이 생기기 전 설정 → 꺼진 상태로
    expect(m.scanTag).toBe('');
    expect(m.continuousScan).toBe(false);
  });
});

describe('syncCard', () => {
  it('하나가 실패해도 나머지는 성공 처리하고, 이전 remoteId 를 넘긴다', async () => {
    const calls: string[] = [];
    const ok = (id: string) => vi.fn(async (_c, ctx) => (calls.push(id), { remoteId: `${id}-1`, message: ctx.previous?.remoteId }));
    const connectors = {
      contacts: ok('contacts'),
      sheets: vi.fn(async () => {
        throw new Error('Network request failed');
      }),
      hubspot: ok('hubspot'),
      webhook: ok('webhook'),
      slack: ok('slack'),
    } as unknown as ConnectorMap;

    const card = makeCard({ sync: { contacts: { state: 'ok', at: 'x', remoteId: 'old-contact' } } });
    const sync = await syncCard(card, { settings: fullSettings, connectors, fetch: fetch, now: () => 'T' });

    expect(calls.sort()).toEqual(['contacts', 'hubspot', 'slack']);
    expect(sync.contacts).toEqual({ state: 'ok', at: 'T', remoteId: 'contacts-1', message: 'old-contact' });
    expect(sync.sheets?.state).toBe('error');
    expect(sync.sheets?.message).toContain('네트워크');
    expect(sync.webhook).toBeUndefined(); // 고객 명함은 거래처 전용 웹훅으로 보내지 않는다
    expect(pendingTargets({ ...card, sync }, fullSettings)).toEqual(['sheets']);
  });

  it('only 로 특정 연동만 재시도', async () => {
    const hub = vi.fn(async () => ({ remoteId: 'h' }));
    const connectors = { contacts: vi.fn(), sheets: vi.fn(), hubspot: hub, webhook: vi.fn(), slack: vi.fn() } as unknown as ConnectorMap;
    const sync = await syncCard(makeCard(), { settings: fullSettings, connectors, fetch, only: ['hubspot'] });
    expect(Object.keys(sync)).toEqual(['hubspot']);
    expect(connectors.contacts).not.toHaveBeenCalled();
  });
});

describe('HTTP 연동', () => {
  it('웹훅: 비밀 헤더와 이벤트 종류', async () => {
    const f = vi.fn(async () => res(200, 'ok'));
    await webhookConnector(makeCard({ kind: 'partner' }), { settings: fullSettings, fetch: f as typeof fetch, previous: { state: 'ok', at: 'x' } });
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://erp.example.com/hook');
    expect((init.headers as Record<string, string>)['X-CardScan-Secret']).toBe('s3');
    expect(JSON.parse(init.body as string).event).toBe('card.updated');
  });

  it('웹훅: 실패 응답은 오류로', async () => {
    const f = vi.fn(async () => res(500, 'boom'));
    await expect(webhookConnector(makeCard(), { settings: fullSettings, fetch: f as typeof fetch })).rejects.toThrow('HTTP 500 — boom');
  });

  it('구글 시트: 스크립트 응답 확인', async () => {
    const f = vi.fn(async () => res(200, { ok: true, row: 7 }));
    const r = await sheetsConnector(makeCard(), { settings: fullSettings, fetch: f as typeof fetch });
    expect(r.message).toBe('7행');
    const body = JSON.parse((f.mock.calls[0] as unknown as [string, RequestInit])[1].body as string);
    expect(body.secret).toBe('sh');
    expect(body.row[0]).toBe('c1');

    const bad = vi.fn(async () => res(200, '<html>login</html>'));
    await expect(sheetsConnector(makeCard(), { settings: fullSettings, fetch: bad as typeof fetch })).rejects.toThrow('모든 사용자');
    const denied = vi.fn(async () => res(200, { ok: false, error: 'bad secret' }));
    await expect(sheetsConnector(makeCard(), { settings: fullSettings, fetch: denied as typeof fetch })).rejects.toThrow('bad secret');
  });

  it('HubSpot: 새로 만들기', async () => {
    const f = vi.fn(async () => res(201, { id: '901' }));
    const r = await hubspotConnector(makeCard(), { settings: fullSettings, fetch: f as typeof fetch });
    expect(r.remoteId).toBe('901');
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://api.hubapi.com/crm/v3/objects/contacts');
    expect(init.method).toBe('POST');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer pat-na1-xxxxxxxxxxxx');
  });

  it('HubSpot: 같은 이메일이 있으면(409) 기존 연락처 갱신', async () => {
    const f = vi
      .fn()
      .mockResolvedValueOnce(res(409, { message: 'Contact already exists. Existing ID: 555' }))
      .mockResolvedValueOnce(res(200, { id: '555' }));
    const r = await hubspotConnector(makeCard(), { settings: fullSettings, fetch: f as unknown as typeof fetch });
    expect(r.remoteId).toBe('555');
    expect(f.mock.calls[1][0]).toBe('https://api.hubapi.com/crm/v3/objects/contacts/555');
    expect(f.mock.calls[1][1].method).toBe('PATCH');
  });

  it('HubSpot: 이전 id 가 지워졌으면(404) 새로 만든다', async () => {
    const f = vi
      .fn()
      .mockResolvedValueOnce(res(404, 'not found'))
      .mockResolvedValueOnce(res(201, { id: '777' }));
    const r = await hubspotConnector(makeCard(), {
      settings: fullSettings,
      fetch: f as unknown as typeof fetch,
      previous: { state: 'ok', at: 'x', remoteId: '123' },
    });
    expect(r.remoteId).toBe('777');
    expect(f.mock.calls.map((c) => c[1].method)).toEqual(['PATCH', 'POST']);
  });

  it('슬랙: 이미 알렸으면 다시 보내지 않는다', async () => {
    const f = vi.fn(async () => res(200, 'ok'));
    await slackConnector(makeCard(), { settings: fullSettings, fetch: f as typeof fetch, previous: { state: 'ok', at: 'x', remoteId: 'sent' } });
    expect(f).not.toHaveBeenCalled();
    await slackConnector(makeCard(), { settings: fullSettings, fetch: f as typeof fetch });
    expect(f).toHaveBeenCalledOnce();
  });
});

const img = (base64: string) => ({ uri: 'file:///card.jpg', base64 });

describe('OCR 클라이언트 — 서버 모드', () => {
  const ocrSettings = settingsWith((s) => {
    s.ocr = { mode: 'server', apiKey: '', endpoint: 'https://p.supabase.co/functions/v1/scan-card', anonKey: 'anon', appSecret: 'app' };
    return s;
  });


  it('헤더를 붙여 보내고 응답을 정리한다', async () => {
    const f = vi.fn(async () => res(200, { fields: { name: '홍길동', mobile: '01012345678', email: 'A@B.CO' }, extra: ['@insta', 3], note: '' }));
    const r = await scanCardImage(img('b64'), ocrSettings, { fetch: f as typeof fetch });
    const [, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    const h = init.headers as Record<string, string>;
    expect(h.Authorization).toBe('Bearer anon');
    expect(h['x-app-secret']).toBe('app');
    expect(JSON.parse(init.body as string)).toEqual({ image: 'b64', mediaType: 'image/jpeg' });
    expect(r.fields.mobile).toBe('010-1234-5678');
    expect(r.fields.email).toBe('a@b.co');
    expect(r.extra).toEqual(['@insta']);
    expect(r.note).toBeUndefined();
  });

  it('서버 오류 메시지를 그대로 보여준다', async () => {
    const f = vi.fn(async () => res(422, { error: '명함이 아닌 사진으로 보입니다' }));
    await expect(scanCardImage(img('b64'), ocrSettings, { fetch: f as typeof fetch })).rejects.toThrow('명함이 아닌');
  });
});

describe('OCR 클라이언트 — 유료(Claude API 키) 모드', () => {
  const direct = settingsWith((s) => {
    s.ocr.mode = 'direct';
    s.ocr.apiKey = 'sk-ant-api03-test';
    return s;
  });
  const apiReply = (payload: object, stop = 'end_turn') => res(200, { stop_reason: stop, content: [{ type: 'text', text: JSON.stringify(payload) }] });
  const fields = { name: '김철수', nameEn: '', company: '테스트', department: '', title: '', mobile: '+82 10 2222 3333', phone: '', fax: '', email: 'K@T.CO', website: '', address: '' };

  it('키가 없으면 유료 모드를 골라도 무료(기기) 인식으로 동작', () => {
    expect(effectiveOcrMode(setPath(DEFAULT_SETTINGS, 'ocr.mode', 'direct'))).toBe('device');
    expect(effectiveOcrMode(direct)).toBe('direct');
  });

  it('Messages API 를 서버와 같은 요청 모양으로 호출한다', async () => {
    const f = vi.fn(async () => apiReply({ fields, extra: [], isBusinessCard: true, note: '' }));
    const r = await scanCardImage(img('IMG'), direct, { fetch: f as typeof fetch });
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://api.anthropic.com/v1/messages');
    const h = init.headers as Record<string, string>;
    expect(h['x-api-key']).toBe('sk-ant-api03-test');
    expect(h['anthropic-version']).toBe('2023-06-01');
    expect(h['anthropic-beta']).toBe('server-side-fallback-2026-07-01');
    const body = JSON.parse(init.body as string);
    expect(body.model).toBe('claude-opus-5-5');
    expect(body.fallbacks).toBe('default');
    expect(body.output_config.format.type).toBe('json_schema');
    expect(body.messages[0].content[0].source).toEqual({ type: 'base64', media_type: 'image/jpeg', data: 'IMG' });
    expect(r.fields.mobile).toBe('010-2222-3333');
    expect(r.fields.email).toBe('k@t.co');
  });

  it('명함이 아니면 안내', async () => {
    const f = vi.fn(async () => apiReply({ fields, extra: [], isBusinessCard: false, note: '' }));
    await expect(scanCardImage(img('IMG'), direct, { fetch: f as typeof fetch })).rejects.toThrow('명함이 아닌');
  });

  it('거절·오류 상태를 사람이 읽을 수 있게 바꾼다', async () => {
    const refusal = vi.fn(async () => res(200, { stop_reason: 'refusal', content: [] }));
    await expect(scanCardImage(img('IMG'), direct, { fetch: refusal as typeof fetch })).rejects.toThrow('처리할 수 없습니다');
    const unauthorized = vi.fn(async () => res(401, { error: { message: 'invalid x-api-key' } }));
    await expect(scanCardImage(img('IMG'), direct, { fetch: unauthorized as typeof fetch })).rejects.toThrow('API 키가 올바르지 않습니다');
    const credit = vi.fn(async () => res(400, { error: { message: 'Your credit balance is too low' } }));
    await expect(scanCardImage(img('IMG'), direct, { fetch: credit as typeof fetch })).rejects.toThrow('크레딧');
  });

  it('연결 확인은 과금 없는 모델 조회로 한다', async () => {
    const f = vi.fn(async () => res(200, { id: 'claude-opus-5-5' }));
    await checkOcr(direct, f as typeof fetch);
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://api.anthropic.com/v1/models/claude-opus-5-5');
    expect(init.method).toBeUndefined();
    await expect(checkOcr(setPath(direct, 'ocr.apiKey', 'abc'), f as typeof fetch)).rejects.toThrow('sk-ant-');
  });

  it('예전 버전에서 서버 주소를 넣어 둔 설정은 서버 모드로 이어간다', () => {
    expect(mergeSettings({ ocr: { endpoint: 'https://x.supabase.co/functions/v1/scan-card', appSecret: 's' } }).ocr.mode).toBe('server');
    expect(mergeSettings({}).ocr.mode).toBe('device');
    expect(mergeSettings({ ocr: { mode: 'direct', endpoint: 'https://x' } }).ocr.mode).toBe('direct');
  });
});

describe('OCR 클라이언트 — 무료(기기) 모드', () => {
  it('기본값이 무료 모드이고 네트워크를 쓰지 않는다', async () => {
    expect(DEFAULT_SETTINGS.ocr.mode).toBe('device');
    const f = vi.fn();
    const recognize = vi.fn(async () => ({
      lines: [
        { text: '(주)한빛상사', height: 40 },
        { text: '홍길동 팀장', height: 60 },
        { text: 'M 010 1234 5678', height: 24 },
        { text: 'GD.Hong@Hanbit.co.kr', height: 24 },
      ],
    }));
    const r = await scanCardImage(img('unused'), DEFAULT_SETTINGS, { fetch: f as unknown as typeof fetch, recognize });
    expect(recognize).toHaveBeenCalledWith('file:///card.jpg');
    expect(f).not.toHaveBeenCalled();
    expect(r.fields).toMatchObject({ name: '홍길동', title: '팀장', company: '(주)한빛상사', mobile: '010-1234-5678', email: 'gd.hong@hanbit.co.kr' });
  });

  it('글자를 못 찾으면 다시 찍으라고 안내', async () => {
    await expect(scanCardImage(img('x'), DEFAULT_SETTINGS, { recognize: async () => ({ lines: [] }) })).rejects.toThrow('다시 찍어');
  });

  it('네이티브 모듈이 없는 환경(웹)에서는 안내 메시지', async () => {
    await expect(scanCardImage(img('x'), DEFAULT_SETTINGS, {})).rejects.toThrow('안드로이드 설치 앱');
  });

  it('연결 확인은 무료 모드에서 아무 요청도 하지 않는다', async () => {
    const f = vi.fn();
    await checkOcr(DEFAULT_SETTINGS, f as unknown as typeof fetch);
    expect(f).not.toHaveBeenCalled();
  });
});
