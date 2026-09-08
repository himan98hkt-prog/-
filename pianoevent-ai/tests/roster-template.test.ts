import { describe, expect, it } from 'vitest'
import { parseRoster } from '@/lib/program/roster'
import {
  LEVEL_WORDS,
  ROSTER_FIELDS,
  ROSTER_HEADERS,
  ROSTER_PITFALLS,
  ROSTER_SAMPLE,
  rosterSampleText,
  rosterTemplateCsv,
} from '@/lib/program/template'
import { LEVEL_LABEL, type Level } from '@/lib/types'

describe('명단 양식', () => {
  it('엑셀에서 열어도 한글이 깨지지 않는다 (BOM)', () => {
    expect(rosterTemplateCsv().charCodeAt(0)).toBe(0xfeff)
  })

  it('머리글과 예시가 함께 들어 있다 — 파일만 열어 보셔도 알 수 있게', () => {
    const csv = rosterTemplateCsv()
    for (const head of ROSTER_HEADERS) expect(csv).toContain(head)
    expect(csv).toContain('김서연')
    expect(csv).toContain('엘리제를 위하여')
  })

  it('쉼표가 든 칸을 따옴표로 감싼다', () => {
    // 예시에 쉼표가 없더라도 규칙 자체가 맞아야 한다
    const csv = rosterTemplateCsv()
    for (const line of csv.split('\r\n').filter(Boolean)) {
      const quotes = (line.match(/"/g) ?? []).length
      expect(quotes % 2).toBe(0)
    }
  })

  it('줄 끝이 CRLF 다 — 엑셀이 한 줄로 읽지 않게', () => {
    expect(rosterTemplateCsv()).toContain('\r\n')
  })

  /**
   * 가장 중요한 검사.
   * 우리가 나눠 준 양식을 우리 파서가 못 읽으면, 원장님은 시킨 대로 하고도 막힌다.
   */
  it('나눠 준 양식을 그대로 붙여넣으면 읽힌다', () => {
    const parsed = parseRoster(rosterSampleText())
    expect(parsed.headerDetected).toBe(true)
    expect(parsed.errors).toEqual([])
    expect(parsed.rows).toHaveLength(ROSTER_SAMPLE.length)
    expect(parsed.rows[0].student_name).toBe('김서연')
    expect(parsed.rows[0].piece_title).toBe('엘리제를 위하여')
    expect(parsed.rows[0].duration_sec).toBe(210)
    expect(parsed.rows[0].level).toBe('intermediate')
  })

  it('양식의 CSV 를 그대로 붙여넣어도 읽힌다 (쉼표로 나뉜 채)', () => {
    const parsed = parseRoster(rosterTemplateCsv().replace(/^﻿/, ''))
    expect(parsed.rows).toHaveLength(ROSTER_SAMPLE.length)
    expect(parsed.rows.map((row) => row.student_name)).toContain('박지호')
  })

  it('비워 둔 칸이 있어도 읽힌다 — 예시 셋째 줄에 빈칸이 있다', () => {
    const parsed = parseRoster(rosterSampleText())
    const yerin = parsed.rows.find((row) => row.student_name === '정예린')
    expect(yerin).toBeTruthy()
    expect(yerin?.piece_title).toBe('아라베스크')
  })

  it('화면 설명이 실제 칸과 같은 차례다', () => {
    expect(ROSTER_FIELDS.map((field) => field.name)).toEqual([...ROSTER_HEADERS])
  })

  it('꼭 필요한 칸은 이름 하나뿐이라고 말한다', () => {
    expect(ROSTER_FIELDS.filter((field) => field.required).map((f) => f.name)).toEqual(['이름'])
  })

  it('난이도에 적을 수 있다고 알려 준 말이 실제로 읽힌다', () => {
    for (const level of Object.keys(LEVEL_LABEL) as Level[]) {
      for (const word of LEVEL_WORDS[level]) {
        const parsed = parseRoster(`이름\t연주곡\t작곡가\t소요시간\t난이도\n아이\t곡\t\t\t${word}`)
        expect(parsed.rows[0]?.level, `${level} — "${word}"`).toBe(level)
      }
    }
  })

  it('자주 하는 실수를 미리 적어 둔다', () => {
    expect(ROSTER_PITFALLS.length).toBeGreaterThanOrEqual(3)
    for (const row of ROSTER_PITFALLS) {
      expect(row.wrong.length).toBeGreaterThan(0)
      expect(row.why.length).toBeGreaterThan(0)
    }
  })
})
