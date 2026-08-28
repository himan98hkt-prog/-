import { deflateRawSync } from 'node:zlib'
import { describe, expect, it } from 'vitest'
import { zipStore } from '@/lib/stage/zip'
import { columnIndex, excelTimeToText, sharedStrings, sheetRows, unzip, xlsxRows, xlsxToText } from '@/lib/program/xlsx'
import { parseRoster } from '@/lib/program/roster'

const enc = (s: string) => new TextEncoder().encode(s)

/** 엑셀이 실제로 쓰는 모양으로 작은 .xlsx 한 개를 만든다 */
function workbook(sheet: string, strings: string[] = []): Buffer {
  const entries = [
    { name: 'xl/worksheets/sheet1.xml', data: enc(sheet) },
    ...(strings.length > 0
      ? [
          {
            name: 'xl/sharedStrings.xml',
            data: enc(
              `<sst count="${strings.length}">${strings.map((s) => `<si><t>${s}</t></si>`).join('')}</sst>`,
            ),
          },
        ]
      : []),
  ]
  return Buffer.from(zipStore(entries))
}

/** 압축한 ZIP — 진짜 엑셀이 내놓는 모양(deflate) */
function deflatedZip(name: string, body: string): Buffer {
  const data = deflateRawSync(Buffer.from(body, 'utf8'))
  const nameBytes = Buffer.from(name, 'utf8')
  const raw = Buffer.from(body, 'utf8')
  // crc32
  let crc = 0xffffffff
  for (const b of raw) {
    crc ^= b
    for (let k = 0; k < 8; k += 1) crc = crc & 1 ? 0xedb88320 ^ (crc >>> 1) : crc >>> 1
  }
  crc = (crc ^ 0xffffffff) >>> 0

  const local = Buffer.alloc(30 + nameBytes.length)
  local.writeUInt32LE(0x04034b50, 0)
  local.writeUInt16LE(20, 4)
  local.writeUInt16LE(0x0800, 6)
  local.writeUInt16LE(8, 8) // deflate
  local.writeUInt32LE(crc, 14)
  local.writeUInt32LE(data.length, 18)
  local.writeUInt32LE(raw.length, 22)
  local.writeUInt16LE(nameBytes.length, 26)
  nameBytes.copy(local, 30)

  const central = Buffer.alloc(46 + nameBytes.length)
  central.writeUInt32LE(0x02014b50, 0)
  central.writeUInt16LE(20, 4)
  central.writeUInt16LE(20, 6)
  central.writeUInt16LE(0x0800, 8)
  central.writeUInt16LE(8, 10)
  central.writeUInt32LE(crc, 16)
  central.writeUInt32LE(data.length, 20)
  central.writeUInt32LE(raw.length, 24)
  central.writeUInt16LE(nameBytes.length, 28)
  nameBytes.copy(central, 46)

  const eocd = Buffer.alloc(22)
  eocd.writeUInt32LE(0x06054b50, 0)
  eocd.writeUInt16LE(1, 8)
  eocd.writeUInt16LE(1, 10)
  eocd.writeUInt32LE(central.length, 12)
  eocd.writeUInt32LE(local.length + data.length, 16)

  return Buffer.concat([local, data, central, eocd])
}

describe('ZIP 풀기', () => {
  it('압축하지 않은 칸을 꺼낸다', () => {
    const files = unzip(Buffer.from(zipStore([{ name: 'a.txt', data: enc('안녕') }])))
    expect(files.get('a.txt')?.toString('utf8')).toBe('안녕')
  })

  it('압축한 칸도 꺼낸다 — 진짜 엑셀은 이쪽이다', () => {
    const files = unzip(deflatedZip('b.xml', '<r>가나다</r>'))
    expect(files.get('b.xml')?.toString('utf8')).toBe('<r>가나다</r>')
  })

  it('엑셀이 아닌 파일은 그렇다고 말해 준다', () => {
    expect(() => unzip(Buffer.from('이건 그냥 글입니다'))).toThrow('엑셀 파일이 아닙니다')
  })
})

describe('열 이름 읽기', () => {
  it('A 는 0, Z 는 25', () => {
    expect(columnIndex('A1')).toBe(0)
    expect(columnIndex('Z9')).toBe(25)
  })

  it('AA 는 26 — 열이 26개를 넘어가도 어긋나지 않는다', () => {
    expect(columnIndex('AA1')).toBe(26)
    expect(columnIndex('AB12')).toBe(27)
  })
})

