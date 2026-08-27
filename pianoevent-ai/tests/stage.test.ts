import { describe, expect, it } from 'vitest'
import { buildProgram } from '@/lib/program/order'
import { buildStageDeck, DEFAULT_STAGE_OPTIONS } from '@/lib/stage/deck'
import type { EventRecord } from '@/lib/types'
import { student } from './helpers'

const EVENT_AT = '2026-09-16T06:00:00.000Z' // 2026-09-16 15:00 KST

const event = {
  id: 'e1',
  academy_id: 'a1',
  title: '제12회 정기 연주회',
  type: 'recital',
  event_at: EVENT_AT,
  venue: '구민회관 소공연장',
  status: 'ready',
  theme: null,
  greeting: null,
  mc_opening: null,
  mc_closing: null,
  program_source: 'rule',
  program_generated_at: null,
  design_theme: null,
  design_template: null,
  design_copy: null,
  photo_url: null,
  created_at: EVENT_AT,
} as EventRecord

const roster = [
  student('김서연', 'beginner', 100, { piece_title: '나비야', composer: '전래' }),
  student('박지호', 'beginner', 110, { piece_title: '즐거운 나의 집', composer: '비숍' }),
  student('정예린', 'intermediate', 170, { piece_title: '아라베스크', composer: '부르크뮐러' }),
  student('한도윤', 'intermediate', 190, { piece_title: '미뉴에트 G장조', composer: '바흐' }),
  student('윤채원', 'advanced', 260, { piece_title: '녹턴 op.9 no.2', composer: '쇼팽' }),
  student('임가온', 'ensemble', 120, { piece_title: '젓가락 행진곡', composer: '전래' }),
]

function deck(options = DEFAULT_STAGE_OPTIONS) {
  const plan = buildProgram(roster)
  return buildStageDeck(event, plan, '하모니 피아노학원', options)
}

describe('무대 화면 슬라이드', () => {
  it('대기 화면으로 시작해 인사 화면으로 끝난다', () => {
    const slides = deck()
    expect(slides[0].kind).toBe('standby')
    expect(slides[0].title).toBe('제12회 정기 연주회')
    expect(slides[slides.length - 1].kind).toBe('closing')
  })

  it('연주자 한 명당 한 장을 만든다 — 아무도 빠지지 않는다', () => {
    const slides = deck()
    const performances = slides.filter((slide) => slide.kind === 'performance')
    expect(performances).toHaveLength(roster.length)
    for (const name of roster.map((row) => row.student_name)) {
      expect(performances.some((slide) => slide.title === name)).toBe(true)
    }
  })

  it('연주 화면은 곡과 작곡가, 순서 번호를 함께 띄운다', () => {
    const slides = deck()
    const chopin = slides.find((slide) => slide.title === '윤채원')
    expect(chopin?.subtitle).toContain('녹턴 op.9 no.2')
    expect(chopin?.subtitle).toContain('쇼팽')
    expect(chopin?.counter).toMatch(/^\d+ \/ 6$/)
    expect(chopin?.at).toBeTruthy()
  })

  it('연주 순서가 순서표와 같다', () => {
    const plan = buildProgram(roster)
    const slides = buildStageDeck(event, plan, '하모니 피아노학원')
    const shown = slides.filter((slide) => slide.kind === 'performance').map((slide) => slide.title)
    expect(shown).toEqual(plan.items.map((item) => item.student.student_name))
  })

  it('오늘의 순서 화면이 모든 연주자를 담는다', () => {
    const slides = deck()
    const rows = slides.filter((slide) => slide.kind === 'agenda').flatMap((slide) => slide.lines ?? [])
    expect(rows).toHaveLength(roster.length)
  })

  it('연주자가 많으면 오늘의 순서를 여러 장으로 나눈다 — 화면 밖으로 넘치지 않게', () => {
    const many = Array.from({ length: 34 }, (_, i) => student(`학생${i + 1}`, 'intermediate', 150))
    const slides = buildStageDeck(event, buildProgram(many), '하모니 피아노학원')
    const agenda = slides.filter((slide) => slide.kind === 'agenda')
    expect(agenda.length).toBeGreaterThan(1)
    for (const slide of agenda) expect((slide.lines ?? []).length).toBeLessThanOrEqual(12)
    expect(agenda.flatMap((slide) => slide.lines ?? [])).toHaveLength(34)
  })

  it('모든 화면이 다음 화면을 알려 준다 — 사회자가 미리 준비한다', () => {
    const slides = deck()
    for (let i = 0; i < slides.length - 1; i += 1) expect(slides[i].next).toBeTruthy()
    expect(slides[slides.length - 1].next).toBe('')
  })

  it('곡 해설을 끄면 이름과 곡만 남는다', () => {
    const plain = deck({ ...DEFAULT_STAGE_OPTIONS, show_commentary: false })
    expect(plain.filter((slide) => slide.kind === 'performance').every((slide) => !slide.body)).toBe(true)
  })

  it('부 전환·순서 화면을 끄면 그만큼만 줄어든다', () => {
    const full = deck()
    const bare = deck({ show_commentary: true, show_sections: false, show_agenda: false })
    expect(bare.filter((slide) => slide.kind === 'section')).toHaveLength(0)
    expect(bare.filter((slide) => slide.kind === 'agenda')).toHaveLength(0)
    expect(bare.length).toBeLessThan(full.length)
    expect(bare.filter((slide) => slide.kind === 'performance')).toHaveLength(roster.length)
  })

  it('명단이 비어도 만들어진다 — 대기 화면과 인사 화면', () => {
    const slides = buildStageDeck(event, buildProgram([]), '하모니 피아노학원')
    expect(slides).toHaveLength(2)
    expect(slides.map((slide) => slide.kind)).toEqual(['standby', 'closing'])
  })

  it('슬라이드 id 가 겹치지 않는다', () => {
    const slides = deck()
    expect(new Set(slides.map((slide) => slide.id)).size).toBe(slides.length)
  })
})
