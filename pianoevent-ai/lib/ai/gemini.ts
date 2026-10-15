import { GoogleGenAI } from '@google/genai'

/**
 * 서버 전용 Gemini 래퍼.
 * GEMINI_API_KEY 는 이 모듈 밖으로 절대 나가지 않으며, 클라이언트 번들에 포함되면 안 된다.
 * (Google Play 정책 체크리스트 1항 — API 키 은닉)
 */

if (typeof window !== 'undefined') {
  throw new Error('lib/ai/gemini.ts 는 서버에서만 불러올 수 있습니다. API Route 를 통해 호출하세요.')
}

/** 지시서는 gemini-1.5-pro/flash 를 명시하지만, 모델은 수명이 있으므로 env 로 교체 가능하게 둔다 */
export const PRO_MODEL = process.env.GEMINI_MODEL_PRO ?? 'gemini-2.5-pro'
export const FLASH_MODEL = process.env.GEMINI_MODEL_FLASH ?? 'gemini-2.5-flash'

const TIMEOUT_MS = Number(process.env.GEMINI_TIMEOUT_MS ?? 45_000)

export function isAiConfigured(): boolean {
  return Boolean(process.env.GEMINI_API_KEY?.trim())
}

let client: GoogleGenAI | null = null
function getClient(): GoogleGenAI {
  const apiKey = process.env.GEMINI_API_KEY?.trim()
  if (!apiKey) throw new AiUnavailableError('GEMINI_API_KEY 가 설정되지 않았습니다.')
  if (!client) client = new GoogleGenAI({ apiKey })
  return client
}

export class AiUnavailableError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'AiUnavailableError'
  }
}

/** 모델이 ```json 펜스나 앞뒤 설명을 붙여도 JSON 만 뽑아낸다 */
export function extractJson(raw: string): unknown {
  const text = raw.trim()
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i)
  const body = fenced ? fenced[1].trim() : text

  try {
    return JSON.parse(body)
  } catch {
    const start = body.search(/[[{]/)
    const end = Math.max(body.lastIndexOf(']'), body.lastIndexOf('}'))
    if (start >= 0 && end > start) return JSON.parse(body.slice(start, end + 1))
    throw new AiUnavailableError('AI 응답을 JSON 으로 해석하지 못했습니다.')
  }
}

export interface GenerateJsonInput {
  systemInstruction: string
  contents: string
  model?: string
  temperature?: number
  /** 응답 스키마(선택). 주면 모델이 형태를 지킬 확률이 크게 올라간다 */
  responseSchema?: Record<string, unknown>
}

export async function generateJson<T>(input: GenerateJsonInput): Promise<T> {
  const ai = getClient()

  const call = ai.models.generateContent({
    model: input.model ?? PRO_MODEL,
    contents: input.contents,
    config: {
      systemInstruction: input.systemInstruction,
      responseMimeType: 'application/json',
      temperature: input.temperature ?? 0.7,
      ...(input.responseSchema ? { responseSchema: input.responseSchema } : {}),
    },
  })

  let timer: ReturnType<typeof setTimeout> | undefined
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new AiUnavailableError(`AI 응답이 ${TIMEOUT_MS}ms 안에 오지 않았습니다.`)), TIMEOUT_MS)
  })

  try {
    const response = await Promise.race([call, timeout])
    const text = (response as { text?: string }).text
    if (!text) throw new AiUnavailableError('AI 가 빈 응답을 돌려주었습니다.')
    return extractJson(text) as T
  } catch (error) {
    if (error instanceof AiUnavailableError) throw error
    throw new AiUnavailableError(error instanceof Error ? error.message : String(error))
  } finally {
    if (timer) clearTimeout(timer)
  }
}
