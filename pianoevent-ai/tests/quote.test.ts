import { describe, expect, it } from 'vitest'
import { getPack, getTemplate, packTemplates } from '@/lib/design/templates'
import { paperText, quoteRow, quoteRows, quoteSentence, quoteText, quoteTotal } from '@/lib/print/quote'

describe('인쇄소가 쓰는 말로', () => {
  it('용지를 mm 로 적는다 — 인쇄소는 mm 로 말한다', () => {
    expect(paperText('a4-portrait')).toBe('A4 세로 (210 × 297mm)')
  })

  it('가로 인쇄물은 가로가 길게 적힌다', () => {
    expect(paperText('a4-landscape')).toBe('A4 가로 (297 × 210mm)')
  })

  it('현수막 시안도 실제 크기로 적힌다', () => {
    expect(paperText('banner-wide')).toContain('×')
  })
})

describe('한 줄 견적', () => {
  const poster = getTemplate('poster-classic')

  it('포스터에는 빳빳한 종이를 권한다 — 벽에 붙는다', () => {
    expect(quoteRow(poster, 12, 1).stock).toContain('스노우지')
  })

  it('부수를 곱해 총 장수를 낸다 — 인쇄소가 가장 먼저 묻는다', () => {
    const row = quoteRow(poster, 12, 30)
    expect(row.sheets).toBe(1)
    expect(row.total).toBe(30)
  })

  it('0부는 없다', () => {
    expect(quoteRow(poster, 12, 0).copies).toBe(1)
  })

  it('아이마다 한 장씩 나오는 양식은 명단 수를 따라간다', () => {
    const perStudent = quoteRows([getTemplate('certificate')], 12, 1)[0]
    expect(perStudent.sheets).toBeGreaterThan(1)
  })

  it('전화로 읽으실 한 줄이 된다', () => {
    expect(quoteSentence(quoteRow(poster, 12, 30))).toBe(
      '클래식 포스터 — A4 세로 (210 × 297mm), 스노우지 200g (반광), 30부 (총 30장)',
    )
  })
})

describe('한 벌 견적', () => {
  const pack = getPack('audience')
  const rows = quoteRows(packTemplates(pack!), 12, 40)

  it('한 벌 안의 양식마다 한 줄씩', () => {
    expect(rows.length).toBeGreaterThan(1)
  })

  it('갈래마다 권하는 종이가 다르다 — 포스터와 순서지는 두께가 달라야 한다', () => {
    expect(new Set(rows.map((r) => r.stock)).size).toBeGreaterThan(1)
  })

  it('합계를 낸다', () => {
    expect(quoteTotal(rows)).toBe(rows.reduce((sum, r) => sum + r.total, 0))
  })

  it('문자로 보내실 글이 된다', () => {
    const text = quoteText('제12회 정기 연주회', rows)
    expect(text).toContain('[제12회 정기 연주회] 인쇄 견적 문의')
    expect(text).toContain('합계')
    // 재단선 이야기를 빠뜨리면 인쇄소가 다시 묻는다
    expect(text).toContain('재단선')
  })
})
