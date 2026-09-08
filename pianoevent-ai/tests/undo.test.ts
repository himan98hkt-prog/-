import { describe, expect, it, vi } from 'vitest'
import {
  UNDO_KEEP,
  UNDO_TTL_MS,
  forScreen,
  keepable,
  popUndo,
  pushUndo,
  undoLine,
  usable,
  type UndoAction,
} from '@/lib/undo/stack'

const action = (partial: Partial<UndoAction> = {}): UndoAction => ({
  id: 'roster:paste',
  what: '명단 붙여넣기',
  run: vi.fn(),
  ...partial,
})

describe('되돌릴 것 쌓기', () => {
  it('가장 최근 것이 맨 앞에 온다', () => {
    const stack = pushUndo(pushUndo([], action({ id: 'a' })), action({ id: 'b' }))
    expect(stack[0].id).toBe('b')
  })

  it('같은 것을 두 번 하면 하나로 남는다 — 목록이 같은 말로 채워지면 못 읽으신다', () => {
    const stack = pushUndo(pushUndo([], action({ id: 'roster:paste' })), action({ id: 'roster:paste' }))
    expect(stack).toHaveLength(1)
  })

  it('열 번까지만 쌓는다', () => {
    let stack: UndoAction[] = []
    for (let i = 0; i < 30; i += 1) stack = pushUndo(stack, action({ id: `edit:${i}` }))
    expect(stack).toHaveLength(UNDO_KEEP)
  })
})

describe('되돌릴 것 꺼내기', () => {
  it('맨 앞 것을 꺼내고 나머지를 남긴다', () => {
    const { action: got, rest } = popUndo([action({ id: 'a' }), action({ id: 'b' })])
    expect(got?.id).toBe('a')
    expect(rest).toHaveLength(1)
  })

  it('비어 있으면 아무것도 주지 않는다 — 눌러도 아무 일이 없어야 한다', () => {
    expect(popUndo([]).action).toBeNull()
  })
})

describe('화면을 옮기실 때', () => {
  it('그 화면에서 하신 것만 남긴다 — 다른 화면 일을 여기서 되돌리면 놀라신다', () => {
    const stack = [action({ id: 'roster:paste' }), action({ id: 'program:order' })]
    expect(forScreen(stack, 'roster').map((a) => a.id)).toEqual(['roster:paste'])
  })

  it('그 화면 것이 없으면 띠가 아예 안 뜬다', () => {
    expect(forScreen([action({ id: 'roster:paste' })], 'design')).toEqual([])
  })
})

describe('띠에 적을 말', () => {
  it('무엇을 하셨는지와 되돌리면 어떻게 되는지를 함께 적는다', () => {
    expect(undoLine(action({ what: '김서연 · 연주곡', detail: '소나티네 → 엘리제를 위하여' }))).toBe(
      '김서연 · 연주곡 (소나티네 → 엘리제를 위하여)',
    )
  })

  it('되돌린 뒤 모습을 모르면 무엇을 하셨는지만 적는다', () => {
    expect(undoLine(action({ what: '명단 붙여넣기' }))).toBe('명단 붙여넣기')
  })
})

describe('화면을 옮겨도 되돌릴 수 있게', () => {
  const req = (id: string, extra: Partial<UndoAction> = {}): UndoAction => ({
    id,
    what: '명단 붙여넣기',
    request: { url: '/api/x', method: 'POST', body: { a: 1 } },
    ...extra,
  })

  it('요청으로 적어 둔 것만 남긴다 — 함수는 화면을 옮기면 사라진다', () => {
    const stack = [req('a'), { id: 'b', what: '함수뿐', run: vi.fn() }]
    expect(keepable(stack).map((a) => a.id)).toEqual(['a'])
  })

  it('이 행사에서 하신 것만 보여 준다 — 다른 행사 일을 여기서 되돌리면 안 된다', () => {
    const stack = [req('a', { eventId: 'e1' }), req('b', { eventId: 'e2' })]
    expect(usable(stack, 'e1').map((a) => a.id)).toEqual(['a'])
  })

  it('어느 행사인지 안 적힌 것은 그대로 둔다', () => {
    expect(usable([req('a')], 'e1')).toHaveLength(1)
  })

  it('오래된 것은 스스로 사라진다 — 어제 일을 오늘 되돌리면 놀라신다', () => {
    const now = Date.parse('2026-08-28T12:00:00Z')
    const old = req('a', { at: now - UNDO_TTL_MS - 1 })
    const fresh = req('b', { at: now - 1000 })
    expect(usable([old, fresh], 'e1', now).map((a) => a.id)).toEqual(['b'])
  })
})
