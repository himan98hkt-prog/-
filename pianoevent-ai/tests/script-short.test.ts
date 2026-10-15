import { describe, expect, it } from 'vitest'
import { buildProgram } from '@/lib/program/order'
import { buildMcScript, buildShortMcScript, shortStudentScript } from '@/lib/program/script'
import { student } from './helpers'

const plan = buildProgram([
  student('김서연', 'beginner', 100, { piece_title: '나비야' }),
  student('박지호', 'beginner', 110, { piece_title: '즐거운 나의 집', composer: '비숍' }),
  student('정예린', 'intermediate', 170, { piece_title: '아라베스크', composer: '부르크뮐러' }),
  student('윤채원', 'advanced', 260, { piece_title: '녹턴', composer: '쇼팽' }),
])
const meta = { eventTitle: '제12회 정기 연주회', academyName: '하모니 피아노학원' }

describe('밀렸을 때 읽는 짧은 판', () => {
  const short = buildShortMcScript(plan, meta)
  const full = buildMcScript(plan, meta)

  it('순서마다 한 줄이 있다', () => {
    for (const item of plan.items) {
      expect(short.byStudentId[item.student.id], item.student.student_name).toBeTruthy()
    }
  })

  it('한 줄이다 — 줄바꿈이 없어야 무대 옆에서 읽힌다', () => {
    for (const line of Object.values(short.byStudentId)) {
      expect(line).not.toContain('\n')
    }
  })

  it('긴 판보다 확실히 짧다 — 그게 전부인 기능이다', () => {
    for (const item of plan.items) {
      const id = item.student.id
      expect(short.byStudentId[id].length, item.student.student_name).toBeLessThan(
        full.byStudentId[id].length,
      )
    }
  })

  it('빼면 안 되는 것은 남긴다 — 순번 · 이름 · 곡', () => {
    for (const item of plan.items) {
      const line = short.byStudentId[item.student.id]
      expect(line, item.student.student_name).toContain(String(item.order_no))
      expect(line).toContain(item.student.student_name)
      expect(line).toContain(item.student.piece_title)
    }
  })

  it('작곡가가 있으면 넣고, 없으면 곡만', () => {
    const withComposer = plan.items.find((i) => i.student.composer)!
    expect(short.byStudentId[withComposer.student.id]).toContain(withComposer.student.composer)
    const without = plan.items.find((i) => !i.student.composer)
    if (without) expect(short.byStudentId[without.student.id]).toContain('「')
  })

  it('첫 무대와 마지막 무대는 그렇다고 한마디만 붙인다', () => {
    const first = plan.items[0]
    const last = plan.items[plan.items.length - 1]
    expect(shortStudentScript(first) + shortStudentScript(last)).toMatch(/첫 무대|마지막 무대/)
  })

  it('여는 말은 빼면 안 되는 것만 남긴다 — 인사 · 무음 · 박수', () => {
    expect(short.opening).toContain('환영')
    expect(short.opening).toContain('무음')
    expect(short.opening).toContain('박수')
    expect(short.opening.length).toBeLessThan(full.opening.length)
  })

  it('밀린 상태에서 예정 시간을 말하지 않는다 — 더 이상해진다', () => {
    expect(short.opening).not.toMatch(/\d+분/)
  })

  it('닫는 말도 짧다', () => {
    expect(short.closing).toContain('박수')
    expect(short.closing.length).toBeLessThan(full.closing.length)
  })

  it('명단이 비어도 멈추지 않는다', () => {
    expect(() => buildShortMcScript(buildProgram([]), meta)).not.toThrow()
  })
})
