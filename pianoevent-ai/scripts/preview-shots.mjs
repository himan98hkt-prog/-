#!/usr/bin/env node
/**
 * "구경용 미리보기" 페이지에 넣을 화면 캡처.
 * 설치 없이 파일 하나로 제품을 보여 주기 위한 것이라, 앱 화면과 인쇄물을 골고루 담는다.
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, renameSync, rmSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'

const PORT = Number(process.env.PREVIEW_PORT ?? 3990)
const BASE = `http://127.0.0.1:${PORT}`
const OUT = join(process.cwd(), 'promo', 'preview')
const DATA = join(process.cwd(), '.data')
const BACKUP = join(mkdtempSync(join(tmpdir(), 'pianoevent-preview-')), 'data')
const EVENT_ID = 'demo-event'

const post = (p, b) =>
  fetch(`${BASE}${p}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) })

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
    body: JSON.stringify({ status: 'published', design_theme: 'sunlit-ivory' }),
  })
  for (const r of [
    { parent_name: '김○○', student_name: '김서연', headcount: 3, message: '연습한 만큼만 하고 오면 돼. 우리 딸 최고!' },
    { parent_name: '박○○', student_name: '박지호', headcount: 2, message: '첫 무대 축하해!' },
    { parent_name: '윤○○', student_name: '윤채원', headcount: 4, message: null },
  ]) {
    await post('/api/rsvp', { event_id: EVENT_ID, attending: true, ...r })
  }
}

const APP = [
  ['app-home.jpg', '/', 1280, 860],
  ['app-roster.jpg', `/events/${EVENT_ID}?tab=roster`, 1280, 980],
  ['app-program.jpg', `/events/${EVENT_ID}?tab=program`, 1280, 1180],
  ['app-design.jpg', `/events/${EVENT_ID}/design`, 1280, 1000],
  ['app-prep.jpg', `/events/${EVENT_ID}?tab=prep`, 1280, 1150],
  ['app-invite-admin.jpg', `/events/${EVENT_ID}/invite`, 1280, 900],
  ['app-seasons.jpg', '/seasons', 1280, 900],
]

const MOBILE = [['mobile-invite.jpg', `/e/${EVENT_ID}`, 390, 1400]]

const SHEETS = [
  ['sheet-poster-sunlit.jpg', 'poster-classic', 'sunlit-ivory'],
  ['sheet-poster-noir.jpg', 'poster-classic', 'noir-gold'],
  ['sheet-poster-blossom.jpg', 'poster-fullbleed', 'blossom-white'],
  ['sheet-program.jpg', 'program-inner', 'sunlit-ivory'],
  ['sheet-cover.jpg', 'program-cover', 'moonlit-blue'],
  ['sheet-ticket.jpg', 'ticket-strip', 'pearl-mint'],
  ['sheet-nametag.jpg', 'nametag', 'pastel-kids'],
  ['sheet-certificate.jpg', 'certificate', 'classic-navy'],
  ['sheet-cue.jpg', 'cue-sheet', 'daylight-studio'],
  ['sheet-checklist.jpg', 'checklist', 'sunlit-ivory'],
]

const kb = (f) => Math.round(statSync(join(OUT, f)).size / 1024)

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
    const l = String(c).trim()
    if (l) console.error(`  [server] ${l}`)
  })
  if (!(await waitForServer())) throw new Error('서버가 뜨지 않았습니다.')
  await seed()

  const exe = process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
  browser = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})

  for (const [file, path, width, height] of [...APP, ...MOBILE]) {
    const ctx = await browser.newContext({
      viewport: { width, height },
      deviceScaleFactor: width > 500 ? 0.85 : 1,
      isMobile: width < 500,
      locale: 'ko-KR',
      timezoneId: 'Asia/Seoul',
    })
    const page = await ctx.newPage()
    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(450)
    await page.screenshot({ path: join(OUT, file), type: 'jpeg', quality: 68 })
    await ctx.close()
    console.log(`  ✓ ${file}  ${kb(file)}KB`)
  }

  for (const [file, template, theme] of SHEETS) {
    const ctx = await browser.newContext({ viewport: { width: 900, height: 1300 }, deviceScaleFactor: 0.8 })
    const page = await ctx.newPage()
    await page.goto(`${BASE}/events/${EVENT_ID}/design/print?template=${template}&theme=${theme}`, {
      waitUntil: 'networkidle',
    })
    await page.addStyleTag({ content: '.no-print{display:none!important}body{background:#fff}' })
    await page.waitForTimeout(350)
    await page.locator('.d-sheet').first().screenshot({ path: join(OUT, file), type: 'jpeg', quality: 66 })
    await ctx.close()
    console.log(`  ✓ ${file}  ${kb(file)}KB`)
  }
} catch (e) {
  console.error(`실패 — ${e instanceof Error ? e.message : String(e)}`)
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
