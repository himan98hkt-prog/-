import { describe, expect, it } from 'vitest'
import {
  EDIT_KEEP,
  describeChange,
  describeEdit,
  fieldLabel,
  popEdit,
  pushEdit,
  restorePatch,
  type RosterEdit,
} from '@/lib/program/edit-log'

const edit = (partial: Partial<RosterEdit> = {}): RosterEdit => ({
  student_id: 's1',
  student_name: '김서연',
  field: 'piece_title',
  before: '엘리제를 위하여',
  after: '소나티네',
  ...partial,
})

describe('고친 것 쌓기', () => {
  it('가장 최근 것이 맨 앞에 온다', () => {
    const log = pushEdit(pushEdit([], edit({ field: 'composer' })), edit({ field: 'piece_title' }))
    expect(log[0].field).toBe('piece_title')
  })

  it('열 번까지만 쌓는다 — 더 거슬러 올라가시는 일은 없다', () => {
    let log: RosterEdit[] = []
    for (let i = 0; i < 30; i += 1) log = pushEdit(log, edit({ before: `전${i}`, after: `후${i}` }))
    expect(log).toHaveLength(EDIT_KEEP)
    expect(log[0].after).toBe('후29')
  })

  it('값이 그대로면 쌓지 않는다 — 칸을 눌렀다 그냥 나오신 것도 저장으로 들어온다', () => {
    expect(pushEdit([], edit({ before: '같은값', after: '같은값' }))).toHaveLength(0)
  })

  it('빈칸과 null 은 같은 것으로 본다', () => {
    expect(pushEdit([], edit({ before: null, after: null }))).toHaveLength(0)
    expect(pushEdit([], edit({ before: '', after: '' }))).toHaveLength(0)
  })

  it('사진 목록도 같으면 쌓지 않는다', () => {
    expect(pushEdit([], edit({ field: 'photo_asset_ids', before: ['a', 'b'], after: ['a', 'b'] }))).toHaveLength(0)
    expect(pushEdit([], edit({ field: 'photo_asset_ids', before: ['a'], after: ['a', 'b'] }))).toHaveLength(1)
  })
})

describe('되돌릴 것 꺼내기', () => {
  it('맨 앞 것을 꺼내고 나머지를 남긴다', () => {
    const log = [edit({ field: 'a' }), edit({ field: 'b' })]
    const { edit: got, rest } = popEdit(log)
    expect(got?.field).toBe('a')
    expect(rest).toHaveLength(1)
  })

  it('비어 있으면 아무것도 주지 않는다 — 눌러도 아무 일이 없어야 한다', () => {
    expect(popEdit([]).edit).toBeNull()
  })
})

describe('원장님이 읽으실 말로', () => {
  it('칸 이름을 화면에서 보시는 낱말로 적는다', () => {
    expect(fieldLabel('piece_title')).toBe('연주곡')
    expect(fieldLabel('duration_sec')).toBe('소요시간')
  })

  it('모르는 칸은 그대로 둔다 — 빈칸보다 낫다', () => {
    expect(fieldLabel('알수없음')).toBe('알수없음')
  })

  it('누구의 어느 칸인지 한 줄로 말해 준다', () => {
    expect(describeEdit(edit())).toBe('김서연 · 연주곡')
  })

  it('무엇에서 무엇으로 되돌아가는지 보여 준다', () => {
    expect(describeChange(edit())).toBe('소나티네 → 엘리제를 위하여')
  })

  it('난이도는 우리말로 적는다 — beginner 라고 적으면 못 읽으신다', () => {
    expect(describeChange(edit({ field: 'level', before: 'beginner', after: 'advanced' }))).toBe('고급 → 기초·초급')
  })

  it('소요시간은 분·초로 적는다', () => {
    expect(describeChange(edit({ field: 'duration_sec', before: 210, after: 70 }))).toBe('1분 10초 → 3분 30초')
  })

  it('빈칸은 빈칸이라고 적는다 — 아무것도 안 보이면 무슨 일인지 모르신다', () => {
    expect(describeChange(edit({ before: '', after: '소나티네' }))).toBe('소나티네 → (빈칸)')
  })

  it('긴 곡명은 줄인다', () => {
    const long = '가'.repeat(50)
    expect(describeChange(edit({ before: long, after: '짧은곡' }))).toContain('…')
  })
})

describe('되돌릴 때 보낼 것', () => {
  it('보통은 고친 칸 하나만 되돌린다', () => {
    expect(restorePatch(edit())).toEqual({ piece_title: '엘리제를 위하여' })
  })

  it('두 칸이 함께 바뀐 것은 함께 되돌린다 — 사진은 대표와 목록이 같이 바뀐다', () => {
    const photo = edit({
      field: 'photo_asset_ids',
      restore: { photo_asset_id: 'p1', photo_asset_ids: ['p1', 'p2'] },
    })
    expect(restorePatch(photo)).toEqual({ photo_asset_id: 'p1', photo_asset_ids: ['p1', 'p2'] })
  })
})
