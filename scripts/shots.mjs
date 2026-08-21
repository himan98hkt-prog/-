#!/usr/bin/env node
// 데모 데이터를 넣고 각 화면을 캡처한다 — 결과물 확인용 스크린샷 생성기.
//   node scripts/shots.mjs [시나리오: english|taekwondo|piano]

import { spawn } from 'node:child_process'
import { existsSync, readdirSync, mkdirSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'

const SCENARIO = process.argv[2] || 'english'
const PORT = 5197
const OUT = 'screenshots'
const PROFILE_DIR = join(tmpdir(), `academy-note-shots-${SCENARIO}`)

mkdirSync(OUT, { recursive: true })

const server = spawn('npx', ['vite', '--port', String(PORT), '--strictPort'], { stdio: ['ignore', 'pipe', 'pipe'], detached: true })
const kill = () => { try { process.kill(-server.pid, 'SIGTERM') } catch {} }
process.on('exit', kill)

await waitForServer(`http://localhost:${PORT}/lite.html`, 30000)
const context = await chromium.launchPersistentContext(PROFILE_DIR, {
  viewport: { width: 1280, height: 900 },
  deviceScaleFactor: 2,
  ...(chromeExecutable() ? { executablePath: chromeExecutable() } : {})
})
const page = context.pages()[0] || await context.newPage()

await page.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'domcontentloaded' })
await page.evaluate(async (key) => {
  const { seedDemo } = await import('/src/data/seed.js')
  await seedDemo(key, { students: 36 })
  const { db } = await import('/src/data/db.js')
  const owner = (await db.users.toArray()).find((u) => u.role === 'owner')
  if (owner) localStorage.setItem('academy-note:session', JSON.stringify({ userId: owner.id, at: Date.now() }))
}, SCENARIO)

await page.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'load' })
await page.waitForSelector('.app-nav button')

const VIEWS = [
  ['attendance', '01-출결'],
  ['students', '02-원생'],
  ['payments', '03-수납'],
  ['timetable', '04-시간표'],
  ['counsel', '05-상담'],
  ['expenses', '06-지출'],
  ['dashboard', '07-현황'],
  ['settings', '08-설정']
]

for (const [view, name] of VIEWS) {
  await page.evaluate(async (v) => {
    const { mount } = await import('/src/ui/shell.js')
    await mount(v)
  }, view)
  await page.waitForTimeout(view === 'dashboard' ? 2500 : 400)
  await page.screenshot({ path: `${OUT}/${SCENARIO}-${name}.png` })
  console.log(`  ✓ ${SCENARIO}-${name}.png`)
}

// 원생 카드 (모달)
await page.evaluate(async () => {
  const { mount } = await import('/src/ui/shell.js')
  await mount('students')
})
await page.waitForSelector('.student-row')
await page.click('.student-row')
await page.waitForSelector('.modal')
await page.waitForTimeout(400)
await page.screenshot({ path: `${OUT}/${SCENARIO}-09-원생카드.png` })
console.log(`  ✓ ${SCENARIO}-09-원생카드.png`)

// 학부모 리포트카드 (Canvas 이미지 그대로 저장)
const reportDataUrl = await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  const { drawReportCard } = await import('/src/ui/report.js')
  const { summarize } = await import('/src/core/attendance.js')
  const { displayPairs } = await import('/src/core/customfields.js')
  const s = repo.cache.students[0]
  const att = await repo.attendanceOfStudentRange(s.id, '2000-01-01', '2100-01-01')
  const pays = await repo.paymentsOfStudent(s.id, 1)
  const cls = repo.studentClasses(s.id)
  const canvas = await drawReportCard({
    student: s,
    month: new Date().toISOString().slice(0, 7),
    className: cls.map((c) => c.name).join(', '),
    attendance: summarize(att),
    payment: pays[0] || null,
    customPairs: displayPairs(repo.getSetting('customFields', []), s.custom, 'report'),
    comment: '이번 달 수업 태도가 좋았고 진도도 계획대로 나갔습니다. 다음 달에는 발표 활동을 늘려 보겠습니다.',
    teacherName: repo.cache.users[1]?.name || ''
  })
  return canvas.toDataURL('image/png')
})
writeFileSync(`${OUT}/${SCENARIO}-10-학부모리포트.png`, Buffer.from(reportDataUrl.split(',')[1], 'base64'))
console.log(`  ✓ ${SCENARIO}-10-학부모리포트.png`)

// 키오스크 화면
await page.evaluate(async () => {
  const { openKiosk } = await import('/src/ui/views/kiosk.js')
  openKiosk()
})
await page.waitForSelector('.cover.kiosk')
await page.waitForTimeout(500)
await page.screenshot({ path: `${OUT}/${SCENARIO}-11-키오스크.png` })
console.log(`  ✓ ${SCENARIO}-11-키오스크.png`)

// 모바일 화면 (실제 사용 환경)
const mobile = await context.newPage()
await mobile.setViewportSize({ width: 390, height: 844 })
await mobile.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'load' })
await mobile.waitForSelector('.app-nav button')
await mobile.waitForTimeout(600)
await mobile.screenshot({ path: `${OUT}/${SCENARIO}-12-모바일-출결.png` })
console.log(`  ✓ ${SCENARIO}-12-모바일-출결.png`)

await context.close()
kill()

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
