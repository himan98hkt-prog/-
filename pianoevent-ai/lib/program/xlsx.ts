/**
 * 엑셀 파일(.xlsx) 을 표로 읽는다 — 바깥 라이브러리 없이.
 *
 * 원장님은 명단을 엑셀 파일로 갖고 계신다. "표를 복사해서 붙여넣으세요" 는
 * 한 단계다. 엑셀을 열고 → 범위를 잡고 → 복사하고 → 창을 바꾸고 → 붙여넣는다.
 * 다섯 걸음이다. 파일을 창에 끌어다 놓으면 한 걸음이 된다.
 *
 * .xlsx 는 ZIP 안에 XML 이 든 것이다. 필요한 것은 두 장뿐이다.
 *   xl/worksheets/sheet1.xml — 칸의 위치와 값
 *   xl/sharedStrings.xml     — 글자는 여기 모아 두고 번호로 가리킨다
 *
 * 라이브러리를 하나 더 들이지 않는 이유는 늘 같다. 이 프로그램은 원장님 컴퓨터에서
 * 인터넷 없이 돌아야 하고, 의존성은 적을수록 설치가 쉽다.
 */
import { inflateRawSync } from 'node:zlib'

/** ZIP 안에서 파일 하나를 꺼낸다 (압축 없음·deflate 둘 다) */
export function unzip(buf: Buffer): Map<string, Buffer> {
  const files = new Map<string, Buffer>()
  const eocd = findEocd(buf)
  if (eocd < 0) throw new Error('엑셀 파일이 아닙니다.')

  const count = buf.readUInt16LE(eocd + 10)
  let at = buf.readUInt32LE(eocd + 16)

  for (let i = 0; i < count; i += 1) {
    if (at + 46 > buf.length || buf.readUInt32LE(at) !== 0x02014b50) break
    const method = buf.readUInt16LE(at + 10)
    const compressed = buf.readUInt32LE(at + 20)
    const nameLen = buf.readUInt16LE(at + 28)
    const extraLen = buf.readUInt16LE(at + 30)
    const commentLen = buf.readUInt16LE(at + 32)
    const localAt = buf.readUInt32LE(at + 42)
    const name = buf.subarray(at + 46, at + 46 + nameLen).toString('utf8')

    // 로컬 헤더의 이름·여분 길이는 중앙 목록의 것과 다를 수 있다 — 여기서 다시 읽는다
    if (buf.readUInt32LE(localAt) === 0x04034b50) {
      const lNameLen = buf.readUInt16LE(localAt + 26)
      const lExtraLen = buf.readUInt16LE(localAt + 28)
      const start = localAt + 30 + lNameLen + lExtraLen
      const raw = buf.subarray(start, start + compressed)
      try {
        files.set(name, method === 0 ? Buffer.from(raw) : inflateRawSync(raw))
      } catch {
        /* 못 푸는 칸은 건너뛴다 — 우리가 보는 두 장만 있으면 된다 */
      }
    }
    at += 46 + nameLen + extraLen + commentLen
  }
  return files
}

/** 뒤에서부터 "끝 표시"(EOCD) 를 찾는다. 주석이 붙어 있어도 찾히게 한다 */
function findEocd(buf: Buffer): number {
  for (let i = buf.length - 22; i >= 0 && i > buf.length - 22 - 65_536; i -= 1) {
    if (buf.readUInt32LE(i) === 0x06054b50) return i
  }
  return -1
}

const ENTITIES: Record<string, string> = {
  '&amp;': '&',
  '&lt;': '<',
  '&gt;': '>',
  '&quot;': '"',
  '&apos;': "'",
}

function unescapeXml(v: string): string {
  return v
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, n) => String.fromCodePoint(parseInt(n, 16)))
    .replace(/&(amp|lt|gt|quot|apos);/g, (m) => ENTITIES[m] ?? m)
}

/** sharedStrings.xml → 글자 목록. <si> 하나에 <t> 가 여러 개일 수 있다(서식이 섞인 칸) */
export function sharedStrings(xml: string): string[] {
  const out: string[] = []
  for (const si of xml.match(/<si\b[\s\S]*?<\/si>/g) ?? []) {
    const parts = [...si.matchAll(/<t\b[^>]*>([\s\S]*?)<\/t>/g)].map((m) => unescapeXml(m[1]))
    out.push(parts.join(''))
  }
  return out
}

