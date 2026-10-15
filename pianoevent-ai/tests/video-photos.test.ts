import { describe, expect, it } from 'vitest'
import { missingPhotos } from '@/lib/video/storyboard'

/**
 * 사진을 안 넣은 아이 세기.
 *
 * 「사진이 없는 N명」이라고만 적어 두면 원장님은 그 N명이 누구인지 명단을 뒤져 찾으셔야 한다.
 * 게다가 **곡 수로 세고 있었다** — 한 아이가 두 곡을 치면 사람은 하나인데 둘로 세어,
 * 사진을 다 넣으셨는데도 「없는 사람이 있다」고 나왔다.
 */
const kid = (id: string, name: string) => ({ student: { id, student_name: name } })

describe('사진 없는 아이', () => {
  it('사진이 없는 아이를 이름으로 알려 준다', () => {
    expect(missingPhotos([kid('a', '김서연'), kid('b', '박지호')], { a: 'photo-a' })).toEqual(['박지호'])
  })

  it('다 넣으셨으면 비어 있다', () => {
    expect(missingPhotos([kid('a', '김서연')], { a: 'photo-a' })).toEqual([])
  })

  it('한 아이가 두 곡을 쳐도 **한 사람**으로 센다', () => {
    // 독주 + 듀엣이면 순서표에는 두 줄이다. 사람은 하나다.
    const items = [kid('a', '임가온'), kid('a', '임가온'), kid('b', '임하람')]
    expect(missingPhotos(items, { a: 'photo-a' })).toEqual(['임하람'])
    expect(missingPhotos(items, {})).toEqual(['임가온', '임하람'])
  })

  it('이름 앞뒤 빈칸은 털어 낸다', () => {
    expect(missingPhotos([kid('a', ' 최은우 ')], {})).toEqual(['최은우'])
  })

  it('순서표에 나온 차례를 지킨다 — 명단에서 찾기 쉽게', () => {
    const items = [kid('a', '오수아'), kid('b', '박지호'), kid('c', '정예린')]
    expect(missingPhotos(items, { b: 'photo-b' })).toEqual(['오수아', '정예린'])
  })
})
