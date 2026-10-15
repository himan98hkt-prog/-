import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'
import { parseRoster } from '@/lib/program/roster'
import { xlsxSheetNames, xlsxToText } from '@/lib/program/xlsx'

/**
 * 원장님께 연습용으로 드리는 엑셀이 **우리 프로그램에서 실제로 읽히는지** 본다.
 *
 * 나눠 드린 파일이 안 읽히면 시킨 대로 하고도 막히신다. 그게 가장 나쁘다.
 * 그래서 만드는 길과 읽는 길을 여기서 한 번 맞대어 본다.
 */
const OUT = join(process.cwd(), '배포')
const read = (name: string) => readFileSync(join(OUT, name))

beforeAll(() => {
  if (!existsSync(join(OUT, '학생명단-예시.xlsx'))) {
    execFileSync(process.execPath, [join('scripts', 'sample-xlsx.mjs')], { stdio: 'ignore' })
  }
})

describe('나눠 드리는 연습용 엑셀', () => {
  it('한 장짜리를 우리 파서가 그대로 읽는다', () => {
    const parsed = parseRoster(xlsxToText(read('학생명단-예시.xlsx')))
    expect(parsed.headerDetected).toBe(true)
    expect(parsed.rows).toHaveLength(12)
    expect(parsed.rows[0]).toMatchObject({ student_name: '김서연', duration_sec: 210, level: 'intermediate' })
  })

  it('못 읽은 줄이 하나도 없다', () => {
    expect(parseRoster(xlsxToText(read('학생명단-예시.xlsx'))).errors).toEqual([])
  })

  it('비워 둔 칸을 곡 사전이 채운다 — 그걸 보시라고 일부러 비워 뒀다', () => {
    expect(parseRoster(xlsxToText(read('학생명단-예시.xlsx'))).autofilled.length).toBeGreaterThan(0)
  })

  it('듀엣이 난이도로 읽힌다 — 연탄곡 두 줄이 들어 있다', () => {
    const parsed = parseRoster(xlsxToText(read('학생명단-예시.xlsx')))
    expect(parsed.rows.filter((r) => r.level === 'ensemble')).toHaveLength(2)
  })

  it('학년별 파일은 장이 세 개다 — 장 고르기를 연습해 보시라고', () => {
    expect(xlsxSheetNames(read('학생명단-학년별-예시.xlsx'))).toEqual(['1학년', '2학년', '3학년'])
  })

  it('장마다 그 학년 아이만 있다', () => {
    const buf = read('학생명단-학년별-예시.xlsx')
    expect(parseRoster(xlsxToText(buf, 0)).rows[0].student_name).toBe('임하람')
    expect(parseRoster(xlsxToText(buf, 2)).rows[0].student_name).toBe('임가온')
  })
})
