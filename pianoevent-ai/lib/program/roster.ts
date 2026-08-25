import type { Level } from '@/lib/types'

/** 엑셀에서 복사한 표(TSV) 또는 CSV 한 줄 */
export interface RosterRow {
  student_name: string
  piece_title: string
  composer: string
  duration_sec: number | null
  level: Level
  note: string | null
}

export interface RosterParseResult {
  rows: RosterRow[]
  /** 사람이 고칠 수 있게 "3행: ..." 형태로 남긴다 */
  errors: string[]
  /** 헤더를 인식했는지 (못 하면 열 순서로 읽는다) */
  headerDetected: boolean
}

const HEADER_ALIASES: Record<keyof RosterRow, string[]> = {
  student_name: ['이름', '학생', '학생명', '성명', '연주자', 'name', 'student'],
  piece_title: ['곡', '곡명', '연주곡', '제목', 'title', 'piece'],
  composer: ['작곡가', '작곡', 'composer'],
  duration_sec: ['시간', '소요시간', '연주시간', '길이', 'duration', 'time'],
  level: ['난이도', '수준', '레벨', 'level', '급'],
  note: ['비고', '메모', '특징', '코멘트', 'note', 'memo'],
}

const LEVEL_ALIASES: { level: Level; keys: string[] }[] = [
  { level: 'ensemble', keys: ['앙상블', '듀엣', '듀오', '연탄', '2인', '합주', 'ensemble', 'duet'] },
  { level: 'advanced', keys: ['고급', '상급', '심화', 'advanced', 'a'] },
  { level: 'intermediate', keys: ['중급', '중', 'intermediate', 'b'] },
  { level: 'beginner', keys: ['기초', '초급', '입문', '초', 'beginner', 'c'] },
]

