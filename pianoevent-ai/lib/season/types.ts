import type { SeasonTheme } from '@/lib/types'

export interface SeasonWeek {
  week: number
  title: string
  goal: string
  activities: string[]
  repertoire: string[]
  homework: string
}

export type WorksheetKind = 'quiz' | 'listening' | 'rhythm' | 'coloring'

export interface WorksheetQuestion {
  prompt: string
  /** 객관식이면 보기, 단답이면 비움 */
  choices: string[]
  answer: string
}

export interface Worksheet {
  id: string
  kind: WorksheetKind
  title: string
  instruction: string
  questions: WorksheetQuestion[]
}

export interface SeasonPack {
  theme: SeasonTheme
  title: string
  subtitle: string
  target: string
  weeks: SeasonWeek[]
  worksheets: Worksheet[]
  /** 원장이 학부모에게 보낼 안내 문구 */
  parentNotice: string
  source: 'ai' | 'template'
  fallbackReason: string | null
}
