#!/usr/bin/env node
// 성능 테스트 러너 — 개발지시서 3.4 "원생 1,000명 · 반 80개 · 출결 20만 건에서 모든 화면 1초 내 렌더"를
// 실제 브라우저(Chromium + 실제 IndexedDB)에서 검증한다.
//
//   node scripts/perf.mjs                 기본(1000/80/200000)
//   node scripts/perf.mjs --students 300 --attendance 50000
//   node scripts/perf.mjs --keep          측정 후 브라우저 유지(디버깅)

import { spawn } from 'node:child_process'
import { writeFileSync, existsSync, readdirSync } from 'node:fs'
import { chromium } from 'playwright'

const args = process.argv.slice(2)
const opt = (name, def) => {
  const i = args.indexOf(`--${name}`)
  return i >= 0 ? Number(args[i + 1]) : def
}
const SEED = {
  students: opt('students', 1000),
  classes: opt('classes', 80),
  attendance: opt('attendance', 200000),
  months: opt('months', 12)
}
const BUDGET_MS = opt('budget', 1000)
const PORT = opt('port', 5199)
const VIEWS = ['attendance', 'students', 'payments', 'timetable', 'counsel', 'expenses', 'dashboard', 'settings']

const server = spawn('npx', ['vite', '--port', String(PORT), '--strictPort'], { stdio: ['ignore', 'pipe', 'pipe'] })
const kill = () => { try { server.kill('SIGTERM') } catch {} }
process.on('exit', kill)
process.on('SIGINT', () => { kill(); process.exit(130) })

await waitForServer(`http://localhost:${PORT}/lite.html`, 30000)

// 이 환경에는 Chromium 이 미리 설치돼 있다(PLAYWRIGHT_BROWSERS_PATH). 버전이 다르면 경로로 직접 지정한다.
const browser = await chromium.launch(chromeExecutable() ? { executablePath: chromeExecutable() } : {})
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
page.on('console', (m) => { if (m.type() === 'error') console.error('  [browser]', m.text()) })
page.setDefaultTimeout(600000)

console.log(`\n▶ 더미 데이터 생성: 원생 ${SEED.students} / 반 ${SEED.classes} / 출결 ${SEED.attendance.toLocaleString('en-US')}`)
await page.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'domcontentloaded' })

const seedMs = await page.evaluate(async (seed) => {
  const { seedBulk } = await import('/src/data/seed.js')
  const t0 = performance.now()
  await seedBulk(seed)
  return Math.round(performance.now() - t0)
}, SEED)
console.log(`  생성 완료 (${(seedMs / 1000).toFixed(1)}s)\n`)

// 시드 후 새 세션으로 앱을 다시 띄운다 (실사용과 같은 콜드 스타트)
await page.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'load' })
await page.waitForSelector('.app-nav button', { timeout: 60000 })

const rows = []

// 1) 콜드 스타트(앱 부팅 → 첫 화면)
rows.push({ name: '앱 콜드 스타트(부팅+첫 화면)', ms: await page.evaluate(() => {
  const nav = performance.getEntriesByType('navigation')[0]
  return Math.round(performance.now() - (nav?.responseStart || 0))
}) })

// 2) 각 탭 렌더 시간 (실제 mount → 페인트까지)
for (const view of VIEWS) {
  const ms = await page.evaluate(async (v) => {
    const { mount } = await import('/src/ui/shell.js')
    const t0 = performance.now()
    await mount(v)
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))
    return Math.round(performance.now() - t0)
  }, view)
  rows.push({ name: `${view} 탭 렌더`, ms })
}

// 3) 원생 검색 응답(입력 → 목록 갱신)
rows.push({
  name: '원생 검색 100회(디바운스 제외 순수 필터)',
  ms: await page.evaluate(async () => {
    const repo = await import('/src/data/repo.js')
    const t0 = performance.now()
    for (let i = 0; i < 100; i++) repo.searchStudents(String(i % 10), { status: '재원' })
    return Math.round(performance.now() - t0)
  })
})

// 4) 데이터 계층 상세 (perf.js)
const dataRows = await page.evaluate(async () => {
  const { measure } = await import('/src/data/perf.js')
  return measure()
})
rows.push(...dataRows.filter((r) => r.ms > 0).map((r) => ({ name: `데이터: ${r.name}`, ms: r.ms })))
const scale = dataRows.find((r) => r.ms === 0)?.name || ''

const failed = rows.filter((r) => r.ms > BUDGET_MS)
console.log(`─ 결과 (기준 ${BUDGET_MS}ms) ${'─'.repeat(30)}`)
for (const r of rows) console.log(`  ${r.ms > BUDGET_MS ? '❌' : '✅'} ${String(r.ms).padStart(6)}ms  ${r.name}`)
console.log(`─${'─'.repeat(48)}`)
console.log(`  ${scale}`)
console.log(`  ${failed.length ? `${failed.length}개 항목이 기준을 넘었습니다` : '전 항목 기준 통과'}\n`)

writeFileSync('perf-report.json', JSON.stringify({
  ranAt: new Date().toISOString(), seed: SEED, budgetMs: BUDGET_MS, seedMs, scale, rows, pass: !failed.length
}, null, 2))
console.log('  상세 결과: perf-report.json')

if (!args.includes('--keep')) await browser.close()
kill()
process.exit(failed.length ? 1 : 0)

function chromeExecutable() {
  const explicit = process.env.CHROMIUM_PATH
  if (explicit && existsSync(explicit)) return explicit
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH
  if (!root || !existsSync(root)) return null
  const dir = readdirSync(root).filter((d) => /^chromium-\d+$/.test(d)).sort().pop()
  if (!dir) return null
  const bin = `${root}/${dir}/chrome-linux/chrome`
  return existsSync(bin) ? bin : null
}

async function waitForServer(url, timeoutMs) {
  const until = Date.now() + timeoutMs
  for (;;) {
    try {
      const res = await fetch(url)
      if (res.ok) return
    } catch {}
    if (Date.now() > until) throw new Error(`개발 서버가 뜨지 않았습니다: ${url}`)
    await new Promise((r) => setTimeout(r, 300))
  }
}
