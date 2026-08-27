import { describe, expect, it } from 'vitest'
import { buildProgram } from '@/lib/program/order'
import { getTheme } from '@/lib/design/themes'
import { buildStageDeck, DEFAULT_STAGE_OPTIONS } from '@/lib/stage/deck'
import { buildPptx, pptFont } from '@/lib/stage/pptx'
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

describe('파워포인트 파일 만들기', () => {
  const themed = getTheme('classic-navy')
  const file = () => buildPptx({ slides: deck(), theme: themed, academyName: '하모니 피아노학원', title: '제12회 정기 연주회' })

  it('ZIP 으로 시작한다 — 파워포인트가 여는 그 형식', () => {
    const bytes = file()
    expect(bytes[0]).toBe(0x50)
    expect(bytes[1]).toBe(0x4b)
    expect(bytes.length).toBeGreaterThan(5_000)
  })

  it('파워포인트가 요구하는 부품이 모두 들어 있다', () => {
    const text = new TextDecoder('utf-8').decode(file())
    for (const part of [
      '[Content_Types].xml',
      '_rels/.rels',
      'ppt/presentation.xml',
      'ppt/slideMasters/slideMaster1.xml',
      'ppt/slideLayouts/slideLayout1.xml',
      'ppt/theme/theme1.xml',
      'ppt/slides/slide1.xml',
    ]) {
      expect(text).toContain(part)
    }
  })

  it('슬라이드 수가 화면과 같다', () => {
    const slides = deck()
    const text = new TextDecoder('utf-8').decode(
      buildPptx({ slides, theme: themed, academyName: '하모니', title: '연주회' }),
    )
    const parts = text.match(/ppt\/slides\/slide\d+\.xml(?!\.rels)/g) ?? []
    // 각 슬라이드는 Content_Types · 관계 · 파일 자체로 여러 번 등장한다 — 번호의 최댓값을 본다
    const max = Math.max(...parts.map((name) => Number(name.match(/slide(\d+)/)![1])))
    expect(max).toBe(slides.length)
  })

  it('학생 이름과 곡이 글자로 들어간다 — 그림이 아니라서 고칠 수 있다', () => {
    const text = new TextDecoder('utf-8').decode(file())
    expect(text).toContain('<a:t>윤채원</a:t>')
    expect(text).toContain('녹턴 op.9 no.2')
    expect(text).toContain('txBox="1"')
  })

  it('16:9 용지로 만든다', () => {
    const text = new TextDecoder('utf-8').decode(file())
    expect(text).toContain('<p:sldSz cx="12192000" cy="6858000"/>')
  })

  it('테마를 바꾸면 파일 내용도 바뀐다', () => {
    const navy = new TextDecoder('utf-8').decode(file())
    const blush = new TextDecoder('utf-8').decode(
      buildPptx({ slides: deck(), theme: getTheme('blush-romance'), academyName: '하모니', title: '연주회' }),
    )
    expect(blush).not.toBe(navy)
    expect(navy).toContain(getTheme('classic-navy').palette.accent.replace('#', '').toUpperCase())
    expect(blush).toContain(getTheme('blush-romance').palette.accent.replace('#', '').toUpperCase())
  })

  it('어두운 화면으로 뽑으면 바탕이 잉크색이 된다', () => {
    const dark = new TextDecoder('utf-8').decode(
      buildPptx({ slides: deck(), theme: themed, academyName: '하모니', title: '연주회', dark: true }),
    )
    expect(dark).toContain(themed.palette.ink.replace('#', '').toUpperCase())
  })

  it('줄 간격은 10만분율로 적는다 — 단위를 틀리면 본문이 사라진다', () => {
    const text = new TextDecoder('utf-8').decode(file())
    for (const value of text.match(/<a:spcPct val="(\d+)"\/>/g) ?? []) {
      expect(Number(value.match(/\d+/)![0])).toBeGreaterThanOrEqual(100_000)
    }
  })

  it('이름에 &, <, " 가 있어도 파일이 깨지지 않는다', () => {
    const tricky = [student('김<서>연 & "박"', 'beginner', 100, { piece_title: 'A & B <C>' })]
    const text = new TextDecoder('utf-8').decode(
      buildPptx({
        slides: buildStageDeck(event, buildProgram(tricky), '하모니 & 피아노 <학원>'),
        theme: themed,
        academyName: '하모니 & 피아노 <학원>',
        title: '연주회 & 발표회',
      }),
    )
    // 글자 부분만 떼어 본다 — ZIP 안에는 압축 표식 같은 이진 바이트도 섞여 있다
    const runs = text.match(/<a:t>[^<]*<\/a:t>/g) ?? []
    expect(runs.length).toBeGreaterThan(3)
    expect(runs.join('')).toContain('김&lt;서&gt;연 &amp; &quot;박&quot;')
    expect(runs.join('')).toContain('하모니 &amp; 피아노 &lt;학원&gt;')
    for (const run of runs) expect(run).not.toMatch(/&(?!amp;|lt;|gt;|quot;|apos;|#)/)
  })

  it('같은 입력이면 같은 파일이 나온다 — 시각을 기록하지 않는다', () => {
    expect(Array.from(file())).toEqual(Array.from(file()))
  })

  it('웹폰트 이름 대신 컴퓨터에 있는 글꼴 이름을 쓴다', () => {
    expect(pptFont("'Nanum Myeongjo', Batang, serif")).toBe('바탕')
    expect(pptFont("'Gaegu', Gungsuh, cursive")).toBe('궁서')
    expect(pptFont("'Noto Sans KR', 'Malgun Gothic', sans-serif")).toBe('맑은 고딕')
  })
})
