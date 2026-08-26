#!/usr/bin/env node
/**
 * 상세페이지용 제품 화면 캡처.
 *
 *   npm run build && node scripts/promo-shots.mjs
 *
 * 노트북·태블릿·모바일에서 실제로 보이는 화면과 인쇄물을 JPEG 로 남긴다.
 * 상세페이지에 base64 로 심기 때문에 용량을 작게 유지한다(폭 제한 + 품질 72).
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, renameSync, rmSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'

const PORT = Number(process.env.PROMO_PORT ?? 3989)
const BASE = `http://127.0.0.1:${PORT}`
const OUT = join(process.cwd(), 'promo')
const DATA = join(process.cwd(), '.data')
const BACKUP = join(mkdtempSync(join(tmpdir(), 'pianoevent-promo-')), 'data')
const EVENT_ID = 'demo-event'
const THEME = 'sunlit-ivory'

const post = (path, body) =>
  fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

async function waitForServer(timeoutMs = 60_000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      if ((await fetch(`${BASE}/`, { redirect: 'manual' })).status < 500) return true
    } catch {
      /* 아직 */
    }
    await new Promise((r) => setTimeout(r, 400))
  }
  return false
}

async function seed() {
  await post(`/api/events/${EVENT_ID}/program`, {})
  await fetch(`${BASE}/api/events/${EVENT_ID}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'published', design_theme: THEME, design_template: 'poster-classic' }),
  })
  const replies = [
    { parent_name: '김○○', student_name: '김서연', headcount: 3, message: '연습한 만큼만 하고 오면 돼. 우리 딸 최고!' },
    { parent_name: '박○○', student_name: '박지호', headcount: 2, message: '첫 무대 축하해!' },
    { parent_name: '윤○○', student_name: '윤채원', headcount: 4, message: null },
  ]
  for (const reply of replies) await post('/api/rsvp', { event_id: EVENT_ID, attending: true, ...reply })
}

const kb = (file) => Math.round(statSync(join(OUT, file)).size / 1024)

let server
let browser
try {
  if (existsSync(DATA)) renameSync(DATA, BACKUP)
  rmSync(OUT, { recursive: true, force: true })
  mkdirSync(OUT, { recursive: true })

  server = spawn(process.execPath, [join('node_modules', 'next', 'dist', 'bin', 'next'), 'start', '-p', String(PORT)], {
    stdio: ['ignore', 'ignore', 'pipe'],
    detached: true,
    env: { ...process.env, NODE_ENV: 'production' },
  })
  server.stderr.on('data', (c) => {
    const line = String(c).trim()
    if (line) console.error(`  [server] ${line}`)
  })

  if (!(await waitForServer())) throw new Error(`서버가 ${BASE} 에서 뜨지 않았습니다.`)
  await seed()

  const executablePath = process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
  browser = await chromium.launch(existsSync(executablePath) ? { executablePath } : {})

  /** 앱 화면 — 기기 폭 그대로 (스크롤 없이 한 화면) */
  const screens = [
    ['laptop-program.jpg', `/events/${EVENT_ID}?tab=program`, 1280, 800, false],
    ['laptop-design.jpg', `/events/${EVENT_ID}/design`, 1280, 800, false],
    ['tablet-prep.jpg', `/events/${EVENT_ID}?tab=prep`, 834, 1060, false],
    ['mobile-invite.jpg', `/e/${EVENT_ID}`, 390, 844, false],
  ]

  for (const [file, path, width, height, mobile] of screens) {
    const context = await browser.newContext({
      viewport: { width, height },
      // 0.85 배로 찍어 파일을 가볍게 유지한다 (상세페이지에 base64 로 심기 때문)
      deviceScaleFactor: width > 500 ? 0.85 : 1,
      isMobile: width < 500,
      locale: 'ko-KR',
      timezoneId: 'Asia/Seoul',
    })
    const page = await context.newPage()
    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(500)
    await page.screenshot({ path: join(OUT, file), type: 'jpeg', quality: 66 })
    await context.close()
    console.log(`  ✓ ${file}  ${kb(file)}KB`)
  }

  /** 인쇄물 — 화면용 안내 줄을 감추고 종이만 찍는다 */
  const sheets = [
    ['print-poster.jpg', 'poster-classic'],
    ['print-program.jpg', 'program-inner'],
    ['print-cue.jpg', 'cue-sheet'],
  ]

  for (const [file, template] of sheets) {
    const context = await browser.newContext({ viewport: { width: 900, height: 1200 }, deviceScaleFactor: 0.8 })
    const page = await context.newPage()
    await page.goto(`${BASE}/events/${EVENT_ID}/design/print?template=${template}&theme=${THEME}`, {
      waitUntil: 'networkidle',
    })
    await page.addStyleTag({ content: '.no-print{display:none!important}body{background:#fff}' })
    await page.waitForTimeout(400)
    const sheet = page.locator('.d-sheet').first()
    await sheet.screenshot({ path: join(OUT, file), type: 'jpeg', quality: 64 })
    await context.close()
    console.log(`  ✓ ${file}  ${kb(file)}KB`)
  }
} catch (error) {
  console.error(`실패 — ${error instanceof Error ? error.message : String(error)}`)
  process.exitCode = 1
} finally {
  await browser?.close()
  if (server?.pid) {
    try {
      process.kill(-server.pid, 'SIGTERM')
    } catch {
      server.kill('SIGTERM')
    }
  }
  rmSync(DATA, { recursive: true, force: true })
  if (existsSync(BACKUP)) renameSync(BACKUP, DATA)
}

console.log(`\n캡처 완료 → ${OUT}`)
