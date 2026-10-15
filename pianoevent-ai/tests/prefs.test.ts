import { describe, expect, it } from 'vitest'
import { DESIGN_THEMES } from '@/lib/design/themes'
import {
  hasPrefs,
  prefBool,
  prefNumber,
  prefString,
  sanitizePref,
  sanitizePrefs,
  STAGE_PREF_SPEC,
  VIDEO_PREF_SPEC,
} from '@/lib/prefs'
import { STAGE_BACKDROPS } from '@/lib/stage/backdrops'
import { PHOTO_SHAPES, STAGE_LAYOUTS } from '@/lib/stage/layouts'
import { VIDEO_TEMPLATES } from '@/lib/video/templates'

describe('설정 저장 — 받아도 되는 값만 받는다', () => {
  it('무대 화면 설정의 목록이 실제 화면과 같다', () => {
    // 화면에는 있는데 저장은 안 되는 값이 생기면 원장님은 저장이 안 된 줄도 모른다
    expect(STAGE_PREF_SPEC.layout).toEqual({ type: 'enum', values: STAGE_LAYOUTS.map((l) => l.id) })
    expect(STAGE_PREF_SPEC.shape).toEqual({ type: 'enum', values: PHOTO_SHAPES.map((s) => s.id) })
    expect(STAGE_PREF_SPEC.backdrop).toEqual({ type: 'enum', values: STAGE_BACKDROPS.map((b) => b.id) })
    expect(VIDEO_PREF_SPEC.template).toEqual({ type: 'enum', values: VIDEO_TEMPLATES.map((t) => t.id) })
  })

  it('테마 108종이 모두 저장된다', () => {
    for (const theme of DESIGN_THEMES) {
      expect(sanitizePrefs(STAGE_PREF_SPEC, { theme: theme.id })).toEqual({ theme: theme.id })
    }
  })

  it('모르는 키는 조용히 버린다', () => {
    const out = sanitizePrefs(STAGE_PREF_SPEC, { theme: 'classic-navy', 몰라: 1, __proto__: 'x' })
    expect(out).toEqual({ theme: 'classic-navy' })
  })

  it('없는 값을 보내면 그 항목만 빠진다 — 저장 전체가 실패하지 않는다', () => {
    const out = sanitizePrefs(STAGE_PREF_SPEC, { theme: 'classic-navy', layout: '없는배치', dark: true })
    expect(out).toEqual({ theme: 'classic-navy', dark: true })
  })

  it('숫자는 범위 끝에 붙인다 — 슬라이더를 끝까지 민 것과 같다', () => {
    expect(sanitizePrefs(VIDEO_PREF_SPEC, { student_seconds: 999 })).toEqual({ student_seconds: 12 })
    expect(sanitizePrefs(VIDEO_PREF_SPEC, { student_seconds: 0 })).toEqual({ student_seconds: 1.5 })
    expect(sanitizePrefs(VIDEO_PREF_SPEC, { student_seconds: 3.44 })).toEqual({ student_seconds: 3.4 })
  })

  it('숫자 칸에 글자가 오면 버린다', () => {
    expect(sanitizePrefs(VIDEO_PREF_SPEC, { student_seconds: '삼초' })).toEqual({})
  })

  it('참·거짓 칸은 참·거짓만 받는다', () => {
    expect(sanitizePrefs(STAGE_PREF_SPEC, { dark: 'true' })).toEqual({})
    expect(sanitizePrefs(STAGE_PREF_SPEC, { dark: false })).toEqual({ dark: false })
  })

  it('마무리 문구는 길이를 자른다', () => {
    const long = '감'.repeat(400)
    const out = sanitizePrefs(VIDEO_PREF_SPEC, { closing: long })
    expect(String(out.closing)).toHaveLength(120)
  })

  it('빈 문구는 저장하지 않는다 — 기본 문구가 그대로 쓰이도록', () => {
    expect(sanitizePrefs(VIDEO_PREF_SPEC, { closing: '   ' })).toEqual({})
  })

  it('설정이 아닌 것을 보내도 무너지지 않는다', () => {
    expect(sanitizePrefs(STAGE_PREF_SPEC, null)).toEqual({})
    expect(sanitizePrefs(STAGE_PREF_SPEC, [1, 2])).toEqual({})
    expect(sanitizePrefs(STAGE_PREF_SPEC, '테마')).toEqual({})
  })

  it('값 하나짜리 검사도 규칙을 그대로 따른다', () => {
    expect(sanitizePref({ type: 'enum', values: ['a'] }, 'b')).toBeNull()
    expect(sanitizePref({ type: 'num', min: 1, max: 3 }, 2)).toBe(2)
    expect(sanitizePref({ type: 'text', max: 3 }, ' 가나다라 ')).toBe('가나다')
  })

  it('읽을 때는 없거나 이상하면 기본값', () => {
    expect(prefString({ theme: 'x' }, 'theme', 'y')).toBe('x')
    expect(prefString({}, 'theme', 'y')).toBe('y')
    expect(prefString(null, 'theme', 'y')).toBe('y')
    expect(prefBool({ dark: false }, 'dark', true)).toBe(false)
    expect(prefBool({}, 'dark', true)).toBe(true)
    expect(prefNumber({ a: 3 }, 'a', 1)).toBe(3)
    expect(prefNumber({ a: 'x' as unknown as number }, 'a', 1)).toBe(1)
  })

  it('빈 설정은 "저장해 둔 것 없음" 으로 본다', () => {
    expect(hasPrefs(null)).toBe(false)
    expect(hasPrefs({})).toBe(false)
    expect(hasPrefs({ theme: 'classic-navy' })).toBe(true)
  })
})
