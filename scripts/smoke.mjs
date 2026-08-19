#!/usr/bin/env node
// 실사용 시나리오 스모크 테스트 — 완료 기준(DoD) 2·3·5·6번을 실제 브라우저에서 확인한다.
//
//   2) 계열이 다른 학원 2곳(영어학원/태권도장)을 custom 필드만 바꿔 운영
//   3) 로고·학원명·컬러 변경이 헤더/리포트/설치 아이콘에 반영
//   5) 백업 → 초기화 → 복원 왕복
//   6) 라이선스 키 발급 → 입력 → 플랜 활성화

import { spawn } from 'node:child_process'
import { existsSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'

const PORT = 5198
const PROFILE_DIR = join(tmpdir(), 'academy-note-smoke-profile')
const results = []

const server = spawn('npx', ['vite', '--port', String(PORT), '--strictPort'], { stdio: ['ignore', 'pipe', 'pipe'] })
const kill = () => { try { server.kill('SIGTERM') } catch {} }
process.on('exit', kill)

await waitForServer(`http://localhost:${PORT}/lite.html`, 30000)
const context = await chromium.launchPersistentContext(PROFILE_DIR, {
  viewport: { width: 1280, height: 900 },
  ...(chromeExecutable() ? { executablePath: chromeExecutable() } : {})
})
const page = context.pages()[0] || await context.newPage()
page.setDefaultTimeout(60000)
page.on('pageerror', (e) => console.error('  [page error]', e.message))

await page.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'domcontentloaded' })

// ── 1. 영어학원 시나리오 ────────────────────────────────────
await seed('english')
await reload()
let info = await snapshot()
check('영어학원: 헤더에 학원명 반영', info.headerTitle === '아라 잉글리시')
check('영어학원: 브랜드 컬러가 CSS 변수에 반영', info.brand === '#2563eb')
check('영어학원: custom 필드는 어학 세트', info.fieldKeys.join() === 'level,level_test,book')
check('영어학원: 원생 목록 렌더', info.students > 0)

// 출결 체크(첫 원생 탭)
await page.click('.app-nav button[data-view="attendance"]')
await page.waitForSelector('.att-cell')
const before = await page.getAttribute('.att-cell', 'data-status')
await page.click('.att-cell')
await page.waitForFunction((b) => document.querySelector('.att-cell')?.dataset.status !== b, before)
check('출결: 탭 한 번으로 상태가 바뀐다', (await page.getAttribute('.att-cell', 'data-status')) !== before)

// 리포트 이미지 생성
const report = await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  const { drawReportCard } = await import('/src/ui/report.js')
  const { summarize } = await import('/src/core/attendance.js')
  const { displayPairs } = await import('/src/core/customfields.js')
  const s = repo.cache.students[0]
  const att = await repo.attendanceOfStudentRange(s.id, '2000-01-01', '2100-01-01')
  const canvas = await drawReportCard({
    student: s, month: '2026-08', attendance: summarize(att),
    payment: { amount: 180000, status: '완납' },
    customPairs: displayPairs(repo.getSetting('customFields', []), s.custom, 'report'),
    comment: '이번 달 수업 태도가 좋았습니다.', teacherName: '김강사'
  })
  return { w: canvas.width, h: canvas.height, bytes: canvas.toDataURL('image/png').length }
})
check('리포트: Canvas 이미지 생성', report.w === 760 && report.h === 1180 && report.bytes > 20000)

// ── 2. 브랜딩 변경 반영 ─────────────────────────────────────
const branded = await page.evaluate(async () => {
  const { saveBranding } = await import('/src/ui/branding.js')
  await saveBranding({ name: '테스트 학원', brand_color: '#dc2626' })
  const manifestHref = document.querySelector('link[rel=manifest]')?.href || ''
  const manifest = manifestHref.startsWith('blob:') ? await (await fetch(manifestHref)).json() : null
  return {
    header: document.querySelector('.app-header .title')?.textContent,
    brand: getComputedStyle(document.documentElement).getPropertyValue('--brand').trim(),
    title: document.title,
    manifestName: manifest?.name,
    manifestColor: manifest?.theme_color,
    iconIsPng: (manifest?.icons?.[0]?.src || '').startsWith('data:image/png')
  }
})
check('브랜딩: 헤더 학원명 변경', branded.header === '테스트 학원')
check('브랜딩: --brand CSS 변수 변경', branded.brand === '#dc2626')
check('브랜딩: 문서 제목 변경', branded.title === '테스트 학원')
check('브랜딩: 동적 manifest 에 학원명·컬러 반영', branded.manifestName === '테스트 학원' && branded.manifestColor === '#dc2626')
check('브랜딩: 로고 미업로드 시 이니셜 아이콘 생성', branded.iconIsPng)