/** "BC12" → 열 번호 (0부터) */
export function columnIndex(ref: string): number {
  const letters = ref.replace(/[^A-Z]/gi, '').toUpperCase()
  let n = 0
  for (const ch of letters) n = n * 26 + (ch.charCodeAt(0) - 64)
  return Math.max(0, n - 1)
}

/**
 * 엑셀이 시간처럼 저장해 둔 값을 되돌린다.
 *
 * 원장님이 소요시간 칸에 `3:30` 을 치시면 엑셀은 그것을 **하루의 일부**(0.00243)
 * 로 저장한다. 그대로 읽으면 "0.0024" 가 명단에 들어간다. 하루를 초로 되돌려
 * `분:초` 로 적어 준다. 하루의 5% (72분) 안쪽인 소수만 시간으로 본다 —
 * 연주회에서 72분짜리 한 곡은 없고, 정수는 사람이 적은 숫자다.
 */
export function excelTimeToText(v: number): string | null {
  if (!Number.isFinite(v) || v <= 0 || v >= 0.05 || Number.isInteger(v)) return null
  const total = Math.round(v * 86_400)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

/** sheet1.xml → 줄별 칸 값 */
export function sheetRows(xml: string, strings: string[]): string[][] {
  const rows: string[][] = []
  for (const rowXml of xml.match(/<row\b[\s\S]*?(?:\/>|<\/row>)/g) ?? []) {
    const cells: string[] = []
    for (const cellXml of rowXml.match(/<c\b[\s\S]*?(?:\/>|<\/c>)/g) ?? []) {
      const ref = cellXml.match(/\sr="([A-Z]+\d+)"/)?.[1] ?? ''
      const type = cellXml.match(/\st="([^"]+)"/)?.[1] ?? 'n'
      const at = ref ? columnIndex(ref) : cells.length
      let value = ''

      if (type === 'inlineStr') {
        value = [...cellXml.matchAll(/<t\b[^>]*>([\s\S]*?)<\/t>/g)].map((m) => unescapeXml(m[1])).join('')
      } else {
        const raw = cellXml.match(/<v>([\s\S]*?)<\/v>/)?.[1] ?? ''
        if (type === 's') value = strings[Number(raw)] ?? ''
        else if (raw) {
          const num = Number(raw)
          value = Number.isFinite(num) ? (excelTimeToText(num) ?? raw) : unescapeXml(raw)
        }
      }

      while (cells.length < at) cells.push('')
      cells[at] = value.trim()
    }
    rows.push(cells)
  }
  return rows
}

/** 첫 장의 이름 — 워크북에 적힌 순서를 따른다. 없으면 sheet1 */
function firstSheetPath(files: Map<string, Buffer>): string {
  const names = [...files.keys()].filter((n) => /^xl\/worksheets\/sheet\d+\.xml$/.test(n))
  if (names.length === 0) return 'xl/worksheets/sheet1.xml'
  // sheet10 이 sheet2 앞에 오지 않게 숫자로 센다
  names.sort((a, b) => Number(a.match(/(\d+)/)![1]) - Number(b.match(/(\d+)/)![1]))
  return names[0]
}

/** .xlsx 바이트 → 줄별 칸 값 */
export function xlsxRows(buf: Buffer): string[][] {
  const files = unzip(buf)
  const sheet = files.get(firstSheetPath(files))
  if (!sheet) throw new Error('엑셀 안에서 표를 찾지 못했습니다.')
  const strings = files.has('xl/sharedStrings.xml')
    ? sharedStrings(files.get('xl/sharedStrings.xml')!.toString('utf8'))
    : []
  return sheetRows(sheet.toString('utf8'), strings)
}

/**
 * .xlsx → 붙여넣기 칸에 그대로 들어가는 글.
 *
 * 일부러 TSV(탭으로 나눈 표) 로 돌려준다. 엑셀에서 복사해 붙여넣으신 것과
 * **똑같은 모양**이라, 읽는 길이 하나로 남는다. 길이 둘이면 언젠가 갈라진다.
 */
export function xlsxToText(buf: Buffer): string {
  return xlsxRows(buf)
    .map((cells) => cells.join('\t').replace(/\t+$/, ''))
    .filter((line) => line.trim().length > 0)
    .join('\n')
}
