#!/usr/bin/env node
/**
 * 설치판에 담을 **프로그램 본체**를 한 폴더로 모은다.
 *
 * Next 의 standalone 출력은 서버와 필요한 꾸러미만 담고, 화면에 쓰는 정적 파일
 * (`.next/static`)과 `public` 은 일부러 빼 놓는다 — 웹에서는 그것들을 따로 얹기 때문이다.
 * 설치판은 그럴 데가 없으니 여기서 손으로 붙인다. 빠뜨리면 글씨만 나오고 그림이 다 깨진다.
 *
 *   npm run build && node scripts/build-desktop.mjs
 */
import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const ROOT = process.cwd()
const STANDALONE = join(ROOT, '.next', 'standalone')
const OUT = join(ROOT, 'desktop', 'app')

if (!existsSync(join(STANDALONE, 'server.js'))) {
  console.error('먼저 npm run build 를 하세요 (.next/standalone 이 없습니다).')
  process.exit(1)
}

rmSync(OUT, { recursive: true, force: true })
mkdirSync(OUT, { recursive: true })

// 1) 혼자 도는 서버 한 벌
cpSync(STANDALONE, OUT, { recursive: true })

// 2) 화면에 쓰는 정적 파일 — 빠지면 글씨만 나오고 그림이 다 깨진다
cpSync(join(ROOT, '.next', 'static'), join(OUT, '.next', 'static'), { recursive: true })

// 3) public — 설명서 그림, 체험판, 연습용 자료
if (existsSync(join(ROOT, 'public'))) cpSync(join(ROOT, 'public'), join(OUT, 'public'), { recursive: true })

// 4) 사용설명서 원본 (설명서 화면이 이 파일을 읽는다)
mkdirSync(join(OUT, 'docs'), { recursive: true })
cpSync(join(ROOT, 'docs', 'MANUAL.md'), join(OUT, 'docs', 'MANUAL.md'))

// 5) 설치판은 개발용 설정을 들고 다닐 이유가 없다
for (const junk of ['.env', '.env.local']) rmSync(join(OUT, junk), { force: true })

function folderSize(dir) {
  let total = 0
  const walk = (at) => {
    for (const name of readdirSync(at)) {
      const full = join(at, name)
      const s = statSync(full)
      if (s.isDirectory()) walk(full)
      else total += s.size
    }
  }
  walk(dir)
  return total
}

// 챙겨야 할 것이 실제로 들어갔는지 — 빠진 채로 설치본을 뽑으면 원장님 화면에서야 안다
const must = [
  ['server.js', '서버'],
  ['.next/static', '화면 파일'],
  ['public/manual', '설명서 그림'],
  ['docs/MANUAL.md', '사용설명서'],
  ['node_modules/next', 'Next 꾸러미'],
]
let missing = 0
for (const [rel, what] of must) {
  if (!existsSync(join(OUT, rel))) {
    console.error(`  ✗ ${what} 가 빠졌습니다 — ${rel}`)
    missing += 1
  }
}
if (missing > 0) process.exit(1)

const pkg = JSON.parse(readFileSync(join(OUT, 'package.json'), 'utf8'))
pkg.name = 'pianoevent-app'
writeFileSync(join(OUT, 'package.json'), `${JSON.stringify(pkg, null, 2)}\n`, 'utf8')

console.log(`설치판 본체 준비 완료 · desktop/app · ${Math.round(folderSize(OUT) / 1024 / 1024)}MB`)
