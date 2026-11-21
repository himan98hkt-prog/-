import { describe, it, expect } from 'vitest'
import { parseCsv, toCsv, mapHeaders, normalizePhone, parseStudentTable } from '../src/core/csv.js'

describe('CSV 파싱', () => {
  it('따옴표 안의 쉼표와 줄바꿈을 지킨다', () => {
    const rows = parseCsv('이름,메모\n김하늘,"형제 할인, 3월부터"\n이바다,"두 줄\n메모"')
    expect(rows[1]).toEqual(['김하늘', '형제 할인, 3월부터'])
    expect(rows[2][1]).toBe('두 줄\n메모')
  })

  it('두 겹 따옴표는 한 개로 되돌린다', () => {
    expect(parseCsv('a\n"그는 ""안녕"" 이라 했다"')[1][0]).toBe('그는 "안녕" 이라 했다')
  })

  it('엑셀에서 복사한 탭 구분도 그대로 받는다', () => {
    const rows = parseCsv('이름\t학년\n김하늘\t초3')
    expect(rows[1]).toEqual(['김하늘', '초3'])
  })

  it('빈 줄은 버린다', () => {
    expect(parseCsv('이름\n김하늘\n\n\n이바다')).toHaveLength(3)
  })

  it('내보낸 CSV 를 다시 읽으면 원본과 같다', () => {
    const headers = ['이름', '메모']
    const rows = [['김하늘', '쉼표, 따옴표"']]
    expect(parseCsv(toCsv(headers, rows)).slice(1)).toEqual(rows)
  })
})

describe('헤더 인식', () => {
  it('한국어 헤더를 필드에 맞춘다', () => {
    const map = mapHeaders(['이름', '학년', '학부모 연락처', '반'])
    expect(map.name).toBe(0)
    expect(map.grade).toBe(1)
    expect(map.parent_phone).toBe(2)
    expect(map.class).toBe(3)
  })

  it('모르는 헤더는 -1', () => {
    expect(mapHeaders(['혈액형']).name).toBe(-1)
  })
})

describe('전화번호 정리', () => {
  it('구분자·국가번호를 정리해 하이픈 형태로 만든다', () => {
    expect(normalizePhone('01012345678')).toBe('010-1234-5678')
    expect(normalizePhone('010 1234 5678')).toBe('010-1234-5678')
    expect(normalizePhone('+82 10-1234-5678')).toBe('010-1234-5678')
    expect(normalizePhone('0212345678')).toBe('021-234-5678')
    expect(normalizePhone('')).toBe('')
  })
})

describe('원생 명단 가져오기', () => {
  const csv = [
    '이름,학년,학교,학부모 연락처,반',
    '김하늘,초3,행복초,010-1111-2222,초등A',
    '이바다,초5,행복초,01033334444,초등B',
    ',,,,',
    '김하늘,초3,행복초,010-1111-2222,초등A'
  ].join('\n')

  it('헤더를 읽고 값을 정리해서 돌려준다', () => {
    const { rows, hasHeader } = parseStudentTable(csv)
    expect(hasHeader).toBe(true)
    expect(rows).toHaveLength(2)
    expect(rows[0]).toMatchObject({ name: '김하늘', grade: '초3', parent_phone: '010-1111-2222', className: '초등A' })
    expect(rows[1].parent_phone).toBe('010-3333-4444')
  })

  it('파일 안 중복과 이름 없는 줄은 건너뛰고 이유를 남긴다', () => {
    const { skipped } = parseStudentTable(csv)
    expect(skipped.map((s) => s.reason)).toEqual(['파일 안 중복'])
  })

  it('이미 등록된 원생은 중복 표시만 하고 목록에는 남긴다', () => {
    const { rows } = parseStudentTable(csv, { existing: [{ name: '김하늘', parent_phone: '010-1111-2222' }] })
    expect(rows[0].duplicate).toBe(true)
    expect(rows[1].duplicate).toBe(false)
  })

  it('헤더 없이 이름만 붙여넣어도 등록 후보가 된다', () => {
    const { rows, hasHeader } = parseStudentTable('김하늘\n이바다\n박구름')
    expect(hasHeader).toBe(false)
    expect(rows.map((r) => r.name)).toEqual(['김하늘', '이바다', '박구름'])
  })
})
