import { describe, expect, it } from 'vitest'
import { buildChecklist, checklistTaskCount, currentGroup } from '@/lib/ops/checklist'
import { buildCueSheet, cueSheetSpanMin, suggestedRehearsalMin } from '@/lib/ops/cuesheet'
import { buildMessages, messageBytes } from '@/lib/ops/messages'
import { buildProgram } from '@/lib/program/order'
import type { Academy, EventRecord } from '@/lib/types'
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

const academy = { id: 'a1', name: '하모니 피아노학원', director_name: '김보람' } as Academy

const plan = buildProgram([
  student('가온', 'beginner', 90),
  student('나윤', 'intermediate', 180),
  student('다현', 'advanced', 300),
])

describe('당일 진행표', () => {
  const items = buildCueSheet(event, plan)

  it('도착이 가장 이르고 정리가 가장 늦다', () => {
    expect(items[0].title).toContain('도착')
    expect(items[items.length - 1].title).toContain('정리')
  })

  it('시간 순으로 정렬된다', () => {
    for (let i = 1; i < items.length; i++) {
      expect(items[i].offset_min).toBeGreaterThanOrEqual(items[i - 1].offset_min)
    }
  })

  it('개회는 0분이고 준비 항목은 그보다 앞선다', () => {
    const open = items.find((i) => i.title.includes('개회'))
    expect(open?.offset_min).toBe(0)
    expect(items.filter((i) => i.kind === 'prep').every((i) => i.offset_min < 0)).toBe(true)
  })

  it('연주자 수만큼 무대 항목이 들어간다', () => {
    const performances = items.filter((i) => i.kind === 'stage' && /^\d+\./.test(i.title))
    expect(performances).toHaveLength(plan.items.length)
    // 순서는 배치 엔진이 정한다 — 오프닝으로 뽑힌 학생이 1번이 된다
    expect(performances[0].title).toContain(plan.items[0].student.student_name)
  })

  it('시상·단체사진·폐회가 연주 뒤에 온다', () => {
    const lastPerformance = Math.max(
      ...items.filter((i) => /^\d+\./.test(i.title)).map((i) => i.offset_min),
    )
    for (const title of ['시상', '단체 사진', '폐회']) {
      const item = items.find((i) => i.title.includes(title))
      expect(item, title).toBeTruthy()
      expect(item!.offset_min, title).toBeGreaterThan(lastPerformance)
    }
  })

  it('전체 소요 시간을 계산한다', () => {
    expect(cueSheetSpanMin(items)).toBeGreaterThan(120)
    expect(cueSheetSpanMin([])).toBe(0)
  })

  it('리허설 시간은 인원수에 따라 늘고 상한이 있다', () => {
    expect(suggestedRehearsalMin(0)).toBe(20)
    expect(suggestedRehearsalMin(10)).toBe(30)
    expect(suggestedRehearsalMin(200)).toBe(120)
  })
})

describe('준비 체크리스트', () => {
  const groups = buildChecklist(event)

  it('D-30 부터 종료 후까지 여섯 묶음이 나온다', () => {
    expect(groups.map((g) => g.id)).toEqual(['d30', 'd14', 'd7', 'd1', 'day', 'after'])
    expect(checklistTaskCount(groups)).toBeGreaterThanOrEqual(25)
  })

  it('행사 날짜 기준으로 각 묶음의 날짜를 계산한다', () => {
    expect(groups.find((g) => g.id === 'day')?.date).toBe('2026.09.16')
    expect(groups.find((g) => g.id === 'd30')?.date).toBe('2026.08.17')
    expect(groups.find((g) => g.id === 'd1')?.date).toBe('2026.09.15')
    expect(groups.find((g) => g.id === 'after')?.date).toBe('2026.09.18')
  })

  it('자주 빠뜨리는 항목이 표시돼 있다', () => {
    const critical = groups.flatMap((g) => g.tasks).filter((t) => t.critical)
    expect(critical.length).toBeGreaterThanOrEqual(8)
    expect(critical.some((t) => t.title.includes('조율'))).toBe(true)
  })

  it('오늘 기준으로 지금 손댈 묶음을 고른다', () => {
    const at = (iso: string) => currentGroup(groups, event, new Date(iso))?.id
    expect(at('2026-07-01T00:00:00Z')).toBe('d30')
    expect(at('2026-09-05T00:00:00Z')).toBe('d14')
    expect(at('2026-09-12T00:00:00Z')).toBe('d7')
    expect(at('2026-09-14T20:00:00Z')).toBe('d1')
    expect(at('2026-09-16T01:00:00Z')).toBe('day')
    expect(at('2026-09-18T00:00:00Z')).toBe('after')
  })
})

describe('학부모 안내 문구', () => {
  it('초대·사흘 전·당일·감사 네 통을 만든다', () => {
    const messages = buildMessages({ academy, event, plan })
    expect(messages.map((m) => m.kind)).toEqual(['invite', 'remind', 'today', 'thanks'])
    for (const message of messages) {
      expect(message.body).toContain('하모니 피아노학원')
      expect(message.body.length).toBeGreaterThan(60)
    }
  })

  it('초대장 링크를 주면 문구에 넣고, 없으면 뺀다', () => {
    const withLink = buildMessages({ academy, event, plan, inviteUrl: 'https://x.test/e/e1' })
    expect(withLink[0].body).toContain('https://x.test/e/e1')
    const without = buildMessages({ academy, event, plan })
    expect(without[0].body).not.toContain('http')
  })

  it('감사 문구에 사진 링크를 넣을 수 있다', () => {
    const messages = buildMessages({ academy, event, plan, photoUrl: 'https://photo.test/album' })
    expect(messages[3].body).toContain('https://photo.test/album')
  })

  it('문자 길이를 바이트로 알려 준다', () => {
    expect(messageBytes('가나다')).toBe(9)
    expect(messageBytes('abc')).toBe(3)
  })
})
