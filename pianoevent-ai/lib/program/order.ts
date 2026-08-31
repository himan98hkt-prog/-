import {
  DEFAULT_PROGRAM_OPTIONS,
  type EventStudent,
  type Level,
  type ProgramBreak,
  type ProgramItem,
  type ProgramOptions,
  type ProgramPlan,
  type Stage,
} from '@/lib/types'

/** 소요시간 미입력 시 난이도로 추정하는 기본값(초) */
export const DEFAULT_DURATION_SEC: Record<Level, number> = {
  beginner: 90,
  intermediate: 180,
  advanced: 300,
  ensemble: 210,
}

const LEVEL_WEIGHT: Record<Level, number> = {
  beginner: 0,
  intermediate: 1,
  advanced: 2,
  ensemble: 1.5,
}

export function estimateDurationSec(level: Level, given?: number | null): number {
  if (typeof given === 'number' && Number.isFinite(given) && given > 0) return Math.round(given)
  return DEFAULT_DURATION_SEC[level]
}

/** 정렬 전 정규화: 소요시간 보정 */
export function normalizeStudents(students: EventStudent[]): EventStudent[] {
  return students.map((s) => ({ ...s, duration_sec: estimateDurationSec(s.level, s.duration_sec) }))
}

function byDurationAsc(a: EventStudent, b: EventStudent) {
  if (a.duration_sec !== b.duration_sec) return a.duration_sec - b.duration_sec
  return a.student_name.localeCompare(b.student_name, 'ko')
}

function byWeightThenDuration(a: EventStudent, b: EventStudent) {
  const w = LEVEL_WEIGHT[a.level] - LEVEL_WEIGHT[b.level]
  if (w !== 0) return w
  return byDurationAsc(a, b)
}

const norm = (v: string | null | undefined) => (v ?? '').trim().toLowerCase()

/**
 * 인접한 두 곡이 같은 작곡가이거나 같은 학생이면 지루하다.
 * 같은 구간(stage) 안에서만 뒤쪽 후보와 자리를 바꿔 충돌을 푼다(구간 순서는 절대 깨지 않는다).
 */
export function relaxAdjacency(seq: { student: EventStudent; stage: Stage }[]) {
  const clash = (a: EventStudent, b: EventStudent) =>
    norm(a.student_name) === norm(b.student_name) ||
    (norm(a.composer) !== '' && norm(a.composer) === norm(b.composer))

  for (let i = 1; i < seq.length; i++) {
    if (!clash(seq[i - 1].student, seq[i].student)) continue
    for (let j = i + 1; j < seq.length; j++) {
      if (seq[j].stage !== seq[i].stage) break
      const candidate = seq[j].student
      const prevOk = !clash(seq[i - 1].student, candidate)
      const nextOk = j + 1 >= seq.length || !clash(candidate, seq[j + 1].student)
      const movedOk = !clash(seq[i].student, seq[j - 1].student) || j - 1 === i
      if (prevOk && nextOk && movedOk) {
        const tmp = seq[i]
        seq[i] = seq[j]
        seq[j] = tmp
        break
      }
    }
  }
  return seq
}

/** 순서가 확정된 목록에 시각(오프셋)과 휴식을 얹는다. AI 순서·수동 순서에도 같은 함수를 쓴다. */
export function layoutProgram(
  seq: { student: EventStudent; stage: Stage }[],
  options: ProgramOptions = DEFAULT_PROGRAM_OPTIONS,
): { items: ProgramItem[]; breaks: ProgramBreak[]; play_sec: number; total_sec: number } {
  const items: ProgramItem[] = []
  const breaks: ProgramBreak[] = []
  let cursor = 0
  let play = 0
  let intermissionDone = options.intermission_sec <= 0

  seq.forEach((entry, index) => {
    const duration = estimateDurationSec(entry.student.level, entry.student.duration_sec)

    // 마지막 곡 앞에는 휴식을 넣지 않는다 (피날레 직전에 끊지 않기)
    if (!intermissionDone && cursor >= options.intermission_after_sec && index < seq.length - 1) {
      breaks.push({
        after_order_no: index,
        start_offset_sec: cursor,
        duration_sec: options.intermission_sec,
        label: '중간 휴식',
      })
      cursor += options.intermission_sec
      intermissionDone = true
    }

    items.push({
      student: { ...entry.student, duration_sec: duration, order_no: index + 1 },
      order_no: index + 1,
      stage: entry.stage,
      start_offset_sec: cursor,
      duration_sec: duration,
    })

    play += duration
    cursor += duration
    if (index < seq.length - 1) cursor += options.turnover_sec
  })

  return { items, breaks, play_sec: play, total_sec: cursor }
}

