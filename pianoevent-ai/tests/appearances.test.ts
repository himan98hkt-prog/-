import { describe, expect, it } from 'vitest'
import { groupByPerformer, groupProgram, performerCount, performerKey, pieceIndex, sharePhotosByName } from '@/lib/program/appearances'
import { buildProgram } from '@/lib/program/order'
import { student } from './helpers'

describe('한 아이가 여러 곡을 맡을 때', () => {
  const roster = [
    student('김서연', 'beginner', 90, { id: 'a1', piece_title: '나비야', photo_asset_id: 'p1' }),
    student('박지호', 'beginner', 100, { id: 'b1', piece_title: '즐거운 나의 집' }),
    student('김서연', 'ensemble', 140, { id: 'a2', piece_title: '왕벌의 비행 (듀엣)' }),
    student('정예린', 'intermediate', 170, { id: 'c1', piece_title: '아라베스크' }),
  ]

  it('이름의 띄어쓰기가 달라도 같은 아이로 본다', () => {
    expect(performerKey('김 서연')).toBe(performerKey('김서연'))
    expect(performerKey(' KIM ')).toBe(performerKey('kim'))
  })

  it('사람 수와 곡 수를 따로 센다', () => {
    expect(performerCount(roster)).toBe(3)
    expect(roster).toHaveLength(4)
  })

  it('묶어도 처음 나온 차례를 지킨다', () => {
    const groups = groupByPerformer(roster)
    expect(groups.map((g) => g.name)).toEqual(['김서연', '박지호', '정예린'])
    expect(groups[0].rows.map((r) => r.id)).toEqual(['a1', 'a2'])
  })

  it('순서표를 사람 단위로 묶으면 순번이 함께 따라온다', () => {
    const plan = buildProgram(roster)
    const groups = groupProgram(plan.items)
    const seoyeon = groups.find((g) => g.name === '김서연')
    expect(seoyeon?.rows).toHaveLength(2)
    // 두 번 무대에 오르므로 순번도 둘이다
    expect(new Set(seoyeon?.rows.map((r) => r.order_no)).size).toBe(2)
  })

  it('몇 곡 중 몇 번째인지 알려 준다 — 한 곡뿐이면 알려 주지 않는다', () => {
    expect(pieceIndex(roster, roster[0])).toEqual({ index: 1, total: 2 })
    expect(pieceIndex(roster, roster[2])).toEqual({ index: 2, total: 2 })
    expect(pieceIndex(roster, roster[1])).toBeNull()
  })

  it('사진은 같은 이름끼리 나눠 쓴다 — 곡마다 다시 올리게 하지 않는다', () => {
    const shared = sharePhotosByName({ a1: '사진A' }, roster)
    expect(shared.a2).toBe('사진A')
    expect(shared.b1).toBeUndefined()
  })

  it('줄마다 사진을 따로 넣었으면 그대로 둔다 — 독주 사진과 듀엣 사진이 다를 수 있다', () => {
    const shared = sharePhotosByName({ a1: '사진A', a2: '사진B' }, roster)
    expect(shared.a1).toBe('사진A')
    expect(shared.a2).toBe('사진B')
  })

  it('사진이 하나도 없으면 아무것도 지어내지 않는다', () => {
    expect(sharePhotosByName({}, roster)).toEqual({})
  })
})
