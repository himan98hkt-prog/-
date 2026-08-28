import { describe, expect, it } from 'vitest'
import { summarizeRsvps } from '@/lib/store/types'
import type { Rsvp } from '@/lib/types'

function rsvp(partial: Partial<Rsvp>): Rsvp {
  return {
    id: 'r1',
    event_id: 'e1',
    parent_name: '김보호',
    student_name: '김학생',
    headcount: 2,
    message: null,
    attending: true,
    created_at: '2026-01-01T00:00:00.000Z',
    ...partial,
  }
}

describe('summarizeRsvps', () => {
  it('참석·불참·인원을 집계한다', () => {
    const summary = summarizeRsvps([
      rsvp({ id: 'a', headcount: 3 }),
      rsvp({ id: 'b', headcount: 2 }),
      rsvp({ id: 'c', attending: false, headcount: 0 }),
    ])
    expect(summary).toMatchObject({ responses: 3, attending: 2, declined: 1, headcount: 5 })
  })

  it('불참 가정의 인원은 총원에 넣지 않는다', () => {
    const summary = summarizeRsvps([rsvp({ id: 'a', attending: false, headcount: 4 })])
    expect(summary.headcount).toBe(0)
  })

  it('빈 메시지는 모으지 않는다', () => {
    const summary = summarizeRsvps([
      rsvp({ id: 'a', message: '  ' }),
      rsvp({ id: 'b', message: '잘하고 와!', parent_name: '이보호' }),
    ])
    expect(summary.messages).toEqual([
      { name: '이보호', student: '김학생', message: '잘하고 와!', created_at: '2026-01-01T00:00:00.000Z' },
    ])
  })

  it('누구 아이 것인지 함께 담는다 — 감동영상에서 그 아이 얼굴을 찾는다', () => {
    const summary = summarizeRsvps([rsvp({ message: '고맙습니다', student_name: '윤채원' })])
    expect(summary.messages[0].student).toBe('윤채원')
  })

  it('회신이 없으면 0 으로 채운다', () => {
    expect(summarizeRsvps([])).toMatchObject({ responses: 0, attending: 0, headcount: 0 })
  })
})
