import { describe, expect, it } from 'vitest'
import {
  buildLiveList,
  driftLabel,
  driftLevel,
  EMPTY_LIVE_STATE,
  formatElapsed,
  liveStorageKey,
  parseLiveState,
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
    expect(parseLiveState(JSON.stringify({ index: 3, started_at: 1700 }), 10)).toEqual({
      index: 3,
      started_at: 1700,
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
