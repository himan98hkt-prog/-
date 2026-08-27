#!/usr/bin/env node
// 성능 테스트 러너 — 개발지시서 3.4 "원생 1,000명 · 반 80개 · 출결 20만 건에서 모든 화면 1초 내 렌더"를
// 실제 브라우저(Chromium + 실제 IndexedDB)에서 검증한다.
//
//   node scripts/perf.mjs                 기본(1000/80/200000)
//   node scripts/perf.mjs --students 300 --attendance 50000
//   node scripts/perf.mjs --keep          측정 후 브라우저 유지(디버깅)

import { spawn } from 'node:child_process'
import { writeFileSync, existsSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'
import { generateKey } from '../src/core/license.js'

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
// 배치(마감·집계 재계산)는 화면 렌더가 아니므로 별도 기준을 쓴다
const BATCH_BUDGET_MS = opt('batchBudget', 6000)
const SKIP_SEED = args.includes('--skip-seed')
// 프로필은 프로젝트 밖에 둔다 — 브라우저가 프로필에 쓰는 파일을 Vite 워처가 감지해
// 측정 도중 페이지를 리로드해 버리기 때문이다
const PROFILE_DIR = join(tmpdir(), 'academy-note-perf-profile')
const PORT = opt('port', 5199)
const VIEWS = ['today', 'attendance', 'students', 'payments', 'timetable', 'counsel', 'expenses', 'dashboard', 'settings']

// detached: npx 가 vite 를 자식으로 또 띄우기 때문에, 프로세스 그룹째 종료해야
// 측정이 끝난 뒤 dev 서버가 고아 프로세스로 남지 않는다
const server = spawn('npx', ['vite', '--port', String(PORT), '--strictPort'], { stdio: ['ignore', 'pipe', 'pipe'], detached: true })
const kill = () => { try { process.kill(-server.pid, 'SIGTERM') } catch {} }
process.on('exit', kill)
process.on('SIGINT', () => { kill(); process.exit(130) })

await waitForServer(`http://localhost:${PORT}/lite.html`, 30000)

// 이 환경에는 Chromium 이 미리 설치돼 있다(PLAYWRIGHT_BROWSERS_PATH). 버전이 다르면 경로로 직접 지정한다.
// 영속 프로필을 쓰면 IndexedDB 가 실행 간에 유지돼 --skip-seed 로 재측정이 가능하다
const context = await chromium.launchPersistentContext(PROFILE_DIR, {
  viewport: { width: 1280, height: 900 },
  ...(chromeExecutable() ? { executablePath: chromeExecutable() } : {})
})
const page = context.pages()[0] || await context.newPage()
page.on('console', (m) => { if (m.type() === 'error') console.error('  [browser]', m.text()) })
page.setDefaultTimeout(600000)

await page.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'domcontentloaded' })

const existing = await page.evaluate(async () => {
  const { db } = await import('/src/data/db.js')
  return { students: await db.students.count(), attendance: await db.attendance.count() }
})

let seedMs = 0
if (SKIP_SEED && existing.attendance > 0) {
  console.log(`\n▶ 기존 데이터 재사용: 원생 ${existing.students} / 출결 ${existing.attendance.toLocaleString('en-US')}`)
} else {
  console.log(`\n▶ 더미 데이터 생성: 원생 ${SEED.students} / 반 ${SEED.classes} / 출결 ${SEED.attendance.toLocaleString('en-US')} (수 분 걸립니다)`)
  seedMs = await page.evaluate(async (seed) => {
    const { seedBulk } = await import('/src/data/seed.js')
    const t0 = performance.now()
    await seedBulk(seed)
    return Math.round(performance.now() - t0)
  }, SEED)
  console.log(`  생성 완료 (${(seedMs / 1000).toFixed(1)}s)`)
}

// 인증키 게이트와 PIN 로그인은 측정 대상이 아니므로 미리 통과시켜 둔다
// (키는 앱과 같은 모듈로 발급한 Lite 통합키 — 실제 고객 상태와 동일하다)
const perfKey = generateKey('lite', 'A')
await page.evaluate(async (key) => {
  const { db } = await import('/src/data/db.js')
  const { verifyKey, hashKey } = await import('/src/core/license.js')
  const res = verifyKey(key)
  await db.settings.put({
    key: 'license',
    value: { key: res.key, key_hash: hashKey(res.key), plan: res.plan, product: res.product, activated_at: new Date().toISOString() }
  })
  await db.settings.put({ key: 'wizardDone', value: true })
  const owner = (await db.users.toArray()).find((u) => u.role === 'owner')
  if (owner) {
    const payload = JSON.stringify({ userId: owner.id, at: Date.now() })
    localStorage.setItem('academy-note:session', payload)
    sessionStorage.setItem('academy-note:session', payload)
  }
}, perfKey)
console.log('')

// 시드 후 새 세션으로 앱을 다시 띄운다 (실사용과 같은 콜드 스타트)
await page.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'load' })
await page.waitForSelector('.app-rail button, .app-nav button', { timeout: 120000 })

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

// 2-b) 최악의 경우: 집계 캐시가 하나도 없는 상태의 현황 탭
rows.push({
  name: 'dashboard 탭 렌더(집계 캐시 없음)',
  ms: await page.evaluate(async () => {
    const { db } = await import('/src/data/db.js')
    await db.monthlyStats.clear()
    const { mount } = await import('/src/ui/shell.js')
    await mount('attendance')
    const t0 = performance.now()
    await mount('dashboard')
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))
    return Math.round(performance.now() - t0)
  })
})

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

const budgetOf = (r) => (r.name.includes('배치:') ? BATCH_BUDGET_MS : BUDGET_MS)
const failed = rows.filter((r) => r.ms > budgetOf(r))
console.log(`─ 결과 (화면 기준 ${BUDGET_MS}ms · 배치 기준 ${BATCH_BUDGET_MS}ms) ${'─'.repeat(12)}`)
for (const r of rows) console.log(`  ${r.ms > budgetOf(r) ? '❌' : '✅'} ${String(r.ms).padStart(6)}ms  ${r.name}`)
console.log(`─${'─'.repeat(48)}`)
console.log(`  ${scale}`)
console.log(`  ${failed.length ? `${failed.length}개 항목이 기준을 넘었습니다` : '전 항목 기준 통과'}\n`)

writeFileSync('perf-report.json', JSON.stringify({
  ranAt: new Date().toISOString(), seed: SEED, budgetMs: BUDGET_MS, batchBudgetMs: BATCH_BUDGET_MS, seedMs, scale,
  rows: rows.map((r) => ({ ...r, budgetMs: budgetOf(r), pass: r.ms <= budgetOf(r) })), pass: !failed.length
}, null, 2))
console.log('  상세 결과: perf-report.json')

if (!args.includes('--keep')) await context.close()
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
