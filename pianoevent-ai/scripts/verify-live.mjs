#!/usr/bin/env node
/**
 * 당일 진행 화면 · 여러 곡 맡은 아이 · 초대장 영상 검사.
 *
 *   npm run build && node scripts/verify-live.mjs
 *
 * 연주회 당일에 쓰는 화면은 그날 처음 열어 보게 된다. 그 전에 여기서 눌러 본다.
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, renameSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'

const PORT = Number(process.env.LIVE_PORT ?? 3994)
const BASE = `http://127.0.0.1:${PORT}`
const DATA = join(process.cwd(), '.data')
const BACKUP = join(mkdtempSync(join(tmpdir(), 'pianoevent-live-')), 'data')
const OUT = join(process.cwd(), 'shots', 'live')
const EVENT_ID = 'demo-event'

let passed = 0
const failures = []

function check(name, condition, detail = '') {
  if (condition) {
    passed += 1
    console.log(`  ✓ ${name}`)
  } else {
    failures.push(`${name}${detail ? ` — ${detail}` : ''}`)
    console.log(`  ✗ ${name}${detail ? ` — ${detail}` : ''}`)
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
try {
  if (existsSync(DATA)) renameSync(DATA, BACKUP)
  mkdirSync(OUT, { recursive: true })

  server = spawn(process.execPath, [join('node_modules', 'next', 'dist', 'bin', 'next'), 'start', '-p', String(PORT)], {
    stdio: ['ignore', 'ignore', 'pipe'],
    detached: true,
    env: { ...process.env, NODE_ENV: 'production' },
  })
  server.stderr.on('data', (chunk) => {
    const line = String(chunk).trim()
    if (line) console.error(`  [server] ${line}`)
  })
  if (!(await waitForServer())) throw new Error(`서버가 ${BASE} 에서 뜨지 않았습니다.`)
  await fetch(`${BASE}/api/events/${EVENT_ID}/program`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })

  const executablePath = process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
  browser = await chromium.launch(existsSync(executablePath) ? { executablePath } : {})
  // 원장님 휴대폰 크기로 연다 — 당일에 이걸 손에 들고 계신다
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  })
  const page = await context.newPage()
  page.on('pageerror', (error) => failures.push(`화면 오류: ${error.message}`))

  // ── 한 아이가 여러 곡 ────────────────────────────────────────────
  console.log('\n[한 아이가 여러 곡]')
  const desktop = await browser.newContext({ viewport: { width: 1400, height: 1000 } })
  const wide = await desktop.newPage()
  wide.on('pageerror', (error) => failures.push(`명단 화면 오류: ${error.message}`))
  await wide.goto(`${BASE}/events/${EVENT_ID}?tab=roster`, { waitUntil: 'networkidle' })

  const beforeRows = await wide.locator('table tbody tr').count()
  const firstName = (await wide.locator('table tbody tr').first().locator('input[aria-label="이름"]').inputValue()).trim()
  await wide.getByRole('button', { name: `${firstName} 곡 추가` }).first().click()
  await wide.waitForTimeout(1500)
  const afterRows = await wide.locator('table tbody tr').count()
  check('곡 추가로 한 줄이 늘어난다', afterRows === beforeRows + 1, `${beforeRows} → ${afterRows}`)

  const sameName = await wide.locator(`table tbody tr input[aria-label="이름"]`).evaluateAll(
    (nodes, target) => nodes.filter((node) => node.value.trim() === target).length,
    firstName,
  )
  check('같은 아이 이름으로 들어간다', sameName === 2, `${sameName}줄`)
  const rosterText = await wide.locator('table').textContent()
  check('몇 곡 중 몇 번째인지 표시한다', rosterText.includes('2곡 중 1번째'), rosterText.slice(0, 80))
  const headText = await wide.locator('h3, [class*="CardTitle"], div').filter({ hasText: /연주자 \d+명/ }).first().textContent()
  check('사람 수와 곡 수를 따로 센다', /연주자 \d+명/.test(headText) && headText.includes('곡'), headText.trim().slice(0, 40))

  // 영상에서는 한 사람이 한 장면으로 묶여야 한다 — 늘어난 곡까지 순서표에 넣고 다시 본다
  await wide.request.post(`${BASE}/api/events/${EVENT_ID}/program`, { data: {} })
  await wide.goto(`${BASE}/events/${EVENT_ID}/video`, { waitUntil: 'networkidle' })
  await wide.waitForTimeout(1600)
  const boardText = await wide.getByTestId('storyboard').textContent()
  const shown = (boardText.match(new RegExp(firstName, 'g')) ?? []).length
  check('영상에서는 같은 얼굴이 한 번만 지나간다', shown === 1, `${shown}회`)
  await desktop.close()

  // ── 당일 진행 화면 ───────────────────────────────────────────────
  console.log('\n[당일 진행]')
  await page.goto(`${BASE}/events/${EVENT_ID}/live`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(600)

  const board = page.getByTestId('live-board')
  check('당일 진행 화면이 열린다', (await board.count()) === 1)
  const nowText = (await page.getByTestId('live-now').textContent()).trim()
  check('지금 순서를 크게 보여 준다', nowText.length > 0, nowText)
  const nowSize = await page.getByTestId('live-now').evaluate((node) => parseFloat(getComputedStyle(node).fontSize))
  check('무대 옆에서 읽을 만큼 크다', nowSize >= 28, `${nowSize}px`)
  const nextText = (await page.getByTestId('live-next').textContent()).trim()
  check('다음 순서도 함께 보여 준다', nextText.length > 0 && nextText !== nowText, nextText)

  // 누르는 곳이 손가락에 맞는가
  const nextButton = page.getByRole('button', { name: '개회 · 시작' })
  const buttonBox = await nextButton.boundingBox()
  check('누르는 단추가 손가락에 맞는다', buttonBox.height >= 44, `${Math.round(buttonBox.height)}px`)

  // 가로로 넘치지 않는가 — 휴대폰에서 옆으로 밀리면 못 쓴다
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  check('휴대폰 화면에서 가로로 넘치지 않는다', overflow <= 1, `${overflow}px`)

  await page.screenshot({ path: join(OUT, 'live-before.jpg'), type: 'jpeg', quality: 82, fullPage: false })

  // 개회를 누르고 넘겨 본다
  await nextButton.click()
  await page.waitForTimeout(1400)
  check('개회를 누르면 경과 시간이 흐른다', (await board.textContent()).includes('경과'))
  check('예정과 견준 결과를 알려 준다', (await page.getByTestId('live-drift').count()) === 1)

  await page.getByRole('button', { name: '다음 순서로' }).click()
  await page.waitForTimeout(400)
  const movedNow = (await page.getByTestId('live-now').textContent()).trim()
  check('다음 순서로 넘어간다', movedNow === nextText.replace(/^\d+\.\s*/, ''), `${nowText} → ${movedNow}`)

  await page.screenshot({ path: join(OUT, 'live-running.jpg'), type: 'jpeg', quality: 82 })

  // 새로고침해도 자리를 잃지 않는가 — 당일에 실수로 새로고침하는 일은 반드시 생긴다
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  check('새로고침해도 진행하던 자리가 남는다', (await page.getByTestId('live-now').textContent()).trim() === movedNow)
  check('새로고침해도 시계가 이어진다', (await board.textContent()).includes('경과'))

  // 전체 순서에서 건너뛰기
  const rows = board.locator('ol li button')
  const rowCount = await rows.count()
  check('전체 순서를 모두 보여 준다', rowCount >= 12, `${rowCount}개`)
  await rows.nth(rowCount - 1).click()
  await page.waitForTimeout(400)
  check('마지막 순서로 건너뛰면 "다음 없음" 이 된다', (await page.getByTestId('live-next').textContent()).includes('없음'))

  // 되돌리기
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '처음으로 되돌리기' }).click()
  await page.waitForTimeout(500)
  check('처음으로 되돌린다', (await board.textContent()).includes('아직 시작 전입니다'))

  // ── 초대장 영상 ─────────────────────────────────────────────────
  console.log('\n[초대장 영상]')
  await page.request.patch(`${BASE}/api/events/${EVENT_ID}`, {
    data: { video_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' },
  })
  await page.goto(`${BASE}/e/${EVENT_ID}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(500)
  const frame = page.locator('iframe[title*="영상"]')
  check('초대장에 영상이 붙는다', (await frame.count()) === 1)
  const frameBox = await frame.boundingBox()
  check('영상이 16:9 로 들어간다', Math.abs(frameBox.width / frameBox.height - 16 / 9) < 0.05, `${Math.round(frameBox.width)}×${Math.round(frameBox.height)}`)
  const inviteOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  check('초대장이 가로로 넘치지 않는다', inviteOverflow <= 1, `${inviteOverflow}px`)
  await page.screenshot({ path: join(OUT, 'invite-video.jpg'), type: 'jpeg', quality: 82 })

  // 이상한 주소는 받지 않는다
  const bad = await page.request.patch(`${BASE}/api/events/${EVENT_ID}`, {
    data: { video_url: 'javascript:alert(1)' },
  })
  check('위험한 주소는 거절한다', bad.status() >= 400, String(bad.status()))
  await page.request.patch(`${BASE}/api/events/${EVENT_ID}`, { data: { video_url: '' } })
  const cleared = await (await page.request.get(`${BASE}/e/${EVENT_ID}`)).text()
  check('주소를 비우면 초대장에서 빠진다', !cleared.includes('youtube-nocookie'))

  await context.close()
} catch (error) {
  failures.push(error instanceof Error ? error.message : String(error))
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

console.log(`\n${passed}건 통과 · ${failures.length}건 실패`)
if (failures.length > 0) {
  for (const failure of failures) console.error(`  ✗ ${failure}`)
  process.exitCode = 1
}
