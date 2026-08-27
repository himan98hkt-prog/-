import type { AcademyAsset, ImageMap } from '@/lib/assets'

/** 연주 난이도 — 순서 배치 단계(stage)를 결정하는 1차 기준 */
export type Level = 'beginner' | 'intermediate' | 'advanced' | 'ensemble'

/** 프로그램의 큰 흐름. 지시서의 오프닝 → 기초/초급 → 중급 → 듀엣/앙상블 → 피날레 */
export type Stage = 'opening' | 'beginner' | 'intermediate' | 'ensemble' | 'finale'

export type EventType = 'recital' | 'season'
export type EventStatus = 'draft' | 'ready' | 'published' | 'done'
export type SeasonTheme = 'halloween' | 'christmas' | 'vacation'

export interface Academy {
  id: string
  name: string
  director_name: string
  logo_url: string | null
  theme_color: string
  /** 인쇄물 기본 디자인 테마 (lib/design/themes.ts 의 id) */
  design_theme: string | null
  /** 학원 대표 사진 — 행사 사진이 없을 때 인쇄물에 쓰인다 */
  photo_url: string | null
  /** 로고·상징·사진 보관함. 한 번 올려 두면 모든 행사에서 골라 쓴다 */
  assets: AcademyAsset[]
  created_at: string
}

export interface EventRecord {
  id: string
  academy_id: string
  title: string
  type: EventType
  event_at: string /** ISO 8601 */
  venue: string
  status: EventStatus
  /** 시즌 특강일 때만 사용 */
  theme: SeasonTheme | null
  /** 초대장·프로그램 상단에 들어가는 원장 인사말 */
  greeting: string | null
  /** 사회자 오프닝 멘트 (AI 또는 규칙 엔진 생성 결과) */
  mc_opening: string | null
  /** 사회자 클로징 멘트 */
  mc_closing: string | null
  /** 마지막 순서표 생성이 AI 였는지 규칙 엔진이었는지 */
  program_source: 'ai' | 'rule' | null
  program_generated_at: string | null
  /** 이 행사에서 쓰는 디자인 테마. 비어 있으면 학원 기본 테마를 따른다 */
  design_theme: string | null
  /** 마지막으로 고른 인쇄 양식 */
  design_template: string | null
  /** 인쇄물 문구 (부제·주최·문의·안내) */
  design_copy: Record<string, string> | null
  /** 이 행사의 대표 사진 (작년 연주회·단체 사진 등). 없으면 학원 대표 사진을 쓴다 */
  photo_url: string | null
  /** 인쇄물 갈래별로 어떤 보관함 이미지를 쓸지. 비우면 기본값을 따른다 */
  image_map: ImageMap | null
  created_at: string
}

export interface EventStudent {
  id: string
  event_id: string
  student_name: string
  piece_title: string
  composer: string
  /** 연주 소요시간(초). 미입력이면 난이도 기준으로 추정한다 */
  duration_sec: number
  level: Level
  /** AI/규칙 엔진이 배치한 최종 순서 (1부터). 미배치는 null */
  order_no: number | null
  /** 사회자 멘트 (곡 해설 + 학생 소개) */
  mc_script: string | null
  /** 원장이 남긴 학생 특징 메모 — 멘트 생성의 재료 */
  note: string | null
  /** 이미지 보관함에 있는 이 아이의 사진. 무대 화면·영상에 들어간다 */
  photo_asset_id: string | null
  created_at: string
}

export interface Rsvp {
  id: string
  event_id: string
  parent_name: string
  student_name: string
  headcount: number
  message: string | null
  attending: boolean
  created_at: string
}

/** 순서표 한 줄 — DB 의 event_students 에 배치 결과(시간)를 얹은 뷰 모델 */
export interface ProgramItem {
  student: EventStudent
  order_no: number
  stage: Stage
  /** 행사 시작 시각으로부터의 오프셋(초) */
  start_offset_sec: number
  duration_sec: number
}

/** 순서표 중간에 삽입되는 휴식 */
export interface ProgramBreak {
  after_order_no: number
  start_offset_sec: number
  duration_sec: number
  label: string
}

export interface ProgramPlan {
  items: ProgramItem[]
  breaks: ProgramBreak[]
  /** 연주 시간 합계(초) — 전환·휴식 제외 */
  play_sec: number
  /** 실제 러닝타임(초) — 전환·휴식 포함 */
  total_sec: number
  warnings: string[]
}

export interface ProgramOptions {
  /** 곡과 곡 사이 전환 시간(초): 인사·착석·박수 */
  turnover_sec: number
  /** 이 시간을 넘어가면 중간 휴식을 넣는다(초) */
  intermission_after_sec: number
  /** 중간 휴식 길이(초). 0 이면 휴식 없음 */
  intermission_sec: number
  /** 권장 최대 러닝타임(초). 넘으면 경고 */
  max_total_sec: number
}

export const DEFAULT_PROGRAM_OPTIONS: ProgramOptions = {
  turnover_sec: 40,
  intermission_after_sec: 50 * 60,
  intermission_sec: 10 * 60,
  max_total_sec: 100 * 60,
}

export const LEVEL_LABEL: Record<Level, string> = {
  beginner: '기초·초급',
  intermediate: '중급',
  advanced: '고급',
  ensemble: '듀엣·앙상블',
}

export const STAGE_LABEL: Record<Stage, string> = {
  opening: '오프닝',
  beginner: '1부 · 기초와 첫 무대',
  intermediate: '2부 · 중급',
  ensemble: '3부 · 듀엣과 앙상블',
  finale: '피날레',
}

export const SEASON_LABEL: Record<SeasonTheme, string> = {
  halloween: '할로윈',
  christmas: '크리스마스',
  vacation: '방학 특강',
}

export const EVENT_STATUS_LABEL: Record<EventStatus, string> = {
  draft: '기획 중',
  ready: '순서표 완성',
  published: '초대장 배포',
  done: '종료',
}
