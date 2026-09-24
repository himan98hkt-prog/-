#!/usr/bin/env node
// 만들어진 설명서를 **브라우저로 실제로 열어 본다**.
//
//   npm run manual:verify        (dist/manual.html)
//   node scripts/manual-verify.mjs --file 다른곳.html
//
// `npm run manual` 안에도 검사가 있지만 그건 글자(HTML)를 보는 검사다.
// 여기서는 진짜로 그려지는지를 본다 — 그림이 정말 뜨는지, 목차를 누르면
// 정말 움직이는지, 인쇄하면 A4 로 제대로 나오는지. 릴리스 전에 한 번 돌린다.

import { existsSync, mkdirSync, statSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { chromium } from 'playwright'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..')
const args = process.argv.slice(2)
const argOf = (n, d) => { const i = args.indexOf(n); return i >= 0 && args[i + 1] ? args[i + 1] : d }

const FILE = resolve(ROOT, argOf('--file', 'dist/manual.html'))
const PDF = resolve(ROOT, argOf('--pdf', 'dist/manual.pdf'))

if (!existsSync(FILE)) {
  console.error(`설명서가 없습니다: ${FILE}\n  npm run manual  을 먼저 돌리세요`)
  process.exit(2)
}

const fail = []
const ok = (line) => console.log(`  ✓ ${line}`)
const no = (line) => { fail.push(line); console.log(`  ✗ ${line}`) }

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || undefined,
  args: ['--no-sandbox'],
})
try {
  const ctx = await browser.newContext({ viewport: { width: 1180, height: 950 } })
  const pg = await ctx.newPage()
  const errors = []
  pg.on('pageerror', (e) => errors.push(String(e)))

  await pg.goto(pathToFileURL(FILE).href, { waitUntil: 'load', timeout: 120_000 })
  await pg.waitForSelector('main section', { timeout: 60_000 })

  const n = await pg.evaluate(() => ({
    parts: document.querySelectorAll('.part').length,
    chapters: document.querySelectorAll('main h2').length,
    sections: document.querySelectorAll('main section').length,
    figures: document.querySelectorAll('figure img').length,
    traps: document.querySelectorAll('.trap').length,
    tables: document.querySelectorAll('main table').length,
    toc: document.querySelectorAll('nav a').length,
  }))
  console.log(`구조: ${n.parts}부 · ${n.chapters}장 · ${n.sections}절 · ` +
    `그림 ${n.figures} · 자주하는실수 ${n.traps} · 표 ${n.tables} · 목차 ${n.toc}`)

  // 그림이 실제로 그려졌는가. naturalWidth 가 0 이면 자리만 있고 그림은 없는 것이다.
  // (`loading="lazy"` 가 붙어 있으면 여기서 영영 안 끝난다 — 그래서 빌더가 막는다.)
  const blank = await pg.evaluate(() => [...document.querySelectorAll('figure img')]
    .filter((i) => !i.complete || !i.naturalWidth).length)
  blank ? no(`안 뜬 그림 ${blank}장`) : ok(`그림 ${n.figures}장이 모두 떴다`)

  // 목차를 눌러 정말 그 장으로 가는가
  const target = await pg.getAttribute('nav ul ul a', 'href')
  await pg.click(`nav a[href="${target}"]`)
  await pg.waitForTimeout(400)
  const top = await pg.evaluate((h) =>
    document.querySelector(h).getBoundingClientRect().top, target)
  Math.abs(top) < 200
    ? ok(`목차를 누르니 ${target} 으로 이동 (${Math.round(top)}px)`)
    : no(`목차를 눌러도 안 움직인다: ${target} 이 ${Math.round(top)}px`)

  // 인쇄 — 목차 사이드바는 종이에 안 나와야 하고, A4 로 뽑혀야 한다
  await pg.emulateMedia({ media: 'print' })
  const nav = await pg.evaluate(() => getComputedStyle(document.querySelector('nav')).display)
  nav === 'none' ? ok('인쇄하면 목차 사이드바가 빠진다')
    : no(`인쇄할 때도 목차가 남는다 (display:${nav})`)

  mkdirSync(dirname(PDF), { recursive: true })
  await pg.pdf({ path: PDF, format: 'A4', printBackground: true,
    margin: { top: '16mm', bottom: '16mm', left: '14mm', right: '14mm' } })
  const kb = statSync(PDF).size / 1024
  kb > 200 ? ok(`A4 로 인쇄됨 — ${PDF} (${kb.toFixed(0)} KB)`)
    : no(`인쇄물이 너무 작다 (${kb.toFixed(0)} KB) — 그림이 빠졌을 수 있다`)

  errors.length ? no(`문서에서 오류가 났다: ${errors.join(' / ')}`)
    : ok('문서를 여는 동안 오류 없음')
} finally {
  await browser.close()
}

if (fail.length) {
  console.error(`\n${fail.length}가지가 걸렸습니다.`)
  process.exit(1)
}
console.log('\n설명서를 브라우저에서 확인했습니다.')
