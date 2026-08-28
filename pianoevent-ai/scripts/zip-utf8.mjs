/**
 * 한글 이름이 깨지지 않는 ZIP 쓰기.
 *
 * 왜 직접 쓰는가.
 * 리눅스의 `zip` 명령은 파일 이름을 UTF-8 바이트로 넣으면서 **"이건 UTF-8 이다"
 * 라는 표시(일반 목적 비트 11번, 0x0800)를 켜 주지 않는다.** 그러면 윈도우 탐색기는
 * 그 바이트를 한국어 옛 코드페이지(CP949)로 읽으려다 실패한다.
 * 원장님 화면에서는 **"압축을 풀었는데 아무것도 없다"** 로 나타난다.
 *
 * 파일 이름이 전부 한글인 묶음이라 이 표시 하나가 묶음 전체를 못 쓰게 만든다.
 * 그래서 헤더를 직접 쓴다 — 표시를 켜는 것 말고는 평범한 ZIP 이다.
 */
import { open, readFile, readdir } from 'node:fs/promises'
import path from 'node:path'
import { deflateRawSync } from 'node:zlib'

const UTF8_FLAG = 0x0800
const DEFLATE = 8
const STORE = 0

const CRC_TABLE = (() => {
  const table = new Uint32Array(256)
  for (let i = 0; i < 256; i += 1) {
    let c = i
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    table[i] = c >>> 0
  }
  return table
})()

function crc32(buf) {
  let c = 0xffffffff
  for (let i = 0; i < buf.length; i += 1) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

/** 시각은 고정한다 — 같은 소스에서 같은 묶음이 나와야 무엇이 바뀌었는지 알 수 있다 */
const DOS_TIME = 0
const DOS_DATE = 0x0021 // 1980-01-01

/** 폴더 안의 모든 파일을 ZIP 안에서 쓸 경로와 함께 모은다 */
async function walk(dir, prefix = '') {
  const out = []
  for (const entry of (await readdir(dir, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
    const full = path.join(dir, entry.name)
    // ZIP 안의 경로 구분자는 늘 `/` 다. 윈도우에서 만들어도 마찬가지다.
    const inside = prefix ? `${prefix}/${entry.name}` : entry.name
    if (entry.isDirectory()) {
      out.push({ name: `${inside}/`, dir: true })
      out.push(...(await walk(full, inside)))
    } else if (entry.isFile()) {
      out.push({ name: inside, path: full, dir: false })
    }
  }
  return out
}

/**
 * `root` 안의 모든 것을 `out` 으로 묶는다.
 * 이름은 전부 UTF-8 로 넣고 **표시를 켠다.**
 */
export async function zipFolder(root, out) {
  const items = await walk(root)
  const locals = []
  const centrals = []
  let offset = 0

  for (const item of items) {
    const name = Buffer.from(item.name, 'utf8')
    const raw = item.dir ? Buffer.alloc(0) : await readFile(item.path)
    const sum = item.dir ? 0 : crc32(raw)

    // 이미 압축된 것(jpg·zip 등)을 다시 압축하면 오히려 커진다 — 그럴 땐 그대로 담는다
    let method = STORE
    let data = raw
    if (!item.dir && raw.length > 0) {
      const packed = deflateRawSync(raw, { level: 9 })
      if (packed.length < raw.length) {
        method = DEFLATE
        data = packed
      }
    }

    const local = Buffer.alloc(30 + name.length)
    local.writeUInt32LE(0x04034b50, 0)
    local.writeUInt16LE(20, 4)
    local.writeUInt16LE(UTF8_FLAG, 6) // ← 이 한 줄이 없어서 한글이 깨졌다
    local.writeUInt16LE(method, 8)
    local.writeUInt16LE(DOS_TIME, 10)
    local.writeUInt16LE(DOS_DATE, 12)
    local.writeUInt32LE(sum, 14)
    local.writeUInt32LE(data.length, 18)
    local.writeUInt32LE(raw.length, 22)
    local.writeUInt16LE(name.length, 26)
    local.writeUInt16LE(0, 28)
    name.copy(local, 30)

    const central = Buffer.alloc(46 + name.length)
    central.writeUInt32LE(0x02014b50, 0)
    central.writeUInt16LE(0x031e, 4) // 만든 곳: 유닉스
    central.writeUInt16LE(20, 6)
    central.writeUInt16LE(UTF8_FLAG, 8)
    central.writeUInt16LE(method, 10)
    central.writeUInt16LE(DOS_TIME, 12)
    central.writeUInt16LE(DOS_DATE, 14)
    central.writeUInt32LE(sum, 16)
    central.writeUInt32LE(data.length, 20)
    central.writeUInt32LE(raw.length, 24)
    central.writeUInt16LE(name.length, 28)
    central.writeUInt16LE(0, 30)
    central.writeUInt16LE(0, 32)
    central.writeUInt16LE(0, 34)
    central.writeUInt16LE(0, 36)
    // 바깥 속성 — 폴더는 폴더로, 파일은 읽기 가능하게. 맥에서 풀 때 권한이 이상해지지 않는다
    central.writeUInt32LE(item.dir ? 0x41ed0010 : 0x81a40000, 38)
    central.writeUInt32LE(offset, 42)
    name.copy(central, 46)

    locals.push(local, data)
    centrals.push(central)
    offset += local.length + data.length
  }

  const dir = Buffer.concat(centrals)
  const eocd = Buffer.alloc(22)
  eocd.writeUInt32LE(0x06054b50, 0)
  eocd.writeUInt16LE(0, 4)
  eocd.writeUInt16LE(0, 6)
  eocd.writeUInt16LE(items.length, 8)
  eocd.writeUInt16LE(items.length, 10)
  eocd.writeUInt32LE(dir.length, 12)
  eocd.writeUInt32LE(offset, 16)
  eocd.writeUInt16LE(0, 20)

  const file = await open(out, 'w')
  try {
    await file.writeFile(Buffer.concat([...locals, dir, eocd]))
  } finally {
    await file.close()
  }
  return items.filter((i) => !i.dir).length
}
