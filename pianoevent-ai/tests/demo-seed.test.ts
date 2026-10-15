import { describe, expect, it } from 'vitest'
import { DEMO_ROSTER, DEMO_TITLE, demoEventAt, demoFace, isDemoEvent } from '@/lib/events/demo-seed'

describe('구경용 행사', () => {
  it('이름만 보고도 구경용인 줄 아신다 — 진짜 행사와 헷갈리면 안 된다', () => {
    expect(DEMO_TITLE).toContain('구경용')
    expect(DEMO_TITLE).toContain('지우셔도')
    expect(isDemoEvent(DEMO_TITLE)).toBe(true)
    expect(isDemoEvent('제12회 정기 연주회')).toBe(false)
  })

  it('난이도가 골고루 섞여 있다 — 순서 짜기가 실제처럼 보여야 한다', () => {
    const levels = new Set(DEMO_ROSTER.map((s) => s.level))
    expect(levels.has('beginner')).toBe(true)
    expect(levels.has('intermediate')).toBe(true)
    expect(levels.has('advanced')).toBe(true)
    expect(levels.has('ensemble')).toBe(true)
  })

  it('연탄곡은 두 사람이 같은 곡을 친다', () => {
    const ensemble = DEMO_ROSTER.filter((s) => s.level === 'ensemble')
    expect(ensemble).toHaveLength(2)
    expect(ensemble[0].piece_title).toBe(ensemble[1].piece_title)
  })

  it('모든 아이가 곡과 시간을 갖고 있다 — 구경용인데 비어 있으면 볼 것이 없다', () => {
    for (const row of DEMO_ROSTER) {
      expect(row.piece_title.length, row.student_name).toBeGreaterThan(1)
      expect(row.duration_sec ?? 0, row.student_name).toBeGreaterThan(30)
    }
  })

  it('한 줄 이야기가 몇 개 들어 있다 — 사회자 멘트가 담백해지지 않게', () => {
    expect(DEMO_ROSTER.filter((s) => s.note).length).toBeGreaterThanOrEqual(3)
  })

  it('사진은 아이마다 색이 다르다 — 무대 화면이 다 같아 보이면 안 된다', () => {
    const faces = DEMO_ROSTER.map((_, i) => demoFace(i, DEMO_ROSTER.length))
    expect(new Set(faces).size).toBe(faces.length)
    expect(faces[0].startsWith('data:image/svg+xml')).toBe(true)
  })

  it('행사 날짜는 앞으로다 — 지난 날짜면 이미 끝난 행사처럼 보인다', () => {
    const now = new Date('2026-08-28T00:00:00.000Z')
    expect(new Date(demoEventAt(now)).getTime()).toBeGreaterThan(now.getTime())
  })
})
