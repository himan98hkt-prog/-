import { describe, expect, it } from 'vitest'
import { carryPhotoIds, STUDENT_PHOTO_MAX, studentPhotoList, studentPhotos } from '@/lib/assets'
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

describe('아이 사진 여러 장 고르기', () => {
  const assets = [
    { id: 'a1', kind: 'photo' as const, label: '서연 1', url: 'u1', created_at: '' },
    { id: 'a2', kind: 'photo' as const, label: '서연 2', url: 'u2', created_at: '' },
    { id: 'gone', kind: 'photo' as const, label: '지운 것', url: 'u3', created_at: '' },
  ]
  const rows = [
    { id: 's1', photo_asset_id: 'a1', photo_asset_ids: ['a1', 'a2'] },
    { id: 's2', photo_asset_id: 'a2', photo_asset_ids: null },
    { id: 's3', photo_asset_id: null, photo_asset_ids: null },
  ]

  it('대표 사진이 늘 맨 앞이다 — 무대 화면과 파워포인트는 한 장만 쓴다', () => {
    expect(studentPhotoList(assets, rows).s1).toEqual(['u1', 'u2'])
  })

  it('한 장만 있으면 한 장짜리 목록', () => {
    expect(studentPhotoList(assets, rows).s2).toEqual(['u2'])
  })

  it('사진이 없는 아이는 아예 담지 않는다', () => {
    expect(studentPhotoList(assets, rows).s3).toBeUndefined()
  })

  it('보관함에서 지운 사진은 건너뛴다 — 빈 상자가 뜨지 않게', () => {
    const withDeleted = [{ id: 's4', photo_asset_id: 'a1', photo_asset_ids: ['a1', '없는것'] }]
    expect(studentPhotoList(assets, withDeleted).s4).toEqual(['u1'])
  })

  it('같은 사진을 두 번 넣어 두셨어도 한 번만 나온다', () => {
    const dupe = [{ id: 's5', photo_asset_id: 'a1', photo_asset_ids: ['a1', 'a1', 'a2'] }]
    expect(studentPhotoList(assets, dupe).s5).toEqual(['u1', 'u2'])
  })

  it('한 아이당 정해진 장수까지만', () => {
    const many = Array.from({ length: 20 }, (_, i) => ({
      id: `x${i}`,
      kind: 'photo' as const,
      label: `${i}`,
      url: `u${i}`,
      created_at: '',
    }))
    const row = [{ id: 's6', photo_asset_id: 'x0', photo_asset_ids: many.map((a) => a.id) }]
    expect(studentPhotoList(many, row).s6).toHaveLength(STUDENT_PHOTO_MAX)
  })

  it('대표 사진만 쓰는 화면은 예전 그대로 한 장을 본다', () => {
    expect(studentPhotos(assets, rows)).toEqual({ s1: 'u1', s2: 'u2' })
  })
})

describe('지난 행사에서 명단을 가져올 때 사진', () => {
  const assets = [
    { id: 'a1', kind: 'photo' as const, label: '1', url: 'u1', created_at: '' },
    { id: 'a2', kind: 'photo' as const, label: '2', url: 'u2', created_at: '' },
  ]

  it('대표 사진이 맨 앞인 채로 그대로 물려준다', () => {
    expect(carryPhotoIds(assets, { photo_asset_id: 'a1', photo_asset_ids: ['a1', 'a2'] })).toEqual(['a1', 'a2'])
  })

  it('그 사이 보관함에서 지운 사진은 뺀다', () => {
    expect(carryPhotoIds(assets, { photo_asset_id: 'gone', photo_asset_ids: ['a2', 'gone'] })).toEqual(['a2'])
  })

  it('사진이 하나도 안 남았으면 빈 목록', () => {
    expect(carryPhotoIds([], { photo_asset_id: 'a1', photo_asset_ids: ['a2'] })).toEqual([])
  })

  it('사진이 없던 아이는 그대로 없다', () => {
    expect(carryPhotoIds(assets, { photo_asset_id: null, photo_asset_ids: null })).toEqual([])
  })
})