const clean = (v: string) => v.replace(/^["']|["']$/g, '').trim()
const norm = (v: string) => clean(v).toLowerCase().replace(/\s+/g, '')

export function parseLevel(raw: string | null | undefined): Level {
  const key = norm(raw ?? '')
  if (!key) return 'beginner'
  for (const entry of LEVEL_ALIASES) {
    if (entry.keys.some((k) => key === k || key.includes(k))) return entry.level
  }
  return 'beginner'
}

/**
 * 소요시간 표기를 초로 바꾼다.
 * "3:20" → 200 · "3분20초" → 200 · "3분" → 180 · "200초" → 200
 * 단위 없는 숫자는 20 이하면 분, 그보다 크면 초로 읽는다(20초짜리 연주곡은 없으므로).
 */
export function parseDurationSec(raw: string | null | undefined): number | null {
  const v = clean(raw ?? '')
  if (!v) return null

  const colon = v.match(/^(\d+)\s*:\s*(\d{1,2})$/)
  if (colon) return Number(colon[1]) * 60 + Number(colon[2])

  const korean = v.match(/^(?:(\d+)\s*분)?\s*(?:(\d+)\s*초)?$/)
  if (korean && (korean[1] || korean[2])) {
    return Number(korean[1] ?? 0) * 60 + Number(korean[2] ?? 0)
  }

  const secOnly = v.match(/^(\d+)\s*(?:sec|s|초)$/i)
  if (secOnly) return Number(secOnly[1])

  const minOnly = v.match(/^(\d+(?:\.\d+)?)\s*(?:min|m|분)$/i)
  if (minOnly) return Math.round(Number(minOnly[1]) * 60)

  const bare = v.match(/^(\d+(?:\.\d+)?)$/)
  if (bare) {
    const n = Number(bare[1])
    return n <= 20 ? Math.round(n * 60) : Math.round(n)
  }

  return null
}

function splitLine(line: string): string[] {
  if (line.includes('\t')) return line.split('\t')
  // 따옴표로 감싼 CSV 필드 안의 쉼표는 보존
  const out: string[] = []
  let cur = ''
  let quoted = false
  for (const ch of line) {
    if (ch === '"') quoted = !quoted
    else if (ch === ',' && !quoted) {
      out.push(cur)
      cur = ''
    } else cur += ch
  }
  out.push(cur)
  return out
}

function detectHeader(cells: string[]): Partial<Record<keyof RosterRow, number>> | null {
  const map: Partial<Record<keyof RosterRow, number>> = {}
  cells.forEach((cell, index) => {
    const key = norm(cell)
    if (!key) return
    for (const [field, aliases] of Object.entries(HEADER_ALIASES) as [keyof RosterRow, string[]][]) {
      if (map[field] !== undefined) continue
      if (aliases.some((a) => key === norm(a) || key.includes(norm(a)))) map[field] = index
    }
  })
  return map.student_name !== undefined && map.piece_title !== undefined ? map : null
}

/** 기본 열 순서: 이름 · 곡명 · 작곡가 · 시간 · 난이도 · 비고 */
const POSITIONAL: (keyof RosterRow)[] = ['student_name', 'piece_title', 'composer', 'duration_sec', 'level', 'note']

/** 엑셀 붙여넣기(TSV) 또는 CSV 텍스트를 학생 행으로 파싱한다 */
export function parseRoster(text: string): RosterParseResult {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0)

  const errors: string[] = []
  if (lines.length === 0) return { rows: [], errors: ['붙여넣은 내용이 없습니다.'], headerDetected: false }

  const first = splitLine(lines[0]).map(clean)
  const header = detectHeader(first)
  const body = header ? lines.slice(1) : lines

  const index: Record<keyof RosterRow, number> = {
    student_name: header?.student_name ?? POSITIONAL.indexOf('student_name'),
    piece_title: header?.piece_title ?? POSITIONAL.indexOf('piece_title'),
    composer: header?.composer ?? POSITIONAL.indexOf('composer'),
    duration_sec: header?.duration_sec ?? POSITIONAL.indexOf('duration_sec'),
    level: header?.level ?? POSITIONAL.indexOf('level'),
    note: header?.note ?? POSITIONAL.indexOf('note'),
  }

  const rows: RosterRow[] = []
  body.forEach((line, i) => {
    const cells = splitLine(line).map(clean)
    const lineNo = i + (header ? 2 : 1)
    const at = (field: keyof RosterRow) => {
      const pos = index[field]
      return pos >= 0 && pos < cells.length ? cells[pos] : ''
    }

    const name = at('student_name')
    const piece = at('piece_title')
    if (!name) {
      errors.push(`${lineNo}행: 학생 이름이 비어 있어 건너뛰었습니다.`)
      return
    }
    if (!piece) {
      errors.push(`${lineNo}행: ${name} 학생의 연주곡이 비어 있습니다. 곡명을 채워 주세요.`)
    }

    const rawDuration = at('duration_sec')
    const duration = parseDurationSec(rawDuration)
    if (rawDuration && duration === null) {
      errors.push(`${lineNo}행: 소요시간 "${rawDuration}" 을 읽지 못해 난이도 기준으로 추정합니다.`)
    }

    rows.push({
      student_name: name,
      piece_title: piece,
      composer: at('composer'),
      duration_sec: duration,
      level: parseLevel(at('level')),
      note: at('note') || null,
    })
  })

  if (rows.length === 0) errors.push('읽어 들인 학생이 없습니다. 이름·곡명 열이 있는지 확인해 주세요.')

  return { rows, errors, headerDetected: Boolean(header) }
}

/** 내보내기용 CSV (엑셀에서 한글이 깨지지 않도록 BOM 포함) */
export function toRosterCsv(rows: RosterRow[]): string {
  const esc = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v)
  const header = ['이름', '연주곡', '작곡가', '소요시간(초)', '난이도', '비고']
  const body = rows.map((r) =>
    [r.student_name, r.piece_title, r.composer, r.duration_sec ?? '', r.level, r.note ?? ''].map((v) => esc(String(v))).join(','),
  )
  return '﻿' + [header.join(','), ...body].join('\n')
}
