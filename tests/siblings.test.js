import { describe, it, expect } from 'vitest'
import { normalizePhone, groupSiblings, assignSiblingGroups } from '../src/core/siblings.js'

describe('전화번호 정규화', () => {
  it('표기가 달라도 같은 번호로 본다', () => {
    const forms = ['010-1234-5678', '01012345678', '010 1234 5678', '+82 10-1234-5678', '(010)1234-5678']
    const normalized = new Set(forms.map(normalizePhone))
    expect(normalized.size).toBe(1)
    expect([...normalized][0]).toBe('01012345678')
  })

  it('빈 값은 매칭 대상이 아니다', () => {
    expect(normalizePhone('')).toBe('')
    expect(normalizePhone(null)).toBe('')
    expect(normalizePhone('전화없음')).toBe('')
  })
})

describe('형제 자동 묶기', () => {
  const students = [
    { id: '1', name: '김서준', parent_phone: '010-1111-2222' },
    { id: '2', name: '김서연', parent_phone: '01011112222' },
    { id: '3', name: '이하은', parent_phone: '+82 10 3333 4444' },
    { id: '4', name: '박도윤', parent_phone: '' },
    { id: '5', name: '박지우', parent_phone: null, phone: '010-3333-4444' }
  ]

  it('학부모 번호가 같으면 한 그룹', () => {
    const groups = groupSiblings(students)
    expect(groups.get('01011112222').map((s) => s.name)).toEqual(['김서연', '김서준'])
  })

  it('학부모 번호가 없으면 본인 번호로 보조 매칭한다', () => {
    const groups = groupSiblings(students)
    expect(groups.get('01033334444').map((s) => s.id).sort()).toEqual(['3', '5'])
  })

  it('번호가 아예 없는 원생은 어느 그룹에도 들어가지 않는다', () => {
    const groups = groupSiblings(students)
    const all = [...groups.values()].flat().map((s) => s.id)
    expect(all).not.toContain('4')
  })

  it('그룹이 바뀐 원생만 변경분으로 돌려준다', () => {
    const changed = assignSiblingGroups(students)
    expect(changed.map((s) => s.id).sort()).toEqual(['1', '2', '3', '5'])
    expect(changed.every((s) => s.siblings_group)).toBe(true)
  })

  it('형제가 아니게 되면 기존 그룹을 해제한다', () => {
    const changed = assignSiblingGroups([
      { id: '9', name: '외동', parent_phone: '010-9999-8888', siblings_group: '01099998888' }
    ])
    expect(changed).toEqual([expect.objectContaining({ id: '9', siblings_group: null })])
  })
})
