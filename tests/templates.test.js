import { describe, it, expect } from 'vitest'
import { renderTemplate, missingVars, unknownVars, DEFAULT_TEMPLATES } from '../src/core/templates.js'

describe('알림 문구 템플릿', () => {
  it('변수를 치환한다', () => {
    const out = renderTemplate('{학원명} {원생명}({반}) {금액}', {
      '{학원명}': '아라 잉글리시', '{원생명}': '김서준', '{반}': 'Basic A', '{금액}': '180,000원'
    })
    expect(out).toBe('아라 잉글리시 김서준(Basic A) 180,000원')
  })

  it('값이 없는 변수는 그대로 남겨 눈에 띄게 한다', () => {
    const out = renderTemplate('{원생명} {금액}', { '{원생명}': '김서준' })
    expect(out).toBe('김서준 {금액}')
    expect(missingVars(out)).toEqual(['{금액}'])
  })

  it('중괄호 없는 키로도 값을 넘길 수 있다', () => {
    expect(renderTemplate('{원생명}', { 원생명: '이하은' })).toBe('이하은')
  })

  it('정의되지 않은 변수를 찾아낸다', () => {
    expect(unknownVars('{원생명} {알수없음}')).toEqual(['{알수없음}'])
  })

  it('기본 템플릿은 모두 정의된 변수만 쓴다', () => {
    for (const t of DEFAULT_TEMPLATES) expect(unknownVars(t.body)).toEqual([])
  })
})
