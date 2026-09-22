#!/usr/bin/env node
// 관리노트와 반주 플레이어가 **같이 쓰는 파일**을 맞춘다.
//
//   npm run sync:shared          맞춘다
//   npm run sync:shared -- --check   다른지만 본다 (CI·테스트가 쓴다)
//
// 왜 사본인가: 플레이어는 정적 꾸러미로 따로 배포돼서 관리노트 소스를 불러올 수 없다.
// 왜 손으로 안 맞추는가: 형식을 한쪽에서만 고치면 **원장님 쪽에서 파일이 안 읽힌다.**
// 그런 고장은 우리 화면에서 안 보이고 현장에서만 보인다.

import { copyFileSync, mkdirSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

/** [원본, 사본] — 사본은 원본의 글자 그대로여야 한다. */
export const SHARED = [
  ['src/core/practice-piano.js', 'mr/server/static/player/js/practice-format.js'],
]

export function differences() {
  return SHARED.filter(([from, to]) => {
    let a, b
    try { a = readFileSync(resolve(ROOT, from), 'utf8') } catch { return true }
    try { b = readFileSync(resolve(ROOT, to), 'utf8') } catch { return true }
    return a !== b
  })
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const check = process.argv.includes('--check')
  const bad = differences()
  if (!bad.length) {
    console.log(`같이 쓰는 파일 ${SHARED.length}개 — 맞습니다.`)
    process.exit(0)
  }
  if (check) {
    console.error('같이 쓰는 파일이 어긋났습니다:')
    for (const [from, to] of bad) console.error(`  · ${from}\n    ≠ ${to}`)
    console.error('\n  npm run sync:shared   로 맞추세요.')
    process.exit(1)
  }
  for (const [from, to] of bad) {
    mkdirSync(dirname(resolve(ROOT, to)), { recursive: true })
    copyFileSync(resolve(ROOT, from), resolve(ROOT, to))
    console.log(`  ${from} → ${to}`)
  }
  console.log(`${bad.length}개를 맞췄습니다.`)
}
