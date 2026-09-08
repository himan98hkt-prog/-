import { generateJson, isAiConfigured, PRO_MODEL } from '@/lib/ai/gemini'
import { formatDuration } from '@/lib/format'
import { applyOrder, buildProgram } from '@/lib/program/order'
import { buildMcScript, type McScript } from '@/lib/program/script'
import {
  DEFAULT_PROGRAM_OPTIONS,
  LEVEL_LABEL,
  type EventStudent,
  type ProgramOptions,
  type ProgramPlan,
} from '@/lib/types'

export const PROGRAM_SYSTEM_INSTRUCTION = `당신은 20년 경력의 피아노 정기 연주회 총괄 디렉터이자 전문 사회자입니다.
입력된 학생 목록(이름, 연주곡, 작곡가, 난이도, 소요시간, 특징 메모)을 분석하여 다음을 수행하세요.

1. 지루하지 않고 극적 긴장감을 주는 최적의 연주 순서로 재배치합니다.
   흐름은 오프닝 → 기초/초급 → 중급 → 듀엣/앙상블 → 피날레 를 따릅니다.
   - 오프닝은 짧고 안정적인 곡으로 무대의 긴장을 풀어 줍니다.
   - 같은 작곡가의 곡이나 같은 학생의 연주가 연달아 오지 않게 합니다.
   - 피날레는 가장 난이도가 높고 여운이 남는 곡으로 배치합니다.
2. 각 곡마다 사회자가 그대로 읽을 수 있는 멘트를 씁니다.
   - 곡 해설 1~2문장 + 학생 소개 1문장, 총 3문장 내외의 한국어 존댓말.
   - 특징 메모가 있으면 자연스럽게 녹이되, 없는 사실을 지어내지 마세요.
   - 학생을 비교하거나 등수를 매기는 표현, 과장된 수식은 쓰지 마세요.
3. 행사 전체의 오프닝 멘트와 클로징 멘트를 각각 4문장 내외로 씁니다.

반드시 아래 JSON 스키마만 출력하세요. 설명 문장이나 마크다운은 붙이지 마세요.
{
  "order": [{ "id": "학생 id(입력과 동일)", "mc_script": "사회자 멘트" }],
  "opening_script": "행사 오프닝 멘트",
  "closing_script": "행사 클로징 멘트"
}
order 배열에는 입력된 모든 학생이 정확히 한 번씩 들어가야 합니다.`

export const PROGRAM_RESPONSE_SCHEMA = {
  type: 'object',
  properties: {
    order: {
      type: 'array',
      items: {
        type: 'object',
        properties: { id: { type: 'string' }, mc_script: { type: 'string' } },
        required: ['id', 'mc_script'],
      },
    },
    opening_script: { type: 'string' },
    closing_script: { type: 'string' },
  },
  required: ['order', 'opening_script', 'closing_script'],
} as const

export interface ProgramPromptInput {
  eventTitle: string
  academyName: string
  eventAt: string
  venue: string
  students: EventStudent[]
}

/** 모델에 넘길 입력. 토큰을 아끼려 필요한 필드만 추린다 */
export function buildProgramContents(input: ProgramPromptInput): string {
  return JSON.stringify({
    eventTitle: input.eventTitle,
    academyName: input.academyName,
    eventAt: input.eventAt,
    venue: input.venue,
    students: input.students.map((s) => ({
      id: s.id,
      name: s.student_name,
      piece: s.piece_title,
      composer: s.composer,
      level: LEVEL_LABEL[s.level],
      duration: formatDuration(s.duration_sec),
      note: s.note ?? '',
    })),
  })
}

interface RawProgramResponse {
  order?: unknown
  opening_script?: unknown
  closing_script?: unknown
}

export interface ParsedAiProgram {
  orderedIds: string[]
  scripts: Record<string, string>
  opening: string | null
  closing: string | null
}

/** 모델 응답을 방어적으로 읽는다. 형태가 조금 어긋나도 쓸 수 있는 만큼만 취한다. */
export function parseAiProgram(raw: unknown, students: EventStudent[]): ParsedAiProgram {
  const known = new Set(students.map((s) => s.id))
  const data = (raw ?? {}) as RawProgramResponse
  const orderedIds: string[] = []
  const scripts: Record<string, string> = {}

  if (Array.isArray(data.order)) {
    for (const entry of data.order) {
      if (!entry || typeof entry !== 'object') continue
      const item = entry as { id?: unknown; mc_script?: unknown }
      const id = typeof item.id === 'string' ? item.id : null
      if (!id || !known.has(id) || orderedIds.includes(id)) continue
      orderedIds.push(id)
      if (typeof item.mc_script === 'string' && item.mc_script.trim()) {
        scripts[id] = item.mc_script.trim()
      }
    }
  }

  const str = (v: unknown) => (typeof v === 'string' && v.trim() ? v.trim() : null)
  return { orderedIds, scripts, opening: str(data.opening_script), closing: str(data.closing_script) }
}

export interface GeneratedProgram {
  plan: ProgramPlan
  script: McScript
  /** ai: Gemini 결과 · rule: 내장 규칙 엔진 폴백 */
  source: 'ai' | 'rule'
  /** 폴백으로 내려온 이유 (원장 화면에 그대로 보여 준다) */
  fallbackReason: string | null
  model: string | null
}

/**
 * 연주 순서 + 사회자 대본 생성.
 * AI 가 없거나 실패하면 규칙 엔진 결과로 조용히 내려앉되, 그 사실을 숨기지 않는다.
 */
export async function generateProgram(
  input: ProgramPromptInput,
  options: ProgramOptions = DEFAULT_PROGRAM_OPTIONS,
): Promise<GeneratedProgram> {
  const meta = { eventTitle: input.eventTitle, academyName: input.academyName }

  const fallback = (reason: string | null): GeneratedProgram => {
    const plan = buildProgram(input.students, options)
    return { plan, script: buildMcScript(plan, meta), source: 'rule', fallbackReason: reason, model: null }
  }

  if (input.students.length === 0) return fallback('학생 명단이 비어 있습니다.')
  if (!isAiConfigured()) return fallback('GEMINI_API_KEY 가 없어 내장 규칙 엔진으로 생성했습니다.')

  try {
    const raw = await generateJson<unknown>({
      systemInstruction: PROGRAM_SYSTEM_INSTRUCTION,
      contents: buildProgramContents(input),
      model: PRO_MODEL,
      responseSchema: PROGRAM_RESPONSE_SCHEMA as unknown as Record<string, unknown>,
    })

    const parsed = parseAiProgram(raw, input.students)
    if (parsed.orderedIds.length === 0) return fallback('AI 응답에 유효한 순서가 없어 규칙 엔진으로 대체했습니다.')

    const plan = applyOrder(input.students, parsed.orderedIds, options)
    const base = buildMcScript(plan, meta)

    // AI 멘트를 우선 쓰되, 비어 있는 학생은 폴백 멘트로 채워 빈칸이 남지 않게 한다
    const byStudentId = { ...base.byStudentId }
    for (const [id, text] of Object.entries(parsed.scripts)) byStudentId[id] = text

    return {
      plan,
      script: {
        opening: parsed.opening ?? base.opening,
        closing: parsed.closing ?? base.closing,
        byStudentId,
      },
      source: 'ai',
      fallbackReason: null,
      model: PRO_MODEL,
    }
  } catch (error) {
    return fallback(`AI 호출 실패 — ${error instanceof Error ? error.message : String(error)}`)
  }
}
