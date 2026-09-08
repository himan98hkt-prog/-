import { describe, expect, it } from 'vitest'
import { parseDurationSec, parseLevel, parseRoster, toRosterCsv } from '@/lib/program/roster'

describe('parseDurationSec', () => {
  it('m:ss 를 읽는다', () => {
    expect(parseDurationSec('3:20')).toBe(200)
    expect(parseDurationSec('10:05')).toBe(605)
  })

  it('한글 표기를 읽는다', () => {
    expect(parseDurationSec('3분 20초')).toBe(200)
    expect(parseDurationSec('3분')).toBe(180)
    expect(parseDurationSec('45초')).toBe(45)
  })

  it('단위 없는 숫자는 20 이하면 분, 크면 초로 읽는다', () => {
    expect(parseDurationSec('3')).toBe(180)
    expect(parseDurationSec('200')).toBe(200)
    expect(parseDurationSec('2.5')).toBe(150)
  })

  it('읽지 못하면 null 을 돌려준다', () => {
    expect(parseDurationSec('세 시간쯤')).toBeNull()
    expect(parseDurationSec('')).toBeNull()
    expect(parseDurationSec(null)).toBeNull()
  })
})

describe('parseLevel', () => {
  it('한글·영문 표기를 모두 인식한다', () => {
    expect(parseLevel('초급')).toBe('beginner')
    expect(parseLevel('중급')).toBe('intermediate')
    expect(parseLevel('고급')).toBe('advanced')
    expect(parseLevel('듀엣')).toBe('ensemble')
    expect(parseLevel('Advanced')).toBe('advanced')
  })

  it('모르는 값은 초급으로 둔다', () => {
    expect(parseLevel('???')).toBe('beginner')
    expect(parseLevel(null)).toBe('beginner')
  })
})

describe('parseRoster', () => {
  it('헤더가 있는 엑셀 붙여넣기(TSV)를 읽는다', () => {
    const result = parseRoster(
      ['이름\t연주곡\t작곡가\t소요시간\t난이도\t비고', '김서연\t엘리제를 위하여\t베토벤\t3:30\t중급\t세 번째 무대'].join(
        '\n',
      ),
    )
    expect(result.headerDetected).toBe(true)
    expect(result.rows).toHaveLength(1)
    expect(result.rows[0]).toMatchObject({
      student_name: '김서연',
      piece_title: '엘리제를 위하여',
      composer: '베토벤',
      duration_sec: 210,
      level: 'intermediate',
      note: '세 번째 무대',
    })
  })

  it('헤더 순서가 뒤바뀌어도 이름으로 찾아 읽는다', () => {
    const result = parseRoster(['연주곡,이름,난이도', '터키 행진곡,강민준,중급'].join('\n'))
    expect(result.rows[0].student_name).toBe('강민준')
    expect(result.rows[0].piece_title).toBe('터키 행진곡')
  })

  it('헤더가 없으면 열 순서로 읽는다', () => {
    const result = parseRoster('박지호,즐거운 나의 집,비숍,1:10,초급')
    expect(result.headerDetected).toBe(false)
    expect(result.rows[0].student_name).toBe('박지호')
    expect(result.rows[0].duration_sec).toBe(70)
  })

  it('따옴표로 감싼 CSV 필드 안의 쉼표를 보존한다', () => {
    const result = parseRoster('이름,연주곡\n이하윤,"소녀의 기도, Op.4"')
    expect(result.rows[0].piece_title).toBe('소녀의 기도, Op.4')
  })

  it('이름이 없는 행은 건너뛰고 이유를 남긴다', () => {
    const result = parseRoster('이름,연주곡\n,곡만 있음\n김학생,곡')
    expect(result.rows).toHaveLength(1)
    expect(result.errors.some((e) => e.includes('이름이 비어'))).toBe(true)
  })

  it('읽지 못한 소요시간은 경고로 알린다', () => {
    const result = parseRoster('이름,연주곡,작곡가,소요시간\n김학생,곡,작곡가,대충 3분쯤')
    expect(result.rows[0].duration_sec).toBeNull()
    expect(result.errors.some((e) => e.includes('소요시간'))).toBe(true)
  })

  it('빈 입력을 안전하게 처리한다', () => {
    expect(parseRoster('   ').rows).toHaveLength(0)
  })
})

describe('toRosterCsv', () => {
  it('엑셀 한글 깨짐 방지를 위해 BOM 을 붙이고 쉼표를 이스케이프한다', () => {
    const csv = toRosterCsv([
      { student_name: '김서연', piece_title: '소녀의 기도, Op.4', composer: '바다르체프스카', duration_sec: 210, level: 'intermediate', note: null },
    ])
    expect(csv.startsWith('﻿')).toBe(true)
    expect(csv).toContain('"소녀의 기도, Op.4"')
  })
})
