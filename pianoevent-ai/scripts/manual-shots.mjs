#!/usr/bin/env node
/**
 * 사용설명서에 넣을 화면 그림 만들기.
 *
 *   npm run build && node scripts/manual-shots.mjs
 *
 * 설명서가 글만 있으면 "이 화면이 그 화면 맞나?" 에서 멈추신다. 절마다 한 장씩,
 * 원장님이 실제로 보실 화면을 그대로 찍어 둔다.
 *
 * 그림은 public/manual/ 에 둔다 — 프로그램 안에서 그대로 열리고, 인터넷도 필요 없다.
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, renameSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'

const PORT = Number(process.env.MANUAL_PORT ?? 3998)
const BASE = `http://127.0.0.1:${PORT}`
const DATA = join(process.cwd(), '.data')
const BACKUP = join(mkdtempSync(join(tmpdir(), 'pianoevent-manual-')), 'data')
const OUT = join(process.cwd(), 'public', 'manual')
const EVENT_ID = 'demo-event'

/**
 * 찍을 곳. `clip` 이 없으면 창 전체.
 * 설명서에 붙는 그림이라 **너무 크면 글을 밀어낸다** — 필요한 만큼만 잘라 둔다.
 */
const SHOTS = [
  { name: 'roster', at: `/events/${EVENT_ID}?tab=roster`, height: 1150, why: '학생 명단 넣기' },
  { name: 'program', at: `/events/${EVENT_ID}?tab=program`, height: 1150, why: '순서표 · 사회자 대본' },
  { name: 'design', at: `/events/${EVENT_ID}/design`, height: 1150, why: '인쇄물 디자인' },
  { name: 'print', at: `/events/${EVENT_ID}/program/print`, height: 900, why: '인쇄 · 종이 미리보기', paper: true },
  { name: 'stage', at: `/events/${EVENT_ID}/stage`, height: 1000, why: '무대 화면' },
  { name: 'video', at: `/events/${EVENT_ID}/video`, height: 1100, why: '감동영상' },
  { name: 'live', at: `/events/${EVENT_ID}/live`, height: 900, why: '당일 진행', phone: true },
  { name: 'invite', at: `/events/${EVENT_ID}/invite`, height: 1000, why: '초대장 · 참석 집계' },
  { name: 'settings', at: '/settings', height: 1100, why: '학원 정보 · 자동 저장' },
  { name: 'seasons', at: '/seasons', height: 900, why: '시즌 특강' },
]

async function waitForServer(timeoutMs = 60_000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      if ((await fetch(`${BASE}/`, { redirect: 'manual' })).status < 500) return true
    } catch {
      /* 아직 */
    }
    await new Promise((resolve) => setTimeout(resolve, 400))
  }
  return false
}

let server
let browser
let made = 0
try {
  if (existsSync(DATA)) renameSync(DATA, BACKUP)
  mkdirSync(OUT, { recursive: true })

  server = spawn(
    process.execPath,
    [join('node_modules', 'next', 'dist', 'bin', 'next'), 'start', '-p', String(PORT)],
    { stdio: ['ignore', 'ignore', 'pipe'], detached: true, env: { ...process.env, NODE_ENV: 'production' } },
  )
  server.stderr.on('data', (chunk) => {
    const line = String(chunk).trim()
    if (line) console.error(`  [server] ${line}`)
  })
  if (!(await waitForServer())) throw new Error(`서버가 ${BASE} 에서 뜨지 않았습니다.`)

  // 데모 명단으로 순서표까지 만들어 둔다 — 빈 화면을 설명서에 실을 수는 없다
  await fetch(`${BASE}/api/events/${EVENT_ID}/program`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })

  const executablePath = process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
  browser = await chromium.launch(existsSync(executablePath) ? { executablePath } : {})

  for (const shot of SHOTS) {
    const ctx = await browser.newContext(
      shot.phone
        ? { viewport: { width: 390, height: shot.height }, deviceScaleFactor: 2, isMobile: true, hasTouch: true }
        : { viewport: { width: 1280, height: shot.height }, deviceScaleFactor: 1 },
    )
    const page = await ctx.newPage()
    await page.goto(`${BASE}${shot.at}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1400)

    // 처음 켰을 때 안내는 설명서 그림마다 따라다니면 안 된다
    await page
      .getByTestId('first-run-close')
      .click({ timeout: 1500 })
      .catch(() => {})

    // 인쇄 화면은 [종이로 보기] 를 켜 둔 모습이 설명에 맞다
    if (shot.paper) {
      await page
        .getByTestId('paper-toggle')
        .click({ timeout: 3000 })
        .catch(() => {})
      await page.waitForTimeout(700)
    }

    await page.waitForTimeout(400)
    await page.screenshot({ path: join(OUT, `${shot.name}.jpg`), type: 'jpeg', quality: 78 })
    await ctx.close()
    made += 1
    console.log(`  ✓ ${shot.name}.jpg — ${shot.why}`)
  }
} catch (error) {
  console.error(error)
  process.exitCode = 1
} finally {
  if (browser) await browser.close().catch(() => {})
  if (server) {
    try {
      process.kill(-server.pid)
    } catch {
      /* 이미 죽음 */
    }
  }
  rmSync(DATA, { recursive: true, force: true })
  if (existsSync(BACKUP)) renameSync(BACKUP, DATA)
}

console.log(`\n설명서 그림 ${made}장 · public/manual/`)
