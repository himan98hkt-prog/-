import { describe, expect, it } from 'vitest'
import { BOX_SHEETS, BULK_FROM_SHEETS, REAM_SHEETS, paperBulkNote, printSummary, printSummaryLine } from '@/lib/print/paper'

describe('뽑기 전 마지막 확인', () => {
  it('넷을 보여 준다 — 종이 · 장수 · 색 · 양면', () => {
    const rows = printSummary({ paperLabel: 'A4 세로', sheets: 12 })
    expect(rows.map((r) => r.what)).toEqual(['종이', '장수', '색', '양면'])
  })

  it('한 부면 장수만 적는다', () => {
    const rows = printSummary({ paperLabel: 'A4 세로', sheets: 12 })
    expect(rows[1].value).toBe('12장')
  })

  it('여러 부면 곱한 값까지 적어 준다 — 100부를 뽑기 전에 아셔야 한다', () => {
    const rows = printSummary({ paperLabel: 'A4 세로', sheets: 12, copies: 100 })
    expect(rows[1].value).toContain('1,200장')
  })

  it('양면으로 뽑아야 하는 인쇄물은 넘기는 방향까지 적는다', () => {
    expect(printSummary({ paperLabel: 'A4 세로', sheets: 2, duplex: true })[3].value).toContain('짧은 쪽')
    expect(printSummary({ paperLabel: 'A4 세로', sheets: 2 })[3].value).toContain('아니요')
  })

  it('글만 있는 인쇄물은 흑백으로 뽑으셔도 된다고 말해 준다', () => {
    expect(printSummary({ paperLabel: 'A4 세로', sheets: 1, grayOk: true })[2].value).toContain('흑백')
  })

  it('한 줄로도 읽힌다', () => {
    const line = printSummaryLine(printSummary({ paperLabel: 'A4 세로', sheets: 12 }))
    expect(line).toBe('A4 세로 · 12장 · 컬러 · 아니요 (한 면씩)')
  })

  it('부수가 이상해도 멈추지 않는다', () => {
    expect(printSummary({ paperLabel: 'A4 세로', sheets: 3, copies: 0 })[1].value).toBe('3장')
  })
})

describe('종이를 몸으로 아는 단위로', () => {
  it('적게 뽑으실 때는 아무 말도 하지 않는다 — 겁줄 일이 아니다', () => {
    expect(paperBulkNote(12)).toBeNull()
    expect(paperBulkNote(BULK_FROM_SHEETS - 1)).toBeNull()
  })

  it('백 장쯤부터는 종이를 채워 두시라고 한다', () => {
    const note = paperBulkNote(BULK_FROM_SHEETS)
    expect(note).toContain('연')
    expect(note).toContain('채워')
  })

  it('한 연에 못 미치면 연으로 견줘 준다', () => {
    expect(paperBulkNote(300)).toContain('연')
  })

  it('연 단위면 프린터에 그만큼 있는지 보라고 한다', () => {
    const note = paperBulkNote(1200)
    expect(note).toContain('연')
    expect(note).toContain('프린터')
  })

  it('박스를 넘으면 인쇄소를 권한다 — 학원 프린터로는 못 한다', () => {
    const note = paperBulkNote(BOX_SHEETS + 100)
    expect(note).toContain('박스')
    expect(note).toContain('인쇄소')
  })

  it('한 연·한 박스가 실제 값이다', () => {
    expect(REAM_SHEETS).toBe(500)
    expect(BOX_SHEETS).toBe(2500)
  })

  it('어느 장수에서도 멈추지 않는다', () => {
    for (const n of [0, 1, 249, 250, 499, 500, 2499, 2500, 99999]) {
      expect(() => paperBulkNote(n), `${n}장`).not.toThrow()
    }
  })
})
