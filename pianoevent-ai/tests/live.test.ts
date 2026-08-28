import { describe, expect, it } from 'vitest'
import {
  actualRows,
  actualSeconds,
  buildLiveList,
  driftLabel,
  driftLevel,
  durationUpdates,
  elapsedAtIndex,
  elapsedTotal,
  EMPTY_LIVE_STATE,
  formatElapsed,
  LIVE_CODE_ALPHABET,
  LIVE_CODE_LENGTH,
  liveCodeAllows,
  liveStorageKey,
  makeLiveCode,
  moveLive,
  normalizeLiveCode,
  namedDurations,
  newerLiveState,
  normalizeLiveState,
  parseLiveState,
  progressLabel,
  startLive,
} from '@/lib/ops/live'
import { buildProgram } from '@/lib/program/order'
import { DEFAULT_PROGRAM_OPTIONS } from '@/lib/types'
import { student } from './helpers'

const roster = [
  student('김서연', 'beginner', 90, { piece_title: '나비야', composer: '전래' }),
  student('박지호', 'beginner', 100, { piece_title: '즐거운 나의 집' }),
  student('정예린', 'intermediate', 170, { piece_title: '아라베스크' }),
  student('윤채원', 'advanced', 260, { piece_title: '녹턴', composer: '쇼팽' }),
]
const plan = buildProgram(roster)

describe('당일 진행 화면', () => {
  it('연주 순서를 그대로 한 줄씩 늘어놓는다', () => {
    const list = buildLiveList(plan)
    expect(list).toHaveLength(plan.items.length)
    expect(list.map((row) => row.order_no)).toEqual(plan.items.map((item) => item.order_no))
  })

  it('이름과 곡을 나눠 담는다 — 큰 글씨는 이름이어야 한다', () => {
    const first = buildLiveList(plan)[0]
    expect(first.title).toBe(plan.items[0].student.student_name)
    expect(first.detail).toContain(plan.items[0].student.piece_title)
  })

  it('중간 휴식도 한 자리를 차지한다 — 넘기다 건너뛰지 않게', () => {
    const many = Array.from({ length: 30 }, (_, i) => student(`학생${i}`, 'intermediate', 200))
    const long = buildProgram(many, { ...DEFAULT_PROGRAM_OPTIONS, intermission_after_sec: 600, intermission_sec: 600 })
    expect(long.breaks.length).toBeGreaterThan(0)
    const list = buildLiveList(long)
    expect(list).toHaveLength(long.items.length + long.breaks.length)
    const brk = list.find((row) => row.kind === 'break')
    expect(brk?.order_no).toBeNull()
    // 휴식은 그 앞 순서와 뒤 순서 사이에 놓인다
    const at = list.findIndex((row) => row.kind === 'break')
    expect(list[at - 1].kind).toBe('item')
    expect(list[at + 1].kind).toBe('item')
  })

  it('밀린 정도를 분 단위로만 말한다 — 초 단위로 떨리면 불안해진다', () => {
    expect(driftLabel(100, 90)).toBe('예정대로')
    expect(driftLabel(300, 120)).toBe('예정보다 3분 늦음')
    expect(driftLabel(120, 300)).toBe('예정보다 3분 빠름')
  })

  it('많이 밀리면 화면이 경고로 바뀐다', () => {
    expect(driftLevel(0, 0)).toBe('ok')
    expect(driftLevel(5 * 60, 0)).toBe('warn')
    expect(driftLevel(12 * 60, 0)).toBe('late')
    // 예정보다 빠른 것은 문제가 아니다
    expect(driftLevel(0, 20 * 60)).toBe('ok')
  })

  it('경과 시간은 분:초로 보여 준다', () => {
    expect(formatElapsed(0)).toBe('0:00')
    expect(formatElapsed(65)).toBe('1:05')
    expect(formatElapsed(-5)).toBe('0:00')
  })

  it('담아 둔 진행 상태를 되읽는다', () => {
    expect(parseLiveState(JSON.stringify({ index: 3, started_at: 1700, marks: [1700], updated_at: 9 }), 10)).toEqual({
      index: 3,
      started_at: 1700,
      marks: [1700],
      updated_at: 9,
    })
  })

  it('예전에 담아 둔 것(넘긴 시각이 없던 때)도 그대로 열린다', () => {
    // 지난 판으로 쓰시다 새 판으로 올리셔도 당일에 화면이 비면 안 된다
    expect(parseLiveState(JSON.stringify({ index: 2, started_at: 1700 }), 10)).toEqual({
      index: 2,
      started_at: 1700,
      marks: [],
      updated_at: 0,
    })
  })

  it('명단이 줄었으면 마지막 순서로 당겨 온다 — 빈 화면이 뜨지 않게', () => {
    expect(parseLiveState(JSON.stringify({ index: 99, started_at: null }), 4).index).toBe(3)
  })

  it('담긴 것이 망가져 있어도 당일에 오류 화면을 보이지 않는다', () => {
    expect(parseLiveState('{망가짐', 5)).toEqual(EMPTY_LIVE_STATE)
    expect(parseLiveState(null, 5)).toEqual(EMPTY_LIVE_STATE)
    expect(parseLiveState(JSON.stringify({ index: '셋', started_at: '어제' }), 5)).toEqual(EMPTY_LIVE_STATE)
  })

  it('행사마다 따로 담는다 — 지난 행사 진행 상태가 섞이지 않게', () => {
    expect(liveStorageKey('e1')).not.toBe(liveStorageKey('e2'))
  })
})

