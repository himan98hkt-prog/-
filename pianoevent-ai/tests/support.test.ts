import { describe, expect, it } from 'vitest'
import { browserName, buildReport, containsAny, osName, scrubError, scrubPath } from '@/lib/support/report'

const base = {
  path: '/events/8f3c1d2e-4a5b-6c7d-8e9f-0a1b2c3d4e5f/video',
  version: '0.1.0',
  driver: 'demo' as const,
  userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36',
  screen: '1920×1080',
  online: true,
  note: '영상 만들기를 눌렀는데 아무 일도 안 일어납니다',
  errors: [],
  now: '2026-08-28T09:30:00.000Z',
}

describe('주소에서 사람 지우기', () => {
  it('행사 번호를 지운다', () => {
    expect(scrubPath('/events/8f3c1d2e-4a5b-6c7d-8e9f-0a1b2c3d4e5f/video')).toBe('/events/[행사]/video')
  })

  it('물음표 뒤는 버린다', () => {
    expect(scrubPath('/events/demo-event-1?tab=roster')).toBe('/events/[행사]')
  })

  it('짧고 뜻이 있는 토막은 남긴다 — 어느 화면인지 알아야 한다', () => {
    expect(scrubPath('/help')).toBe('/help')
    expect(scrubPath('/settings')).toBe('/settings')
  })
})

describe('브라우저 알아보기', () => {
  it('Edge 를 Chrome 으로 잘못 읽지 않는다 — 둘 다 Chrome 이라 적혀 있다', () => {
    expect(browserName('... Chrome/131.0 ... Edg/131.0')).toBe('Edge')
  })

  it('네이버 웨일도 알아본다 — 원장님들이 많이 쓰신다', () => {
    expect(browserName('... Whale/3.0 Chrome/... Safari/537')).toBe('Whale')
  })

  it('윈도우를 알아본다', () => {
    expect(osName('Mozilla/5.0 (Windows NT 10.0; Win64)')).toBe('Windows 10/11')
  })
})

describe('오류 글에서 지워야 할 것', () => {
  it('윈도우 사용자 이름을 지운다 — 원장님 성함이 들어 있다', () => {
    expect(scrubError('at C:\\Users\\김원장\\Desktop\\program.js:12')).toContain('C:\\Users\\[사용자]')
    expect(scrubError('at C:\\Users\\김원장\\Desktop\\program.js:12')).not.toContain('김원장')
  })

  it('사진은 통째로 지운다 — 아이 얼굴이다', () => {
    expect(scrubError('img failed: data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ')).toBe('img failed: [사진]')
  })

  it('주소에 섞인 행사 번호도 지운다', () => {
    expect(scrubError('GET http://localhost:3000/api/events/8f3c1d2e-4a5b-6c7d/students 500')).toContain(
      '/api/events/[행사]/students',
    )
  })

  it('너무 긴 글은 자른다', () => {
    expect(scrubError('가'.repeat(500)).length).toBeLessThanOrEqual(300)
  })
})

describe('보내실 쪽지', () => {
  it('막힌 화면·판·브라우저를 담는다', () => {
    const text = buildReport(base)
    expect(text).toContain('/events/[행사]/video')
    expect(text).toContain('0.1.0')
    expect(text).toContain('Chrome')
  })

  it('원장님이 적으신 설명을 담는다', () => {
    expect(buildReport(base)).toContain('영상 만들기를 눌렀는데')
  })

  it('안 적으셔도 쪽지는 만들어진다 — 빈 채로 막히시면 안 된다', () => {
    expect(buildReport({ ...base, note: '   ' })).toContain('(적지 않으심)')
  })

  it('규모는 숫자만 담는다', () => {
    expect(buildReport({ ...base, counts: { events: 3, students: 24, photos: 12 } })).toContain(
      '행사 3개 · 명단 24줄 · 사진 12장',
    )
  })

  it('아이 이름은 어디에도 들어가지 않는다', () => {
    const text = buildReport({
      ...base,
      counts: { students: 12 },
      errors: ['render failed for 김서연 photo data:image/png;base64,AAAA'],
    })
    // 오류 글에 섞여 온 사진은 지워진다. 이름은 저희가 담지 않는다 —
    // 원장님이 손으로 적으신 칸에만 들어갈 수 있고, 그건 원장님이 정하실 몫이다.
    expect(text).not.toContain('base64')
    expect(containsAny(text, ['data:image'])).toEqual([])
  })

  it('아이 이름·사진이 들어 있지 않다고 쪽지 끝에 적어 준다', () => {
    expect(buildReport(base)).toContain('아이 이름·사진·연락처가 들어 있지 않습니다')
  })

  it('오류가 없으면 없다고 적는다 — 빈칸은 원장님을 불안하게 한다', () => {
    expect(buildReport(base)).toContain('(없음)')
  })

  it('오류는 다섯 개까지만 담는다', () => {
    const text = buildReport({ ...base, errors: Array.from({ length: 20 }, (_, i) => `오류${i}`) })
    expect(text.split('· 오류').length - 1).toBe(5)
  })
})
