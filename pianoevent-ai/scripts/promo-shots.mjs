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
import { existsSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync, statSync } from 'node:fs'
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

/** JPEG 파일에서 [폭, 높이] 를 읽는다 — 캡처가 잘렸는지 확인하는 용도 */
function jpegSize(path) {
  const bytes = readFileSync(path)
  let i = 2
  while (i < bytes.length) {
    if (bytes[i] !== 0xff) {
      i += 1
      continue
    }
    const marker = bytes[i + 1]
    if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
      return [bytes.readUInt16BE(i + 7), bytes.readUInt16BE(i + 5)]
    }
    i += 2 + bytes.readUInt16BE(i + 2)
  }
  return [0, 0]
}

let server
let browser
try {
  if (existsSync(DATA)) renameSync(DATA, BACKUP)
  // promo/ 안에는 캐러셀 등 다른 산출물도 있으므로 통째로 지우지 않는다
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

  /** 연주회장 스크린 — 16:9 슬라이드 한 장을 그대로 찍는다 */
  const stageShots = [
    ['stage-screen.jpg', 0],
    ['stage-performance.jpg', 3],
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

  for (const [file, advance] of stageShots) {
    const context = await browser.newContext({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 0.8 })
    const page = await context.newPage()
    await page.goto(`${BASE}/events/${EVENT_ID}/stage?theme=${THEME}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(400)
    for (let i = 0; i < advance; i += 1) await page.keyboard.press('ArrowRight')
    await page.waitForTimeout(300)
    const slide = page.locator('.stage-slide').first()
    await slide.screenshot({ path: join(OUT, file), type: 'jpeg', quality: 70 })
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

    // 진행표·대본처럼 한 장을 넘치는 문서는 종이가 세로로 늘어난다.
    // 창이 그보다 낮으면 캡처가 아래를 잘라 먹으므로, 종이 높이에 맞춰 창을 키운 뒤 찍는다.
    const box = await sheet.boundingBox()
    if (box && box.height > 1200) {
      await page.setViewportSize({ width: 900, height: Math.ceil(box.height) + 80 })
      await page.waitForTimeout(200)
    }
    await sheet.screenshot({ path: join(OUT, file), type: 'jpeg', quality: 64 })

    // 잘렸는지 눈으로 확인하지 않는다 — 파일 높이와 종이 높이를 맞춰 본다
    const shot = await sheet.boundingBox()
    const [, pixels] = jpegSize(join(OUT, file))
    const expected = Math.round((shot?.height ?? 0) * 0.8)
    if (Math.abs(pixels - expected) > 4) {
      throw new Error(`${file} 가 잘렸습니다 — 종이 ${expected}px 인데 그림은 ${pixels}px 입니다.`)
    }
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
