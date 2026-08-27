/**
 * 압축하지 않는 ZIP 묶기 (stored, method 0).
 *
 * pptx 는 ZIP 파일이다. 파워포인트는 압축하지 않은 ZIP 도 그대로 연다.
 * 슬라이드는 전부 짧은 XML 이라 압축해도 몇십 KB 차이라, 외부 라이브러리를
 * 하나 더 들이는 대신 직접 쓴다 — 원장님 컴퓨터에서 인터넷 없이 돌아야 하므로
 * 의존성은 적을수록 좋다.
 */

const CRC_TABLE = (() => {
  const table = new Uint32Array(256)
  for (let i = 0; i < 256; i += 1) {
    let c = i
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    table[i] = c >>> 0
  }
  return table
})()

function crc32(bytes: Uint8Array): number {
  let c = 0xffffffff
  for (let i = 0; i < bytes.length; i += 1) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

export interface ZipEntry {
  name: string
  data: Uint8Array
}

/** 파일 목록 → ZIP 바이트 */
export function zipStore(entries: ZipEntry[]): Uint8Array {
  const encoder = new TextEncoder()
  const locals: Uint8Array[] = []
  const centrals: Uint8Array[] = []
  let offset = 0

  for (const entry of entries) {
    const name = encoder.encode(entry.name)
    const sum = crc32(entry.data)
    const size = entry.data.length

    const local = new Uint8Array(30 + name.length + size)
    const lv = new DataView(local.buffer)
    lv.setUint32(0, 0x04034b50, true) // 로컬 헤더 서명
    lv.setUint16(4, 20, true) // 필요한 버전
    lv.setUint16(6, 0x0800, true) // UTF-8 파일명
    lv.setUint16(8, 0, true) // 압축 없음
    lv.setUint16(10, 0, true) // 시각 — 결과가 매번 같아야 하므로 0 으로 고정
    lv.setUint16(12, 0x0021, true) // 날짜 1980-01-01
    lv.setUint32(14, sum, true)
    lv.setUint32(18, size, true)
    lv.setUint32(22, size, true)
    lv.setUint16(26, name.length, true)
    lv.setUint16(28, 0, true)
    local.set(name, 30)
    local.set(entry.data, 30 + name.length)
    locals.push(local)

    const central = new Uint8Array(46 + name.length)
    const cv = new DataView(central.buffer)
    cv.setUint32(0, 0x02014b50, true)
    cv.setUint16(4, 20, true) // 만든 버전
    cv.setUint16(6, 20, true)
    cv.setUint16(8, 0x0800, true)
    cv.setUint16(10, 0, true)
    cv.setUint16(12, 0, true)
    cv.setUint16(14, 0x0021, true)
    cv.setUint32(16, sum, true)
    cv.setUint32(20, size, true)
    cv.setUint32(24, size, true)
    cv.setUint16(28, name.length, true)
    cv.setUint32(42, offset, true)
    central.set(name, 46)
    centrals.push(central)

    offset += local.length
  }

  const centralSize = centrals.reduce((sum, part) => sum + part.length, 0)
  const end = new Uint8Array(22)
  const ev = new DataView(end.buffer)
  ev.setUint32(0, 0x06054b50, true)
  ev.setUint16(8, entries.length, true)
  ev.setUint16(10, entries.length, true)
  ev.setUint32(12, centralSize, true)
  ev.setUint32(16, offset, true)

  const total = offset + centralSize + end.length
  const out = new Uint8Array(total)
  let cursor = 0
  for (const part of [...locals, ...centrals, end]) {
    out.set(part, cursor)
    cursor += part.length
  }
  return out
}
