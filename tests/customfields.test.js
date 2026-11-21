import { describe, it, expect } from 'vitest'
import { validateField, normalizeValues, displayPairs, PRESETS } from '../src/core/customfields.js'

describe('custom 필드 정의', () => {
  it('키 규칙을 검사한다', () => {
    expect(validateField({ key: 'belt', label: '띠 급수', type: 'text' })).toEqual([])
    expect(validateField({ key: '1belt', label: '띠', type: 'text' })[0]).toContain('저장 키')
    expect(validateField({ key: 'belt', label: '', type: 'text' })[0]).toContain('항목 이름')
  })

  it('중복 키를 막는다', () => {
    const errs = validateField({ key: 'belt', label: '띠', type: 'text' }, [{ key: 'belt' }])
    expect(errs.join()).toContain('이미 같은 저장 키')
  })

  it('선택 목록은 선택지가 필요하다', () => {
    expect(validateField({ key: 'lv', label: '레벨', type: 'select', options: [] }).join()).toContain('선택 목록')
  })
})

describe('custom 값 정규화', () => {
  const fields = [
    { key: 'belt', label: '띠 급수', type: 'select', options: ['흰띠', '검은띠'], onCard: true, onReport: true },
    { key: 'score', label: '점수', type: 'number', onCard: false, onReport: true },
    { key: 'memo', label: '메모', type: 'text', onCard: true }
  ]

  it('정의되지 않은 키는 버린다', () => {
    const v = normalizeValues(fields, { belt: '흰띠', hacker: 'drop me' })
    expect(v).toEqual({ belt: '흰띠' })
  })

  it('숫자는 숫자로, 잘못된 숫자는 버린다', () => {
    expect(normalizeValues(fields, { score: '88' })).toEqual({ score: 88 })
    expect(normalizeValues(fields, { score: '팔십팔' })).toEqual({})
  })

  it('선택 목록에 없는 값은 버린다', () => {
    expect(normalizeValues(fields, { belt: '무지개띠' })).toEqual({})
  })

  it('빈 값은 저장하지 않는다', () => {
    expect(normalizeValues(fields, { belt: '', memo: null })).toEqual({})
  })

  it('카드/리포트 노출 대상만 골라낸다', () => {
    const values = { belt: '검은띠', score: 90, memo: '성실' }
    expect(displayPairs(fields, values, 'card').map((p) => p.key)).toEqual(['belt', 'memo'])
    expect(displayPairs(fields, values, 'report').map((p) => p.key)).toEqual(['belt', 'score'])
  })
})

describe('계열 프리셋', () => {
  it('모든 프리셋이 유효한 필드 정의다', () => {
    for (const [name, fields] of Object.entries(PRESETS)) {
      const seen = []
      for (const f of fields) {
        expect(validateField(f, seen), `${name}.${f.key}`).toEqual([])
        seen.push(f)
      }
    }
  })
})
