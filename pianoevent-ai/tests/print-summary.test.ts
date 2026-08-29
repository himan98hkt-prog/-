import { describe, expect, it } from 'vitest'
import { printSummary, printSummaryLine } from '@/lib/print/paper'

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