describe('당일 진행 — 넘긴 시각과 함께 보기', () => {
  const list = buildLiveList(plan)
  const T0 = 1_700_000_000_000

  it('개회하면 시계가 켜지고 첫 순서에 표가 찍힌다', () => {
    const state = startLive(T0)
    expect(state.started_at).toBe(T0)
    expect(state.marks).toEqual([T0])
    expect(state.index).toBe(0)
  })

  it('넘길 때마다 시각이 쌓여 실제 걸린 시간이 남는다', () => {
    let state = startLive(T0)
    state = moveLive(state, 1, T0 + 100_000, list.length)
    state = moveLive(state, 2, T0 + 260_000, list.length)
    expect(actualSeconds(state, 0)).toBe(100)
    expect(actualSeconds(state, 1)).toBe(160)
    // 지금 진행 중인 순서는 아직 모른다 — 지어내지 않는다
    expect(actualSeconds(state, 2)).toBeNull()
  })

  it('되돌아가면 그 뒤에 적어 둔 시각을 지운다 — 잘못 눌렀다는 뜻이다', () => {
    let state = startLive(T0)
    state = moveLive(state, 1, T0 + 100_000, list.length)
    state = moveLive(state, 2, T0 + 200_000, list.length)
    state = moveLive(state, 1, T0 + 205_000, list.length)
    expect(state.index).toBe(1)
    expect(actualSeconds(state, 1)).toBeNull()
    // 앞의 것은 그대로 남는다
    expect(actualSeconds(state, 0)).toBe(100)
  })

  it('개회 전에 넘겨도 시각을 지어내지 않는다', () => {
    const state = moveLive(EMPTY_LIVE_STATE, 3, T0, list.length)
    expect(state.index).toBe(3)
    expect(state.started_at).toBeNull()
    expect(state.marks).toEqual([])
  })

  it('순서표 끝을 넘어가지 않는다', () => {
    const state = moveLive(startLive(T0), 999, T0 + 1000, list.length)
    expect(state.index).toBe(list.length - 1)
  })

  it('함께 보기 — 나중에 손댄 쪽이 이긴다', () => {
    const mine = { ...startLive(T0), updated_at: T0 }
    const theirs = { ...startLive(T0), index: 5, updated_at: T0 + 5000 }
    expect(newerLiveState(mine, theirs)).toBe(theirs)
    expect(newerLiveState(theirs, mine)).toBe(theirs)
  })

  it('서버에서 온 이상한 값에 화면이 무너지지 않는다', () => {
    expect(normalizeLiveState({ index: '셋', marks: ['어제', 5, -1], started_at: 0 }, 10)).toEqual(EMPTY_LIVE_STATE)
    expect(normalizeLiveState(null, 10)).toEqual(EMPTY_LIVE_STATE)
    expect(normalizeLiveState([1, 2], 10)).toEqual(EMPTY_LIVE_STATE)
  })

  it('뒤죽박죽인 시각은 앞뒤가 맞는 데까지만 쓴다', () => {
    const state = normalizeLiveState({ index: 2, started_at: T0, marks: [T0, T0 + 5000, T0 - 9999], updated_at: 1 }, 10)
    expect(state.marks).toEqual([T0, T0 + 5000])
  })

  it('실제 시간이 예정과 다르면 명단에 되돌릴 값을 뽑아 준다', () => {
    let state = startLive(T0)
    // 첫 곡이 예정보다 한참 길게 걸렸다
    state = moveLive(state, 1, T0 + 240_000, list.length)
    state = moveLive(state, 2, T0 + 340_000, list.length)
    const rows = actualRows(list, state)
    expect(rows).toHaveLength(2)
    expect(rows[0].actual_sec).toBe(240)
    const updates = durationUpdates(rows)
    expect(updates[0]).toEqual({ student_id: list[0].student_id, duration_sec: 240 })
  })

  it('잘못 누른 것으로 보이는 시간은 명단에 되돌리지 않는다', () => {
    let state = startLive(T0)
    // 3초 만에 넘겼다 — 무대에 오르지도 못했다
    state = moveLive(state, 1, T0 + 3_000, list.length)
    // 40분을 머물렀다 — 넘기는 걸 잊으셨다
    state = moveLive(state, 2, T0 + 3_000 + 40 * 60_000, list.length)
    expect(durationUpdates(actualRows(list, state))).toEqual([])
  })

  it('예정과 거의 같으면 굳이 고치지 않는다', () => {
    let state = startLive(T0)
    state = moveLive(state, 1, T0 + list[0].planned_sec * 1000 + 3000, list.length)
    expect(durationUpdates(actualRows(list, state))).toEqual([])
  })

  it('휴식은 명단에 되돌릴 것이 없다', () => {
    const many = Array.from({ length: 30 }, (_, i) => student(`학생${i}`, 'intermediate', 200))
    const long = buildProgram(many, { ...DEFAULT_PROGRAM_OPTIONS, intermission_after_sec: 600, intermission_sec: 600 })
    const rows = buildLiveList(long)
    const at = rows.findIndex((row) => row.kind === 'break')
    let state = startLive(T0)
    for (let i = 1; i <= at + 1; i += 1) state = moveLive(state, i, T0 + i * 200_000, rows.length)
    const actual = actualRows(rows, state)
    expect(actual.find((row) => row.entry.kind === 'break')?.usable).toBe(false)
  })

  it('이름과 함께 몇 초에서 몇 초로 바뀌는지 보여 준다', () => {
    let state = startLive(T0)
    state = moveLive(state, 1, T0 + 240_000, list.length)
    state = moveLive(state, 2, T0 + 340_000, list.length)
    const named = namedDurations(actualRows(list, state), plan.items.map((item) => item.student))
    expect(named[0].name).toBe(list[0].title)
    expect(named[0].after).toBe(240)
    expect(named[0].before).toBe(list[0].planned_sec)
  })

  it('진행 상황을 한 줄로 말해 준다', () => {
    let state = startLive(T0)
    state = moveLive(state, 1, T0 + 100_000, list.length)
    expect(progressLabel(list, state)).toBe(`${list.length}개 중 1개를 마쳤습니다`)
  })

  it('이 순서를 시작한 지 몇 초 지났는지 따로 센다 — 전체 경과와 다르다', () => {
    let state = startLive(T0)
    state = moveLive(state, 1, T0 + 100_000, list.length)
    expect(elapsedTotal(state, T0 + 130_000)).toBe(130)
    expect(elapsedAtIndex(state, 1, T0 + 130_000)).toBe(30)
  })
})

