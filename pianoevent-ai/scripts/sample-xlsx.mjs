#!/usr/bin/env node
/**
 * 연습용 엑셀 명단 만들기.
 *
 *   node scripts/sample-xlsx.mjs
 *
 * 원장님이 프로그램을 처음 켜시면 "그래서 뭘 올려요?" 에서 멈추신다.
 * 실제로 끌어다 놓아 볼 파일이 손에 있어야 한다. 두 개를 만든다.
 *
 *   학생명단-예시.xlsx        — 한 장짜리, 아이 12명. 기본 연습용
 *   학생명단-학년별-예시.xlsx — 장 세 개(1·2·3학년). 장 고르기 연습용
 *
 * 파일은 바깥 라이브러리 없이 직접 쓴다 (.xlsx 는 ZIP 안의 XML 이다).
 * 프로그램이 그 파일을 읽는 길과 같은 길로 만들어져야 연습이 연습이 된다.
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const OUT = join(process.cwd(), '배포')

// ── 압축하지 않는 ZIP (엑셀도 그대로 연다)
const CRC = (() => {
  const table = new Uint32Array(256)
  for (let i = 0; i < 256; i += 1) {
    let c = i
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    table[i] = c >>> 0
  }
  return table
})()

function crc32(bytes) {
  let c = 0xffffffff
  for (const b of bytes) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function zipStore(entries) {
  const locals = []
  const centrals = []
  let offset = 0
  for (const entry of entries) {
    const name = Buffer.from(entry.name, 'utf8')
    const data = Buffer.from(entry.data, 'utf8')
    const sum = crc32(data)

    const local = Buffer.alloc(30 + name.length)
    local.writeUInt32LE(0x04034b50, 0)
    local.writeUInt16LE(20, 4)
    local.writeUInt16LE(0x0800, 6)
    local.writeUInt32LE(sum, 14)
    local.writeUInt32LE(data.length, 18)
    local.writeUInt32LE(data.length, 22)
    local.writeUInt16LE(name.length, 26)
    name.copy(local, 30)

    const central = Buffer.alloc(46 + name.length)
    central.writeUInt32LE(0x02014b50, 0)
    central.writeUInt16LE(20, 4)
    central.writeUInt16LE(20, 6)
    central.writeUInt16LE(0x0800, 8)
    central.writeUInt32LE(sum, 16)
    central.writeUInt32LE(data.length, 20)
    central.writeUInt32LE(data.length, 24)
    central.writeUInt16LE(name.length, 28)
    central.writeUInt32LE(offset, 42)
    name.copy(central, 46)

    locals.push(local, data)
    centrals.push(central)
    offset += local.length + data.length
  }
  const dir = Buffer.concat(centrals)
  const eocd = Buffer.alloc(22)
  eocd.writeUInt32LE(0x06054b50, 0)
  eocd.writeUInt16LE(entries.length, 8)
  eocd.writeUInt16LE(entries.length, 10)
  eocd.writeUInt32LE(dir.length, 12)
  eocd.writeUInt32LE(offset, 16)
  return Buffer.concat([...locals, dir, eocd])
}

const esc = (v) =>
  String(v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

const COL = (n) => {
  let s = ''
  let i = n
  do {
    s = String.fromCharCode(65 + (i % 26)) + s
    i = Math.floor(i / 26) - 1
  } while (i >= 0)
  return s
}

/** 표(2차원 배열) → sheet XML. 글자는 칸에 바로 적는다(inlineStr) — 읽기 쉽고 어긋날 일이 없다 */
function sheetXml(rows) {
  const body = rows
    .map((cells, r) => {
      const tds = cells
        .map((v, c) => {
          if (v === '' || v === null || v === undefined) return ''
          const ref = `${COL(c)}${r + 1}`
          // 소요시간은 일부러 3:30 처럼 **글자로** 넣는다.
          // 엑셀에서 직접 치시면 엑셀이 시간으로 바꿔 두는데, 프로그램이 그것도 되돌린다.
          return `<c r="${ref}" t="inlineStr"><is><t xml:space="preserve">${esc(v)}</t></is></c>`
        })
        .join('')
      return `<row r="${r + 1}">${tds}</row>`
    })
    .join('')
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${body}</sheetData></worksheet>`
}

/** 장 여러 개를 담은 .xlsx 한 개 */
function workbook(sheets) {
  const entries = [
    {
      name: '[Content_Types].xml',
      data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
${sheets
  .map(
    (_, i) =>
      `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`,
  )
  .join('\n')}
</Types>`,
    },
    {
      name: '_rels/.rels',
      data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`,
    },
    {
      name: 'xl/workbook.xml',
      data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>${sheets
        .map((s, i) => `<sheet name="${esc(s.name)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`)
        .join('')}</sheets>
