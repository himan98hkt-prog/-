#!/usr/bin/env node
// 퍼널모아(워드프레스)에 올릴 플러그인 zip 을 만든다.
//   node scripts/build-plugin.mjs  →  dist-plugin/academy-note-keys.zip
//
// 워드프레스의 "플러그인 업로드" 는 zip 안에 플러그인 폴더가 한 겹 들어 있어야 한다.
// 외부 도구에 기대지 않도록 zip 형식을 직접 쓴다(파일 몇 개뿐이라 충분하다).

import { readdirSync, readFileSync, statSync, mkdirSync, writeFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { deflateRawSync } from 'node:zlib'

const SRC = 'integration/funnelmoa/academy-note-keys'
const OUT_DIR = 'dist-plugin'
const OUT = join(OUT_DIR, 'academy-note-keys.zip')
const ROOT_IN_ZIP = 'academy-note-keys'

const files = walk(SRC).sort()
const version = /Version:\s*([\d.]+)/.exec(readFileSync(join(SRC, 'academy-note-keys.php'), 'utf8'))?.[1] || '0'

mkdirSync(OUT_DIR, { recursive: true })
writeFileSync(OUT, zip(files.map((f) => ({
  name: `${ROOT_IN_ZIP}/${relative(SRC, f).split('\\').join('/')}`,
  data: readFileSync(f)
}))))

console.log(`플러그인 ${version} — 파일 ${files.length}개 → ${OUT} (${(statSync(OUT).size / 1024).toFixed(1)} KB)`)

function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(join(dir, e.name)) : [join(dir, e.name)])
}

function zip(entries) {
  const local = []
  const central = []
  let offset = 0
  // 날짜는 빌드 시각으로 — 워드프레스는 이 값을 쓰지 않지만 0 이면 1980년으로 보인다
  const now = new Date()
  const time = (now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1)
  const date = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate()

  for (const { name, data } of entries) {
    const nameBuf = Buffer.from(name, 'utf8')
    const body = deflateRawSync(data, { level: 9 })
    const crc = crc32(data)

    const head = Buffer.alloc(30)
    head.writeUInt32LE(0x04034b50, 0)
    head.writeUInt16LE(20, 4)          // 풀 때 필요한 버전
    head.writeUInt16LE(0x0800, 6)      // 파일 이름이 UTF-8
    head.writeUInt16LE(8, 8)           // deflate
    head.writeUInt16LE(time, 10)
    head.writeUInt16LE(date, 12)
    head.writeUInt32LE(crc, 14)
    head.writeUInt32LE(body.length, 18)
    head.writeUInt32LE(data.length, 22)
    head.writeUInt16LE(nameBuf.length, 26)
    local.push(head, nameBuf, body)

    const cen = Buffer.alloc(46)
    cen.writeUInt32LE(0x02014b50, 0)
    cen.writeUInt16LE(20, 4)
    cen.writeUInt16LE(20, 6)
    cen.writeUInt16LE(0x0800, 8)
    cen.writeUInt16LE(8, 10)
    cen.writeUInt16LE(time, 12)
    cen.writeUInt16LE(date, 14)
    cen.writeUInt32LE(crc, 16)
    cen.writeUInt32LE(body.length, 20)
    cen.writeUInt32LE(data.length, 24)
    cen.writeUInt16LE(nameBuf.length, 28)
    cen.writeUInt32LE((0o100644 << 16) >>> 0, 38) // 일반 파일 권한
    cen.writeUInt32LE(offset, 42)
    central.push(cen, nameBuf)

    offset += head.length + nameBuf.length + body.length
  }

  const centralBuf = Buffer.concat(central)
  const end = Buffer.alloc(22)
  end.writeUInt32LE(0x06054b50, 0)
  end.writeUInt16LE(entries.length, 8)
  end.writeUInt16LE(entries.length, 10)
  end.writeUInt32LE(centralBuf.length, 12)
  end.writeUInt32LE(offset, 16)
  return Buffer.concat([...local, centralBuf, end])
}

function crc32(buf) {
  let c = ~0
  for (let i = 0; i < buf.length; i++) {
    c ^= buf[i]
    for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1))
  }
  return ~c >>> 0
}
