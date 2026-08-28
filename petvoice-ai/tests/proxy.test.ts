import { describe, expect, it, vi } from 'vitest';
import { ApiError, userMessageKey } from '../src/api/errors';
import { analyzePetMedia, type ProxyConfig } from '../src/api/proxy';
import type { PetProfile } from '../src/core/types';

const pet: PetProfile = { id: 'p', name: '초코', type: 'DOG', createdAt: 0 };

const VALID_BODY = JSON.stringify({
  petVoiceMessage: '심심해!',
  primaryEmotion: 'playful',
  emotionScores: { playful: 75, attentionSeeking: 20, anxiety: 5 },
  behaviorAnalysis: '경쾌한 짧은 짖음.',
  actionGuide: '놀아 주세요.',
});

function config(fetchImpl: typeof fetch, over: Partial<ProxyConfig> = {}): ProxyConfig {
  return {
    supabaseUrl: 'https://demo.supabase.co',
    anonKey: 'anon',
    getAccessToken: async () => 'user-token',
    fetchImpl,
    timeoutMs: 200,
    ...over,
  };
}

function ok(body: string): Response {
  return { ok: true, status: 200, text: async () => body } as Response;
}

function fail(status: number, body = ''): Response {
  return { ok: false, status, text: async () => body } as Response;
}

const input = {
  pet,
  mediaBase64: 'AAAA',
  mediaType: 'audio/m4a' as const,
  context: '외출 직전',
  contextTags: ['separation' as const],
  locale: 'ko' as const,
};

describe('analyzePetMedia', () => {
  it('사용자 토큰만 보내고 AI 키는 절대 싣지 않는다', async () => {
    const fetchImpl = vi.fn(async () => ok(VALID_BODY)) as unknown as typeof fetch;
    await analyzePetMedia(config(fetchImpl), input);

    const [url, init] = (fetchImpl as unknown as { mock: { calls: [string, RequestInit][] } }).mock.calls[0];
    expect(url).toBe('https://demo.supabase.co/functions/v1/gemini-proxy');
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer user-token');
    expect(JSON.stringify(init)).not.toMatch(/gemini[_-]?api[_-]?key/i);
  });

  it('결과와 이상 징후 판정을 함께 돌려준다', async () => {
    const fetchImpl = (async () => ok(VALID_BODY)) as unknown as typeof fetch;
    const { result, health } = await analyzePetMedia(config(fetchImpl), input);
    expect(result.primaryEmotion).toBe('playful');
    expect(health.level).toBe('none');
  });

  it('세션이 없으면 인증 오류', async () => {
    const fetchImpl = (async () => ok(VALID_BODY)) as unknown as typeof fetch;
    await expect(analyzePetMedia(config(fetchImpl, { getAccessToken: async () => null }), input)).rejects.toMatchObject({
      code: 'unauthorized',
    });
  });

  it('402 는 한도 초과로 매핑하고 재시도하지 않는다', async () => {
    const fetchImpl = vi.fn(async () => fail(402, 'quota_exceeded')) as unknown as typeof fetch;
    await expect(analyzePetMedia(config(fetchImpl), input)).rejects.toMatchObject({ code: 'quota' });
    expect((fetchImpl as unknown as { mock: { calls: unknown[] } }).mock.calls).toHaveLength(1);
  });

  it('415 는 지원하지 않는 미디어로 매핑한다', async () => {
    const fetchImpl = (async () => fail(415)) as unknown as typeof fetch;
    await expect(analyzePetMedia(config(fetchImpl), input)).rejects.toMatchObject({ code: 'unsupported_media' });
  });

  it('5xx 는 재시도한 뒤 성공하면 결과를 준다', async () => {
    let calls = 0;
    const fetchImpl = (async () => {
      calls += 1;
      return calls === 1 ? fail(503) : ok(VALID_BODY);
    }) as unknown as typeof fetch;
    const { result } = await analyzePetMedia(config(fetchImpl), input);
    expect(calls).toBe(2);
    expect(result.primaryEmotion).toBe('playful');
  });

  it('망가진 응답은 parse 오류로 바꿔 사용자 문구를 낸다', async () => {
    const fetchImpl = (async () => ok('그건 분석하기 어렵네요')) as unknown as typeof fetch;
    const error = await analyzePetMedia(config(fetchImpl), input).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe('parse');
    expect(userMessageKey(error)).toBe('errors.parse');
  });
});