</workbook>`,
    },
    {
      name: 'xl/_rels/workbook.xml.rels',
      data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
${sheets
  .map(
    (_, i) =>
      `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`,
  )
  .join('\n')}
</Relationships>`,
    },
    ...sheets.map((s, i) => ({ name: `xl/worksheets/sheet${i + 1}.xml`, data: sheetXml(s.rows) })),
  ]
  return zipStore(entries)
}

const HEAD = ['이름', '연주곡', '작곡가', '소요시간', '난이도', '비고']

/**
 * 연습용 명단.
 * 일부러 **비운 칸**을 섞어 두었다 — 비워도 곡 사전이 채운다는 것을 눈으로 보셔야 한다.
 */
const ONE = [
  HEAD,
  ['김서연', '엘리제를 위하여', '베토벤', '3:30', '중급', '세 번째 무대입니다'],
  ['박지호', '즐거운 나의 집', '비숍', '1:10', '초급', '시작한 지 다섯 달'],
  ['정예린', '아라베스크', '부르크뮐러', '', '중급', ''],
  ['한도윤', '미뉴에트 G장조', '바흐', '2:10', '초급', '할머니가 오십니다'],
  ['최은우', '작은 별 변주곡', '', '', '초급', ''],
  ['오수아', '인벤션 1번', '바흐', '2:45', '중급', '올해 콩쿠르 준비 중'],
  ['임가온', '터키 행진곡', '모차르트', '3:20', '고급', ''],
  ['윤채원', '인형의 꿈', '오귀스트', '2:30', '중급', '동생과 함께 다닙니다'],
  ['배시우', '즉흥환상곡', '쇼팽', '5:10', '고급', '올해 마지막 무대'],
  ['임하람', '봄노래', '', '', '초급', '올해 처음 무대에 섭니다'],
  ['강민준', '캐논 변주곡', '파헬벨', '4:00', '듀엣', '누나와 함께 연탄'],
  ['강서아', '캐논 변주곡', '파헬벨', '4:00', '듀엣', '동생과 함께 연탄'],
]

const BY_GRADE = [
  {
    name: '1학년',
    rows: [
      HEAD,
      ['임하람', '봄노래', '', '', '초급', '올해 처음 무대에 섭니다'],
      ['박지호', '즐거운 나의 집', '비숍', '1:10', '초급', '시작한 지 다섯 달'],
      ['한도윤', '미뉴에트 G장조', '바흐', '2:10', '초급', ''],
      ['최은우', '작은 별 변주곡', '', '', '초급', ''],
    ],
  },
  {
    name: '2학년',
    rows: [
      HEAD,
      ['김서연', '엘리제를 위하여', '베토벤', '3:30', '중급', '세 번째 무대입니다'],
      ['정예린', '아라베스크', '부르크뮐러', '', '중급', ''],
      ['오수아', '인벤션 1번', '바흐', '2:45', '중급', ''],
      ['윤채원', '인형의 꿈', '오귀스트', '2:30', '중급', '동생과 함께 다닙니다'],
    ],
  },
  {
    name: '3학년',
    rows: [
      HEAD,
      ['임가온', '터키 행진곡', '모차르트', '3:20', '고급', ''],
      ['배시우', '즉흥환상곡', '쇼팽', '5:10', '고급', '올해 마지막 무대'],
      ['강민준', '캐논 변주곡', '파헬벨', '4:00', '듀엣', '누나와 함께 연탄'],
      ['강서아', '캐논 변주곡', '파헬벨', '4:00', '듀엣', '동생과 함께 연탄'],
    ],
  },
]

mkdirSync(OUT, { recursive: true })

const one = join(OUT, '학생명단-예시.xlsx')
writeFileSync(one, workbook([{ name: '학생명단', rows: ONE }]))
console.log(`  ✓ ${one} — 아이 ${ONE.length - 1}명, 한 장`)

const many = join(OUT, '학생명단-학년별-예시.xlsx')
writeFileSync(many, workbook(BY_GRADE))
console.log(`  ✓ ${many} — 장 ${BY_GRADE.length}개 (${BY_GRADE.map((s) => s.name).join(' · ')})`)

console.log('\n연습용 엑셀 2개를 만들었습니다.')
