import { FLASH_MODEL, generateJson, isAiConfigured } from '@/lib/ai/gemini'
import { templatePack } from '@/lib/season/templates'
import type { SeasonPack, SeasonWeek, Worksheet, WorksheetKind } from '@/lib/season/types'
import { SEASON_LABEL, type SeasonTheme } from '@/lib/types'

export const SEASON_SYSTEM_INSTRUCTION = `당신은 어린이 음악교육 커리큘럼을 15년간 설계해 온 피아노 교육 전문가입니다.
피아노학원 원장이 시즌 특강을 바로 열 수 있도록, 주차별 수업 계획서와 인쇄용 활동지를 만듭니다.

원칙:
- 모든 활동은 피아노 한 대와 종이·연필만으로 학원에서 실제로 할 수 있어야 합니다.
- 각 주차에는 명확한 학습 목표 하나, 활동 3가지, 다룰 곡, 집에서 할 과제를 담습니다.
- 활동지 문제는 해당 연령이 스스로 풀 수 있는 난이도로, 정답이 분명해야 합니다.
- 실존하지 않는 곡이나 작곡가를 지어내지 마세요. 확실하지 않으면 널리 알려진 곡만 쓰세요.
- 모든 문장은 한국어 존댓말로 씁니다.

반드시 아래 JSON 만 출력하세요.
{
  "title": "특강 제목",
  "subtitle": "한 줄 소개",
  "target": "대상 학년·수준",
  "parentNotice": "학부모 안내 문구 3문장 내외",
  "weeks": [{ "week": 1, "title": "", "goal": "", "activities": ["", "", ""], "repertoire": [""], "homework": "" }],
  "worksheets": [{
    "kind": "quiz | listening | rhythm | coloring",
    "title": "",
    "instruction": "",
    "questions": [{ "prompt": "", "choices": ["", ""], "answer": "" }]
  }]
}`

export interface SeasonPromptInput {
  theme: SeasonTheme
  academyName: string
  weeks: number
  target: string
  /** 원장이 추가로 적은 요청 (예: "형제 수강생이 많아요", "5~7세 위주") */
  focus: string
}

export function buildSeasonContents(input: SeasonPromptInput): string {
  return JSON.stringify({
    theme: SEASON_LABEL[input.theme],
    academyName: input.academyName,
    weekCount: input.weeks,
    target: input.target,
    focus: input.focus,
    worksheetCount: 3,
  })
}

const KINDS: WorksheetKind[] = ['quiz', 'listening', 'rhythm', 'coloring']

const str = (v: unknown, fallback = ''): string => (typeof v === 'string' && v.trim() ? v.trim() : fallback)
const strArray = (v: unknown): string[] =>
  Array.isArray(v) ? v.map((x) => str(x)).filter((x) => x.length > 0) : []

/** 모델 응답을 SeasonPack 으로 정규화한다. 빠진 항목은 템플릿 값으로 메운다. */
export function parseSeasonPack(raw: unknown, theme: SeasonTheme): SeasonPack | null {
  const base = templatePack(theme)
  const data = (raw ?? {}) as Record<string, unknown>

  const weeks: SeasonWeek[] = Array.isArray(data.weeks)
    ? data.weeks
        .map((entry, i): SeasonWeek | null => {
          if (!entry || typeof entry !== 'object') return null
          const w = entry as Record<string, unknown>
          const title = str(w.title)
          if (!title) return null
          return {
            week: typeof w.week === 'number' && w.week > 0 ? Math.round(w.week) : i + 1,
            title,
            goal: str(w.goal, '이번 주 학습 목표'),
            activities: strArray(w.activities),
            repertoire: strArray(w.repertoire),
            homework: str(w.homework, '없음'),
          }
        })
        .filter((w): w is SeasonWeek => w !== null)
    : []

  if (weeks.length === 0) return null

  const worksheets: Worksheet[] = Array.isArray(data.worksheets)
    ? data.worksheets
        .map((entry, i): Worksheet | null => {
          if (!entry || typeof entry !== 'object') return null
          const s = entry as Record<string, unknown>
          const title = str(s.title)
          const questions = Array.isArray(s.questions)
            ? s.questions
                .map((q) => {
                  if (!q || typeof q !== 'object') return null
                  const item = q as Record<string, unknown>
                  const prompt = str(item.prompt)
                  if (!prompt) return null
                  return { prompt, choices: strArray(item.choices), answer: str(item.answer) }
                })
                .filter((q): q is Worksheet['questions'][number] => q !== null)
            : []
          if (!title || questions.length === 0) return null
          const kind = KINDS.includes(s.kind as WorksheetKind) ? (s.kind as WorksheetKind) : 'quiz'
          return { id: `ai-${theme}-${i + 1}`, kind, title, instruction: str(s.instruction, '문제를 풀어 보세요.'), questions }
        })
        .filter((w): w is Worksheet => w !== null)
    : []

  return {
    theme,
    title: str(data.title, base.title),
    subtitle: str(data.subtitle, base.subtitle),
    target: str(data.target, base.target),
    parentNotice: str(data.parentNotice, base.parentNotice),
    weeks,
    worksheets: worksheets.length > 0 ? worksheets : base.worksheets,
    source: 'ai',
    fallbackReason: null,
  }
}

export async function generateSeasonPack(input: SeasonPromptInput): Promise<SeasonPack> {
  const fallback = (reason: string | null): SeasonPack => ({ ...templatePack(input.theme), fallbackReason: reason })

  if (!isAiConfigured()) return fallback('GEMINI_API_KEY 가 없어 기본 커리큘럼 템플릿을 사용했습니다.')

  try {
    const raw = await generateJson<unknown>({
      systemInstruction: SEASON_SYSTEM_INSTRUCTION,
      contents: buildSeasonContents(input),
      model: FLASH_MODEL,
      temperature: 0.8,
    })
    return parseSeasonPack(raw, input.theme) ?? fallback('AI 응답을 해석하지 못해 기본 템플릿을 사용했습니다.')
  } catch (error) {
    return fallback(`AI 호출 실패 — ${error instanceof Error ? error.message : String(error)}`)
  }
}
