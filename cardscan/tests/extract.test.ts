// 서버 함수의 Claude 호출부 — 실제 API 대신 가짜 클라이언트로 요청 모양과 응답 처리를 검증한다.
import type Anthropic from '@anthropic-ai/sdk';
import { describe, expect, it, vi } from 'vitest';
import { CARD_SCHEMA, ExtractError, extractCard, MODEL } from '../supabase/functions/scan-card/extract';

function fakeClient(response: object) {
  const create = vi.fn(async () => response);
  return { client: { beta: { messages: { create } } } as unknown as Anthropic, create };
}

const fields = {
  name: '홍길동', nameEn: '', company: '한빛상사', department: '', title: '팀장',
  mobile: '010-1234-5678', phone: '', fax: '', email: 'a@b.co', website: '', address: '',
};

describe('extractCard', () => {
  it('이미지·스키마·모델을 담아 요청하고 JSON 을 돌려준다', async () => {
    const body = { fields, extra: [], isBusinessCard: true, note: '' };
    const { client, create } = fakeClient({ stop_reason: 'end_turn', content: [{ type: 'text', text: JSON.stringify(body) }] });
    const r = await extractCard(client, 'QUJD', 'image/png');
    expect(r).toEqual(body);

    const req = (create.mock.calls[0] as unknown[])[0] as Record<string, any>;
    expect(req.model).toBe(MODEL);
    expect(req.output_config.format).toEqual({ type: 'json_schema', schema: CARD_SCHEMA });
    expect(req.fallbacks).toBe('default');
    expect(req.betas).toContain('server-side-fallback-2026-07-01');
    expect(req).not.toHaveProperty('thinking'); // 이 모델은 thinking 을 끌 수 없다 — effort 로만 조절
    expect(req.messages[0].content[0]).toEqual({ type: 'image', source: { type: 'base64', media_type: 'image/png', data: 'QUJD' } });
  });

  it('스키마는 strict 출력 요건(additionalProperties:false, 전 필드 required)을 지킨다', () => {
    expect(CARD_SCHEMA.additionalProperties).toBe(false);
    expect(CARD_SCHEMA.properties.fields.additionalProperties).toBe(false);
    expect([...CARD_SCHEMA.properties.fields.required].sort()).toEqual(Object.keys(CARD_SCHEMA.properties.fields.properties).sort());
  });

  it('거절이면 422', async () => {
    const { client } = fakeClient({ stop_reason: 'refusal', content: [] });
    await expect(extractCard(client, 'x')).rejects.toMatchObject({ status: 422 });
  });

  it('JSON 이 아니면 ExtractError', async () => {
    const { client } = fakeClient({ stop_reason: 'end_turn', content: [{ type: 'text', text: 'nope' }] });
    await expect(extractCard(client, 'x')).rejects.toBeInstanceOf(ExtractError);
  });
});
