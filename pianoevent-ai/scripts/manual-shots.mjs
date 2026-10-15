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
  {
    name: 'roster',
    at: `/events/${EVENT_ID}?tab=roster`,
    height: 1150,
    why: '학생 명단 넣기',
    // 누를 자리에 동그라미를 친다 — 글 세 줄이 동그라미 하나로 줄어든다
    marks: [
      { at: '[data-testid="roster-guide"] a[href="/api/roster-template"]', label: '①' },
      { at: '[data-testid="roster-drop"]', label: '②' },
    ],
  },
  {
    name: 'program',
    at: `/events/${EVENT_ID}?tab=program`,
    height: 1150,
    why: '순서표 · 사회자 대본',
    marks: [{ at: 'button:has-text("AI 순서표 만들기")', label: '①' }],
  },
  {
    name: 'design',
    at: `/events/${EVENT_ID}/design`,
    height: 1150,
    why: '인쇄물 디자인',
    marks: [{ at: 'a:has-text("인쇄 · PDF")', label: '①' }],
  },
  {
    name: 'print',
    at: `/events/${EVENT_ID}/program/print`,
    height: 900,
    why: '인쇄 · 종이 미리보기',
    paper: true,
    marks: [
      { at: '[data-testid="paper-toggle"]', label: '①' },
      { at: '[data-testid="print-first"]', label: '②' },
      { at: '[data-testid="print-now"]', label: '③' },
    ],
  },
  { name: 'stage', at: `/events/${EVENT_ID}/stage`, height: 1000, why: '무대 화면' },
  {
    name: 'video',
    at: `/events/${EVENT_ID}/video`,
    height: 1100,
    why: '감동영상',
    marks: [{ at: '[data-testid="video-ready"]', label: '①' }],
  },
  { name: 'live', at: `/events/${EVENT_ID}/live`, height: 900, why: '당일 진행', phone: true },
  { name: 'invite', at: `/events/${EVENT_ID}/invite`, height: 1000, why: '초대장 · 참석 집계' },
  {
    name: 'settings',
    at: '/settings',
    height: 1100,
    why: '학원 정보 · 자동 저장',
    marks: [{ at: '[data-testid="backup-open"]', label: '①' }],
  },
  { name: 'seasons', at: '/seasons', height: 900, why: '시즌 특강' },
]

/**
 * 누를 자리에 동그라미와 번호를 얹는다.
 *
 * 그림만 넣어 두면 "이 화면에서 어디를 누르나요" 가 남는다. 그건 다시 글이 된다.
 * 화면 위에 직접 표시해 두면 글 세 줄이 동그라미 하나로 줄어든다.
 */
async function drawMarks(page, marks) {
  for (const [index, mark] of marks.entries()) {
    const box = await page
      .locator(mark.at)
      .first()
      .boundingBox()
      .catch(() => null)
    if (!box) {
      console.log(`    · ${mark.label} 자리를 못 찾음 (${mark.at})`)
      continue
    }
    await page.evaluate(
      ({ box, label, index }) => {
        const pad = 6
        const ring = document.createElement('div')
        Object.assign(ring.style, {
          position: 'absolute',
          left: `${box.x + window.scrollX - pad}px`,
          top: `${box.y + window.scrollY - pad}px`,
          width: `${box.width + pad * 2}px`,
          height: `${box.height + pad * 2}px`,
          border: '3px solid #d97706',
          borderRadius: '12px',
          boxShadow: '0 0 0 4px rgba(217,119,6,.18)',
          pointerEvents: 'none',
          zIndex: '9999',
        })
        const tag = document.createElement('div')
        tag.textContent = label
        Object.assign(tag.style, {
          position: 'absolute',
          left: `${box.x + window.scrollX - pad - 13}px`,
          top: `${box.y + window.scrollY - pad - 13}px`,
          width: '26px',
          height: '26px',
          lineHeight: '26px',
          textAlign: 'center',
          borderRadius: '999px',
          background: '#d97706',
          color: '#fff',
          font: '700 15px/26px system-ui, sans-serif',
          pointerEvents: 'none',
          zIndex: '10000',
        })
        tag.dataset.manualMark = String(index)
        document.body.append(ring, tag)
      },
      { box, label: mark.label, index },
    )
  }
}

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
    if (shot.marks) await drawMarks(page, shot.marks)
    await page.waitForTimeout(200)
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
