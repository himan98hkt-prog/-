import { describe, expect, it } from 'vitest'
import { canJoin, joinBlocker, joinedName, joinLabel, movePart, partsSeconds, type VideoPart } from '@/lib/video/join'

const part = (id: string, seconds: number, label = id): VideoPart => ({
  id,
  label,
  url: `blob:${id}`,
  seconds,
  made: true,
})

describe('토막을 한 편으로 잇기', () => {
  it('전체 길이를 더한다 — 잇는 데 그만큼 걸린다', () => {
    expect(partsSeconds([part('a', 120), part('b', 200)])).toBe(320)
  })

  it('두 토막부터 이을 수 있다', () => {
    expect(canJoin([])).toBe(false)
    expect(canJoin([part('a', 120)])).toBe(false)
    expect(canJoin([part('a', 120), part('b', 200)])).toBe(true)
  })

  it('길이를 못 읽은 토막이 있으면 아직 못 잇는다', () => {
    expect(canJoin([part('a', 120), part('b', 0)])).toBe(false)
  })

  it('왜 못 잇는지 한 줄로 말해 준다', () => {
    expect(joinBlocker([])).toContain('토막이 없습니다')
    expect(joinBlocker([part('a', 120)])).toContain('하나뿐')
    expect(joinBlocker([part('a', 120), part('b', 0)])).toContain('길이를 읽지 못한')
    expect(joinBlocker([part('a', 120), part('b', 200)])).toBeNull()
  })

  it('토막 수와 전체 길이를 함께 적어 준다', () => {
    expect(joinLabel([part('a', 120), part('b', 200)])).toBe('2토막 · 5분 20초')
  })

  it('토막 차례를 옮긴다', () => {
    const parts = [part('a', 1), part('b', 1), part('c', 1)]
    expect(movePart(parts, 2, -1).map((row) => row.id)).toEqual(['a', 'c', 'b'])
    expect(movePart(parts, 0, 1).map((row) => row.id)).toEqual(['b', 'a', 'c'])
  })

  it('끝에서 더 옮기라고 해도 그대로 둔다', () => {
    const parts = [part('a', 1), part('b', 1)]
    expect(movePart(parts, 0, -1)).toBe(parts)
    expect(movePart(parts, 1, 1)).toBe(parts)
    expect(movePart(parts, 9, 1)).toBe(parts)
  })

  it('이어 붙인 파일 이름은 행사 이름으로 되돌린다', () => {
    expect(joinedName('제12회 정기 연주회', 'mp4')).toBe('제12회 정기 연주회 감동영상 (한 편).mp4')
  })

  it('파일 이름에 쓸 수 없는 글자를 지운다', () => {
    expect(joinedName('제12회 <정기> 연주회 / 봄', 'webm')).toBe('제12회  정기  연주회   봄 감동영상 (한 편).webm')
  })

  it('행사 이름이 비어 있어도 이름이 나온다', () => {
    expect(joinedName('   ', 'mp4')).toBe('연주회 감동영상 (한 편).mp4')
  })
})