describe('따라보기 열쇠', () => {
  it('헷갈리는 글자를 쓰지 않는다 — 무대 옆에서 손으로 옮겨 적을 수도 있다', () => {
    for (const bad of ['O', '0', 'I', '1', 'L']) expect(LIVE_CODE_ALPHABET).not.toContain(bad)
  })

  it('코드는 정해진 길이로 나온다', () => {
    const code = makeLiveCode()
    expect(code).toHaveLength(LIVE_CODE_LENGTH)
    expect(code.split('').every((ch) => LIVE_CODE_ALPHABET.includes(ch))).toBe(true)
  })

  it('만들 때마다 다르다', () => {
    const seen = new Set(Array.from({ length: 50 }, () => makeLiveCode()))
    expect(seen.size).toBeGreaterThan(40)
  })

  it('소문자로 적으셔도 알아본다', () => {
    expect(normalizeLiveCode('ab23cd')).toBe('AB23CD')
    expect(normalizeLiveCode(' AB 23 CD ')).toBe('AB23CD')
  })

  it('짧거나 아는 글자가 아니면 받지 않는다', () => {
    expect(normalizeLiveCode('AB')).toBeNull()
    expect(normalizeLiveCode('!!!!!!')).toBeNull()
    expect(normalizeLiveCode(1234)).toBeNull()
    expect(normalizeLiveCode(null)).toBeNull()
  })

  it('코드를 걸지 않으면 링크를 아는 누구나 본다', () => {
    expect(liveCodeAllows(null, undefined)).toBe(true)
    expect(liveCodeAllows('', 'AAAA')).toBe(true)
  })

  it('코드를 걸면 맞는 코드만 통과한다', () => {
    expect(liveCodeAllows('AB23CD', 'AB23CD')).toBe(true)
    expect(liveCodeAllows('AB23CD', 'ab23cd')).toBe(true)
    expect(liveCodeAllows('AB23CD', 'AB23CE')).toBe(false)
    expect(liveCodeAllows('AB23CD', undefined)).toBe(false)
    expect(liveCodeAllows('AB23CD', '')).toBe(false)
  })
})
