import { describe, expect, it } from 'vitest'
import { extractJson } from '@/lib/ai/gemini'
import { buildProgramContents, parseAiProgram } from '@/lib/program/ai'
import { parseSeasonPack } from '@/lib/season/ai'
import { student } from './helpers'

describe('extractJson', () => {
  it('순수 JSON 을 읽는다', () => {
    expect(extractJson('{"a":1}')).toEqual({ a: 1 })
  })

  it('```json 펜스를 벗겨 낸다', () => {
    expect(extractJson('```json\n{"a":1}\n```')).toEqual({ a: 1 })
  })

  it('앞뒤 설명 문장이 붙어도 JSON 만 뽑아낸다', () => {
    expect(extractJson('아래와 같습니다.\n{"a":[1,2]}\n감사합니다.')).toEqual({ a: [1, 2] })
  })

  it('JSON 이 전혀 없으면 예외를 던진다', () => {
    expect(() => extractJson('죄송합니다. 생성할 수 없습니다.')).toThrow()
  })
})

describe('parseAiProgram', () => {
  const roster = [student('가', 'beginner', 90, { id: 'a' }), student('나', 'intermediate', 180, { id: 'b' })]

  it('정상 응답에서 순서와 멘트를 뽑는다', () => {
    const parsed = parseAiProgram(
      {
        order: [
          { id: 'b', mc_script: '나 학생 멘트' },
          { id: 'a', mc_script: '가 학생 멘트' },
        ],
        opening_script: '오프닝',
        closing_script: '클로징',
      },
      roster,
    )
    expect(parsed.orderedIds).toEqual(['b', 'a'])
    expect(parsed.scripts.a).toBe('가 학생 멘트')
    expect(parsed.opening).toBe('오프닝')
  })

  it('모르는 id·중복 id·빈 멘트를 걸러 낸다', () => {
    const parsed = parseAiProgram(
      { order: [{ id: 'zzz', mc_script: 'x' }, { id: 'a', mc_script: '  ' }, { id: 'a', mc_script: '중복' }] },
      roster,
    )
    expect(parsed.orderedIds).toEqual(['a'])
    expect(parsed.scripts.a).toBeUndefined()
    expect(parsed.opening).toBeNull()
  })

  it('형태가 완전히 어긋나도 터지지 않는다', () => {
    expect(parseAiProgram(null, roster).orderedIds).toEqual([])
    expect(parseAiProgram({ order: '순서가 없습니다' }, roster).orderedIds).toEqual([])
  })
})

describe('buildProgramContents', () => {
  it('모델에 넘기는 입력에 필요한 필드만 담는다', () => {
    const payload = JSON.parse(
      buildProgramContents({
        eventTitle: '연주회',
        academyName: '학원',
        eventAt: '2026-03-14T06:00:00.000Z',
        venue: '소공연장',
        students: [student('서연', 'intermediate', 200, { id: 'x', composer: '베토벤' })],
      }),
    )
    expect(payload.students[0]).toMatchObject({ id: 'x', name: '서연', composer: '베토벤', level: '중급' })
    expect(payload.students[0].mc_script).toBeUndefined()
  })
})

describe('parseSeasonPack', () => {
  it('주차가 하나도 없으면 null 을 돌려 템플릿으로 떨어지게 한다', () => {
    expect(parseSeasonPack({ weeks: [] }, 'christmas')).toBeNull()
    expect(parseSeasonPack({}, 'christmas')).toBeNull()
  })

  it('주차 번호가 없으면 순서대로 채운다', () => {
    const pack = parseSeasonPack({ weeks: [{ title: '첫 주' }, { title: '둘째 주' }] }, 'halloween')
    expect(pack?.weeks.map((w) => w.week)).toEqual([1, 2])
    expect(pack?.source).toBe('ai')
  })

  it('활동지가 비면 템플릿 활동지로 메운다', () => {
    const pack = parseSeasonPack({ weeks: [{ title: '첫 주' }], worksheets: [] }, 'vacation')
    expect(pack?.worksheets.length).toBeGreaterThan(0)
  })

  it('문항이 없는 활동지는 버린다', () => {
    const pack = parseSeasonPack(
      { weeks: [{ title: '첫 주' }], worksheets: [{ title: '빈 활동지', questions: [] }] },
      'vacation',
    )
    expect(pack?.worksheets.every((w) => w.questions.length > 0)).toBe(true)
  })
})