describe('글자 모음', () => {
  it('<si> 하나씩 읽는다', () => {
    expect(sharedStrings('<sst><si><t>김서연</t></si><si><t>엘리제를 위하여</t></si></sst>')).toEqual([
      '김서연',
      '엘리제를 위하여',
    ])
  })

  it('서식이 섞여 <t> 가 나뉜 칸도 한 낱말로 붙인다', () => {
    expect(sharedStrings('<sst><si><r><t>엘리제</t></r><r><t>를 위하여</t></r></si></sst>')).toEqual([
      '엘리제를 위하여',
    ])
  })

  it('&amp; 같은 표기를 되돌린다', () => {
    expect(sharedStrings('<sst><si><t>바흐 &amp; 모차르트</t></si></sst>')).toEqual(['바흐 & 모차르트'])
  })
})

describe('엑셀이 시간으로 바꿔 버린 칸', () => {
  it('3:30 을 되돌린다 — 그대로 읽으면 0.0024 가 명단에 들어간다', () => {
    expect(excelTimeToText(210 / 86400)).toBe('3:30')
  })

  it('1:10 도 되돌린다', () => {
    expect(excelTimeToText(70 / 86400)).toBe('1:10')
  })

  it('사람이 적은 정수는 건드리지 않는다', () => {
    expect(excelTimeToText(210)).toBeNull()
    expect(excelTimeToText(3)).toBeNull()
  })

  it('한 시간을 넘는 값은 연주 시간이 아니다', () => {
    expect(excelTimeToText(0.5)).toBeNull()
  })
})

describe('표 읽기', () => {
  it('빈 칸이 있어도 열이 밀리지 않는다', () => {
    const rows = sheetRows(
      '<sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1" t="s"><v>1</v></c></row></sheetData>',
      ['김서연', '베토벤'],
    )
    expect(rows).toEqual([['김서연', '', '베토벤']])
  })

  it('칸에 바로 적힌 글(inlineStr)도 읽는다', () => {
    const rows = sheetRows('<sheetData><row><c r="A1" t="inlineStr"><is><t>박지호</t></is></c></row></sheetData>', [])
    expect(rows).toEqual([['박지호']])
  })

  it('숫자는 숫자대로 남는다', () => {
    const rows = sheetRows('<sheetData><row><c r="A1"><v>12</v></c></row></sheetData>', [])
    expect(rows).toEqual([['12']])
  })
})

describe('엑셀 파일 한 개를 통째로', () => {
  const sheet = `<worksheet><sheetData>
    <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c><c r="D1" t="s"><v>3</v></c></row>
    <row r="2"><c r="A2" t="s"><v>4</v></c><c r="B2" t="s"><v>5</v></c><c r="C2" t="s"><v>6</v></c><c r="D2"><v>0.0024305555555555556</v></c></row>
    <row r="3"><c r="A3" t="s"><v>7</v></c><c r="B3" t="s"><v>8</v></c><c r="C3" t="s"><v>9</v></c></row>
  </sheetData></worksheet>`
  const strings = [
    '이름',
    '연주곡',
    '작곡가',
    '소요시간',
    '김서연',
    '엘리제를 위하여',
    '베토벤',
    '박지호',
    '즐거운 나의 집',
    '비숍',
  ]

  it('줄과 칸이 그대로 나온다', () => {
    expect(xlsxRows(workbook(sheet, strings))[1]).toEqual(['김서연', '엘리제를 위하여', '베토벤', '3:30'])
  })

  it('붙여넣기 칸에 그대로 들어가는 글이 된다 (탭으로 나뉜 표)', () => {
    const text = xlsxToText(workbook(sheet, strings))
    expect(text.split('\n')).toHaveLength(3)
    expect(text.split('\n')[1]).toBe('김서연\t엘리제를 위하여\t베토벤\t3:30')
  })

  it('그 글을 우리 파서가 그대로 읽는다 — 길이 하나로 남는다', () => {
    const parsed = parseRoster(xlsxToText(workbook(sheet, strings)))
    expect(parsed.headerDetected).toBe(true)
    expect(parsed.rows).toHaveLength(2)
    expect(parsed.rows[0]).toMatchObject({
      student_name: '김서연',
      piece_title: '엘리제를 위하여',
      composer: '베토벤',
      duration_sec: 210,
    })
  })

  it('빈 줄은 버린다', () => {
    const empty = '<sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row><row r="2"/></sheetData>'
    expect(xlsxToText(workbook(empty, ['김서연']))).toBe('김서연')
  })

  it('표가 없는 ZIP 은 그렇다고 말해 준다', () => {
    expect(() => xlsxRows(Buffer.from(zipStore([{ name: 'hello.txt', data: enc('x') }])))).toThrow(
      '표를 찾지 못했습니다',
    )
  })
})