// ── 3. 백업 → 초기화 → 복원 ────────────────────────────────
const roundTrip = await page.evaluate(async () => {
  const { db } = await import('/src/data/db.js')
  const { buildBackup, parseBackup, BACKUP_TABLES } = await import('/src/core/backup.js')
  const tables = {}
  for (const t of BACKUP_TABLES) tables[t] = db[t] ? await db[t].toArray() : []
  const json = JSON.stringify(buildBackup(tables, { plan: 'lite', academy: '테스트 학원' }))
  const beforeCounts = { students: tables.students.length, attendance: tables.attendance.length }

  await db.transaction('rw', db.tables, async () => { await Promise.all(db.tables.map((t) => t.clear())) })
  const emptied = await db.students.count()

  const backup = parseBackup(json)
  await db.transaction('rw', db.tables, async () => {
    for (const t of BACKUP_TABLES) {
      if (!db[t]) continue
      await db[t].clear()
      if (backup.data[t].length) await db[t].bulkPut(backup.data[t])
    }
  })
  return { beforeCounts, emptied, after: { students: await db.students.count(), attendance: await db.attendance.count() } }
})
check('백업: 초기화 후 복원으로 원생/출결이 그대로 돌아온다',
  roundTrip.emptied === 0 &&
  roundTrip.after.students === roundTrip.beforeCounts.students &&
  roundTrip.after.attendance === roundTrip.beforeCounts.attendance)

// ── 4. 라이선스 발급 → 입력 → 플랜 활성화 ───────────────────
const license = await page.evaluate(async () => {
  const { generateKey, verifyKey, hashKey } = await import('/src/core/license.js')
  const repo = await import('/src/data/repo.js')
  const key = generateKey('pro')
  const res = verifyKey(key)
  if (!res.ok) return { ok: false, reason: res.reason }
  await repo.setSetting('license', { key: res.key, key_hash: hashKey(res.key), plan: res.plan })
  repo.setPlan(res.plan)
  const liteKey = generateKey('lite')
  return { ok: true, plan: repo.getPlan(), stored: repo.getSetting('license').plan, litePlan: verifyKey(liteKey).plan, tampered: verifyKey(key.slice(0, -1) + (key.at(-1) === 'A' ? 'B' : 'A')).ok }
})
check('라이선스: Pro 키 입력 시 Pro 플랜 활성화', license.ok && license.plan === 'pro' && license.stored === 'pro')
check('라이선스: Lite 키는 Lite 로 인식', license.litePlan === 'lite')
check('라이선스: 한 글자 바뀐 키는 거부', license.tampered === false)

// Pro 플랜에서 동기화 설정 UI 노출
await reload()
await page.click('.app-nav button[data-view="settings"]')
await page.waitForSelector('details')
const hasProSection = await page.evaluate(() =>
  [...document.querySelectorAll('details summary')].some((s) => s.textContent.includes('Pro 동기화')))
check('Pro: 설정에 동기화 섹션이 나타난다', hasProSection)

// ── 5. 태권도장 시나리오 (계열 전환) ────────────────────────
await seed('taekwondo')
await reload()
info = await snapshot()
check('태권도장: 학원명 전환', info.headerTitle === '성무 태권도')
check('태권도장: 브랜드 컬러 전환', info.brand === '#dc2626')
check('태권도장: custom 필드가 체육 세트로 교체', info.fieldKeys.join() === 'belt,promo_at,goal')
check('태권도장: 원생 카드 항목이 띠 급수로 표시', info.samplePairs.some((p) => p.label === '띠 급수' && p.value))

// ── 정리 ────────────────────────────────────────────────────
const failed = results.filter((r) => !r.ok)
console.log(`\n─ 스모크 결과 ${'─'.repeat(40)}`)
for (const r of results) console.log(`  ${r.ok ? '✅' : '❌'} ${r.name}`)
console.log(`─${'─'.repeat(52)}`)
console.log(`  ${failed.length ? `${failed.length}건 실패` : `${results.length}건 전부 통과`}\n`)

await context.close()
kill()
process.exit(failed.length ? 1 : 0)

// ── 헬퍼 ────────────────────────────────────────────────────
function check(name, ok) {
  results.push({ name, ok: !!ok })
  console.log(`  ${ok ? '✅' : '❌'} ${name}`)
}

async function seed(scenario) {
  console.log(`\n▶ 데모 시드: ${scenario}`)
  await page.evaluate(async (key) => {
    const { seedDemo } = await import('/src/data/seed.js')
    await seedDemo(key, { students: 30 })
    const { db } = await import('/src/data/db.js')
    const owner = (await db.users.toArray()).find((u) => u.role === 'owner')
    if (owner) localStorage.setItem('academy-note:session', JSON.stringify({ userId: owner.id, at: Date.now() }))
  }, scenario)
}

async function reload() {
  await page.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'load' })
  await page.waitForSelector('.app-nav button')
}

function snapshot() {
  return page.evaluate(async () => {
    const repo = await import('/src/data/repo.js')
    const { displayPairs } = await import('/src/core/customfields.js')
    const fields = repo.getSetting('customFields', [])
    const student = repo.cache.students.find((s) => Object.keys(s.custom || {}).length) || repo.cache.students[0]
    return {
      headerTitle: document.querySelector('.app-header .title')?.textContent,
      brand: getComputedStyle(document.documentElement).getPropertyValue('--brand').trim(),
      fieldKeys: fields.map((f) => f.key),
      students: repo.cache.students.length,
      samplePairs: displayPairs(fields, student?.custom || {}, 'card')
    }
  })
}

function chromeExecutable() {
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
    try { if ((await fetch(url)).ok) return } catch {}
    if (Date.now() > until) throw new Error(`개발 서버가 뜨지 않았습니다: ${url}`)
    await new Promise((r) => setTimeout(r, 300))
  }
}
