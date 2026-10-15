import { describe, expect, it } from 'vitest'
import { buildProgram } from '@/lib/program/order'
import { buildMcScript, buildStudentScript, pieceCommentary } from '@/lib/program/script'
import { student } from './helpers'

describe('pieceCommentary', () => {
  it('곡명을 알면 곡 해설을 쓴다', () => {
    expect(pieceCommentary(student('서연', 'intermediate', 200, { piece_title: '엘리제를 위하여' }))).toContain('첫 소절')
  })

  it('곡을 모르면 작곡가 지식으로 해설한다', () => {
    const text = pieceCommentary(student('민준', 'intermediate', 200, { piece_title: '무명 소품', composer: '드뷔시' }))
    expect(text).toContain('근대')
  })

  it('둘 다 모르면 난이도 기준 일반 해설로 떨어진다', () => {
    const text = pieceCommentary(student('가온', 'beginner', 90, { piece_title: '???', composer: '' }))
    expect(text.length).toBeGreaterThan(10)
  })
})

describe('buildStudentScript', () => {
  const plan = buildProgram([
    student('가온', 'beginner', 90),
    student('나윤', 'intermediate', 180),
    student('다현', 'advanced', 300),
  ])

  it('오프닝 곡에는 여는 문장이 붙는다', () => {
    expect(buildStudentScript(plan.items[0], 0, 3)).toContain('첫 무대')
  })

  it('피날레 곡에는 마지막 무대임을 알린다', () => {
    expect(buildStudentScript(plan.items[2], 2, 3)).toContain('마지막 무대')
  })

  it('학생 이름과 곡명이 반드시 들어간다', () => {
    const text = buildStudentScript(plan.items[1], 1, 3)
    expect(text).toContain(plan.items[1].student.student_name)
    expect(text).toContain(plan.items[1].student.piece_title)
  })

  it('특징 메모가 있으면 멘트에 녹인다', () => {
    const withNote = buildProgram([
      student('서연', 'beginner', 90, { note: '올해 처음 무대에 섭니다' }),
      student('민준', 'beginner', 90),
    ])
    const index = withNote.items.findIndex((i) => i.student.student_name === '서연')
    expect(buildStudentScript(withNote.items[index], index, 2)).toContain('올해 처음 무대에 섭니다')
  })
})

describe('buildMcScript', () => {
  const plan = buildProgram([
    student('가온', 'beginner', 90),
    student('나윤', 'intermediate', 180),
    student('다현', 'advanced', 300),
  ])
  const script = buildMcScript(plan, { eventTitle: '제12회 정기 연주회', academyName: '하모니 피아노학원' })

  it('오프닝·클로징에 학원명과 행사명이 들어간다', () => {
    expect(script.opening).toContain('하모니 피아노학원')
    expect(script.opening).toContain('제12회 정기 연주회')
    expect(script.closing).toContain('제12회 정기 연주회')
  })

  it('모든 학생에게 멘트가 하나씩 생긴다', () => {
    expect(Object.keys(script.byStudentId)).toHaveLength(plan.items.length)
    for (const item of plan.items) {
      expect(script.byStudentId[item.student.id]).toBeTruthy()
    }
  })
})
