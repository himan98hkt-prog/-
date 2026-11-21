// 명함 이미지 → 구조화 필드. Claude 비전 + JSON 스키마 출력으로 항상 같은 모양의 결과를 받는다.
// Node(테스트)와 Deno(Supabase Edge Function) 양쪽에서 쓰도록 런타임 의존 코드는 두지 않는다.
import type Anthropic from '@anthropic-ai/sdk';

export const MODEL = 'claude-opus-5-5';

const FIELD_KEYS = [
  'name', 'nameEn', 'company', 'department', 'title', 'mobile', 'phone', 'fax', 'email', 'website', 'address',
] as const;

export const CARD_SCHEMA = {
  type: 'object',
  properties: {
    fields: {
      type: 'object',
      properties: Object.fromEntries(FIELD_KEYS.map((k) => [k, { type: 'string' }])),
      required: [...FIELD_KEYS],
      additionalProperties: false,
    },
    extra: { type: 'array', items: { type: 'string' } },
    isBusinessCard: { type: 'boolean' },
    note: { type: 'string' },
  },
  required: ['fields', 'extra', 'isBusinessCard', 'note'],
  additionalProperties: false,
} as const;

export const SYSTEM_PROMPT = `당신은 한국 비즈니스 명함을 읽어 연락처 데이터로 옮기는 역할을 합니다.
사진에 보이는 글자만 옮기고, 보이지 않는 정보는 추측하지 말고 빈 문자열("")로 둡니다.

필드 규칙:
- name: 사람 이름(한글 우선). 한글 이름이 없으면 영문 이름. 직함·회사명은 넣지 않습니다.
- nameEn: 영문 이름이 따로 적혀 있을 때만.
- company: 회사/기관명 (로고 글자 포함). (주), 주식회사 표기는 명함에 적힌 그대로.
- department: 부서·팀·본부. title: 직급·직책(예: 대표이사, 팀장, 수석연구원).
- mobile: 휴대폰(010 등, M/Mobile/HP/H.P 표시). phone: 사무실 전화(T/Tel/Office). fax: 팩스(F/Fax).
  번호는 명함 표기 그대로 옮기되 +82 표기도 그대로 둡니다. 내선은 "ext 123" 처럼 뒤에 붙입니다.
- email, website: 철자를 정확히. 0/O, 1/l 혼동에 주의하고 도메인 형태가 맞는지 확인합니다.
- address: 주소 한 줄(우편번호가 있으면 앞에 포함).
- extra: 위 필드에 들어가지 않은 의미 있는 문구(SNS 계정, 자격, 슬로건, 두 번째 주소 등). 없으면 빈 배열.
- isBusinessCard: 사진이 명함이 아니면 false.
- note: 앞뒷면이 섞였거나 글자가 흐려 확신이 없는 필드가 있으면 한 문장으로 알려 주고, 아니면 "".`;

export interface ExtractResult {
  fields: Record<(typeof FIELD_KEYS)[number], string>;
  extra: string[];
  isBusinessCard: boolean;
  note: string;
}

export type ImageMediaType = 'image/jpeg' | 'image/png' | 'image/webp';

export class ExtractError extends Error {
  constructor(message: string, readonly status = 502) {
    super(message);
  }
}

export const FALLBACK_BETA = 'server-side-fallback-2026-07-01';

/**
 * Messages API 요청 본문. 서버(SDK)와 앱의 간편 모드(REST 직접 호출 — SDK 가 React Native 를 지원하지 않음)가
 * 같은 프롬프트·스키마를 쓰도록 한곳에서 만든다. 베타 헤더(FALLBACK_BETA)는 호출하는 쪽에서 붙인다.
 */
export function buildCardRequest(imageBase64: string, mediaType: ImageMediaType = 'image/jpeg') {
  return {
    model: MODEL,
    max_tokens: 4000,
    // 정해진 칸에 옮겨 적는 일이라 깊은 추론이 필요 없다 — 응답 속도를 우선
    output_config: { effort: 'low' as const, format: { type: 'json_schema' as const, schema: CARD_SCHEMA as unknown as Record<string, unknown> } },
    // 안전 분류기가 드물게 거절하면 서버 측에서 권장 모델로 자동 재시도
    fallbacks: 'default' as const,
    system: SYSTEM_PROMPT,
    messages: [
      {
        role: 'user' as const,
        content: [
          { type: 'image' as const, source: { type: 'base64' as const, media_type: mediaType, data: imageBase64 } },
          { type: 'text' as const, text: '이 명함의 정보를 스키마에 맞춰 옮겨 주세요.' },
        ],
      },
    ],
  };
}

/** Messages API 응답 → 결과. SDK 응답 객체와 REST JSON 모두 받는다. */
export function parseCardResponse(response: { stop_reason?: string | null; content?: Array<{ type: string; text?: string }> }): ExtractResult {
  if (response.stop_reason === 'refusal') throw new ExtractError('이미지를 처리할 수 없습니다', 422);
  if (response.stop_reason === 'max_tokens') throw new ExtractError('인식 결과가 너무 깁니다');

  const text = (response.content ?? []).flatMap((b) => (b.type === 'text' && typeof b.text === 'string' ? [b.text] : [])).join('');
  try {
    return JSON.parse(text) as ExtractResult;
  } catch {
    throw new ExtractError('인식 결과를 해석하지 못했습니다');
  }
}

export async function extractCard(client: Anthropic, imageBase64: string, mediaType: ImageMediaType = 'image/jpeg'): Promise<ExtractResult> {
  const response = await client.beta.messages.create({ ...buildCardRequest(imageBase64, mediaType), betas: [FALLBACK_BETA] });
  return parseCardResponse(response);
}