function collectWarnings(
  items: ProgramItem[],
  total_sec: number,
  options: ProgramOptions,
): string[] {
  const warnings: string[] = []

  if (total_sec > options.max_total_sec) {
    warnings.push(
      `예상 러닝타임 ${Math.round(total_sec / 60)}분 — 권장 ${Math.round(
        options.max_total_sec / 60,
      )}분을 넘습니다. 곡 수를 줄이거나 1·2부로 나누세요.`,
    )
  }

  const counts = new Map<string, number>()
  for (const item of items) {
    const key = item.student.student_name.trim()
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  for (const [name, count] of counts) {
    if (count >= 3) warnings.push(`${name} 학생이 ${count}회 무대에 오릅니다. 부담이 크지 않은지 확인하세요.`)
  }

  for (let i = 1; i < items.length; i++) {
    if (items[i].student.student_name.trim() === items[i - 1].student.student_name.trim()) {
      warnings.push(`${items[i].student.student_name} 학생이 연속 두 곡을 연주합니다. 사이에 다른 곡을 넣는 편이 좋습니다.`)
    }
  }

  for (const item of items) {
    if (!item.student.composer.trim()) {
      warnings.push(`${item.student.piece_title} — 작곡가가 비어 있어 곡 해설이 단순해집니다.`)
    }
    if (item.duration_sec > 10 * 60) {
      warnings.push(
        `${item.student.student_name} · ${item.student.piece_title} 은 ${Math.round(
          item.duration_sec / 60,
        )}분입니다. 발췌 연주를 검토하세요.`,
      )
    }
  }

  return [...new Set(warnings)]
}

/**
 * 규칙 기반 순서 배치 엔진.
 * AI 키가 없어도, AI 응답이 실패해도 원장은 이 결과만으로 순서표를 뽑을 수 있어야 한다.
 */
export function buildProgram(
  input: EventStudent[],
  options: ProgramOptions = DEFAULT_PROGRAM_OPTIONS,
): ProgramPlan {
  const students = normalizeStudents(input)
  if (students.length === 0) {
    return { items: [], breaks: [], play_sec: 0, total_sec: 0, warnings: ['학생 명단이 비어 있습니다.'] }
  }

  const pool = [...students]
  const take = (predicate: (s: EventStudent) => boolean, pick: (a: EventStudent, b: EventStudent) => number) => {
    const candidates = pool.filter(predicate).sort(pick)
    const chosen = candidates[0]
    if (!chosen) return null
    pool.splice(pool.indexOf(chosen), 1)
    return chosen
  }

  const seq: { student: EventStudent; stage: Stage }[] = []

  // 오프닝: 무대가 얼어붙지 않도록 "짧고 안정적인 중급 이상" 한 곡. 없으면 가장 짧은 곡.
  if (students.length >= 3) {
    const opening =
      take((s) => s.level === 'intermediate' && s.duration_sec <= 210, byDurationAsc) ??
      take((s) => s.level === 'intermediate', byDurationAsc) ??
      take((s) => s.level === 'advanced', byDurationAsc)
    if (opening) seq.push({ student: opening, stage: 'opening' })
  }

  // 피날레: 가장 어렵고 긴 솔로 한 곡을 마지막에 남겨 둔다.
  let finale: EventStudent | null = null
  if (students.length >= 3) {
    finale =
      take((s) => s.level === 'advanced', (a, b) => byDurationAsc(b, a)) ??
      take((s) => s.level === 'intermediate', (a, b) => byDurationAsc(b, a))
  }

  const beginners = pool.filter((s) => s.level === 'beginner').sort(byDurationAsc)
  const middles = pool.filter((s) => s.level === 'intermediate' || s.level === 'advanced').sort(byWeightThenDuration)
  const ensembles = pool.filter((s) => s.level === 'ensemble').sort(byDurationAsc)

  beginners.forEach((s) => seq.push({ student: s, stage: 'beginner' }))
  middles.forEach((s) => seq.push({ student: s, stage: 'intermediate' }))
  ensembles.forEach((s) => seq.push({ student: s, stage: 'ensemble' }))
  if (finale) seq.push({ student: finale, stage: 'finale' })

  relaxAdjacency(seq)

  const laid = layoutProgram(seq, options)
  return { ...laid, warnings: collectWarnings(laid.items, laid.total_sec, options) }
}

/**
 * AI 가 돌려준 순서(학생 id 배열)를 실제 배치로 확정한다.
 * AI 가 빠뜨리거나 지어낸 id 가 있어도 전체가 무너지지 않게 보정한다.
 */
export function applyOrder(
  input: EventStudent[],
  orderedIds: string[],
  options: ProgramOptions = DEFAULT_PROGRAM_OPTIONS,
): ProgramPlan {
  const students = normalizeStudents(input)
  const byId = new Map(students.map((s) => [s.id, s]))
  const seen = new Set<string>()
  const ordered: EventStudent[] = []

  for (const id of orderedIds) {
    const found = byId.get(id)
    if (found && !seen.has(id)) {
      ordered.push(found)
      seen.add(id)
    }
  }
  // AI 응답에서 누락된 학생은 원래 입력 순서대로 뒤에 붙인다 — 아무도 무대를 잃지 않도록
  for (const s of students) if (!seen.has(s.id)) ordered.push(s)

  const seq = ordered.map((student, index) => ({
    student,
    stage: stageFor(index, ordered.length, student),
  }))

  const laid = layoutProgram(seq, options)
  return { ...laid, warnings: collectWarnings(laid.items, laid.total_sec, options) }
}

function stageFor(index: number, length: number, student: EventStudent): Stage {
  if (length >= 3 && index === 0) return 'opening'
  if (length >= 3 && index === length - 1) return 'finale'
  if (student.level === 'ensemble') return 'ensemble'
  if (student.level === 'beginner') return 'beginner'
  return 'intermediate'
}
