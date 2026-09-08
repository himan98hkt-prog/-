import { describe, expect, it } from 'vitest'
import { baseName, findStudent, matchPhotoFiles, trailingNumber } from '@/lib/ops/photo-match'
import { student } from './helpers'

const roster = [
  student('김서연', 'beginner', 100, { id: 'a' }),
  student('박지호', 'beginner', 100, { id: 'b' }),
  student('김서', 'beginner', 100, { id: 'c' }),
  student('김서연', 'ensemble', 140, { id: 'a2' }),
]

describe('파일 이름으로 사진 짝짓기', () => {
  it('확장자를 뗀다', () => {
    expect(baseName('김서연-1.JPG')).toBe('김서연-1')
    expect(baseName('점.있는.이름.png')).toBe('점.있는.이름')
  })

  it('이름 뒤 번호를 읽는다', () => {
    expect(trailingNumber('김서연-2')).toBe(2)
    expect(trailingNumber('김서연 3')).toBe(3)
    expect(trailingNumber('김서연(4)')).toBe(4)
    expect(trailingNumber('김서연_5')).toBe(5)
    expect(trailingNumber('김서연')).toBeNull()
    // 이름 안의 숫자를 차례로 오해하지 않는다
    expect(trailingNumber('2026김서연')).toBeNull()
  })

  it('긴 이름부터 맞춘다 — 김서와 김서연이 함께 있을 때', () => {
    expect(findStudent('김서연 연습', roster)?.id).toBe('a')
    expect(findStudent('김서 연습', roster)?.id).toBe('c')
  })

  it('띄어 쓴 이름도 찾는다', () => {
    expect(findStudent('2026 김 서 연 무대', roster)?.id).toBe('a')
  })

  it('한 아이에 여러 장이면 번호대로 넣는다', () => {
    const { matched } = matchPhotoFiles(['김서연-3.jpg', '김서연-1.jpg', '김서연-2.jpg'], roster)
    expect(matched).toHaveLength(1)
    expect(matched[0].files).toEqual(['김서연-1.jpg', '김서연-2.jpg', '김서연-3.jpg'])
  })

  it('번호가 없으면 고른 차례를 그대로 쓴다', () => {
    const { matched } = matchPhotoFiles(['김서연 웃는.jpg', '김서연 연습.jpg'], roster)
    expect(matched[0].files).toEqual(['김서연 웃는.jpg', '김서연 연습.jpg'])
  })

  it('번호가 있는 파일이 없는 파일보다 앞선다', () => {
    const { matched } = matchPhotoFiles(['김서연 무대.jpg', '김서연-1.jpg'], roster)
    expect(matched[0].files).toEqual(['김서연-1.jpg', '김서연 무대.jpg'])
  })

  it('같은 아이가 명단에 두 줄이면 첫 줄에 붙인다 — 사진은 사람의 것이다', () => {
    const { matched } = matchPhotoFiles(['김서연.jpg'], roster)
    expect(matched[0].student.id).toBe('a')
  })

  it('아이를 찾지 못한 파일은 건너뛰고 알려 준다', () => {
    const { matched, skipped } = matchPhotoFiles(['단체사진.jpg', '박지호.jpg'], roster)
    expect(matched).toHaveLength(1)
    expect(skipped).toEqual(['단체사진.jpg'])
  })

  it('한 아이당 정해진 장수를 넘으면 넘친 것을 알려 준다 — 조용히 사라지지 않게', () => {
    const files = Array.from({ length: 5 }, (_, i) => `김서연-${i + 1}.jpg`)
    const { matched, skipped } = matchPhotoFiles(files, roster, 3)
    expect(matched[0].files).toHaveLength(3)
    expect(skipped).toEqual(['김서연-4.jpg', '김서연-5.jpg'])
  })

  it('아이가 여럿이면 각자 자기 것만 가져간다', () => {
    const { matched } = matchPhotoFiles(['김서연-1.jpg', '박지호.jpg', '김서연-2.jpg'], roster)
    const byId = Object.fromEntries(matched.map((row) => [row.student.id, row.files]))
    expect(byId.a).toEqual(['김서연-1.jpg', '김서연-2.jpg'])
    expect(byId.b).toEqual(['박지호.jpg'])
  })

  it('빈 목록이면 아무 일도 없다', () => {
    expect(matchPhotoFiles([], roster)).toEqual({ matched: [], skipped: [] })
  })
})
