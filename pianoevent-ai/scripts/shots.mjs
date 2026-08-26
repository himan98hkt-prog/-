#!/usr/bin/env node
/**
 * 실제 서버를 띄워 주요 화면을 캡처한다.
 *
 *   npm run build && npm run shots
 *
 * 데모 시드(하모니 피아노학원 · 제12회 정기 연주회 · 연주자 12명)를 기준으로
 * 순서표 생성 → 초대장 배포 → 참석 회신까지 만들어 둔 상태를 찍는다.
 * 산출물은 screenshots/ 에 남는다.
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, renameSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'

const PORT = Number(process.env.SHOTS_PORT ?? 3988)
const BASE = `http://127.0.0.1:${PORT}`
const OUT = join(process.cwd(), 'screenshots')
const DATA = join(process.cwd(), '.data')
const BACKUP = join(mkdtempSync(join(tmpdir(), 'pianoevent-shots-')), 'data')

const EVENT_ID = 'demo-event'

const print_ = (template, theme) => `/events/${EVENT_ID}/design/print?template=${template}&theme=${theme}`

/** [파일명, 경로, 뷰포트 폭, 전체 페이지 여부] */
const SHOTS = [
  ['01-home.png', '/', 1280, false],
  ['02-events.png', '/events', 1280, true],
  ['03-roster.png', `/events/${EVENT_ID}?tab=roster`, 1280, true],
  ['04-program.png', `/events/${EVENT_ID}?tab=program`, 1280, true],
  ['05-program-print.png', `/events/${EVENT_ID}/program/print`, 1024, true],
  ['06-script.png', `/events/${EVENT_ID}/script`, 1024, true],
  ['07-invite-admin.png', `/events/${EVENT_ID}/invite`, 1280, true],
  ['08-invite-mobile.png', `/e/${EVENT_ID}`, 390, true],
  ['09-seasons.png', '/seasons', 1280, false],
  ['10-settings.png', '/settings', 1280, true],
  ['11-design-studio.png', `/events/${EVENT_ID}/design`, 1440, true],
  ['12-poster-classic.png', print_('poster-classic', 'classic-navy'), 900, true],
  ['13-poster-modern.png', print_('poster-modern', 'modern-mono'), 900, true],
  ['13b-poster-photo.png', print_('poster-photo', 'classic-navy'), 900, true],
  ['14-poster-program.png', print_('poster-program', 'ivory-gold'), 900, true],
  ['15-program-cover.png', print_('program-cover', 'blush-romance'), 900, true],
  ['16-program-bifold.png', print_('program-bifold', 'forest-calm'), 1240, true],
  ['17-ticket.png', print_('ticket-strip', 'midnight-stage'), 900, true],
  ['18-social-card.png', print_('social-card', 'halloween-night'), 1000, true],
  ['19-certificate.png', print_('certificate', 'christmas-warm'), 1240, true],
  ['20-nametag.png', print_('nametag', 'pastel-kids'), 900, true],
  ['21-thankyou.png', print_('thankyou-card', 'crayon-play'), 900, true],
]

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
      /* 아직 뜨지 않음 */
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
    body: JSON.stringify({ status: 'published' }),
  })

  const replies = [
    { parent_name: '김○○', student_name: '김서연', headcount: 3, message: '연습한 만큼만 하고 오면 돼. 우리 딸 최고!' },
    { parent_name: '박○○', student_name: '박지호', headcount: 2, message: '첫 무대 축하해!' },
    { parent_name: '윤○○', student_name: '윤채원', headcount: 4, message: null },
    { parent_name: '최○○', student_name: '최은우', headcount: 2, message: '떨지 말고 즐기고 오렴.' },
  ]
  for (const reply of replies) {
    await post('/api/rsvp', { event_id: EVENT_ID, attending: true, ...reply })
  }
  await post('/api/rsvp', {
    event_id: EVENT_ID,
    parent_name: '임○○',
    student_name: '임하람',
    attending: false,
    headcount: 0,
    message: '가족 일정이 겹쳐 참석이 어렵습니다. 죄송합니다.',
  })
}

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
  server.stderr.on('data', (chunk) => {
    const line = String(chunk).trim()
    if (line) console.error(`  [server] ${line}`)
  })

  if (!(await waitForServer())) throw new Error(`서버가 ${BASE} 에서 뜨지 않았습니다.`)
  await seed()

  // 환경에 미리 설치된 Chromium 을 쓴다 (playwright 버전과 브라우저 빌드 번호가 어긋나도 동작)
  const executablePath = process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
  browser = await chromium.launch(existsSync(executablePath) ? { executablePath } : {})
  for (const [file, path, width, fullPage] of SHOTS) {
    const context = await browser.newContext({
      viewport: { width, height: width < 500 ? 844 : 900 },
      deviceScaleFactor: 2,
      isMobile: width < 500,
      locale: 'ko-KR',
      timezoneId: 'Asia/Seoul',
    })
    const page = await context.newPage()
    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(400)
    await page.screenshot({ path: join(OUT, file), fullPage })
    await context.close()
    console.log(`  ✓ ${file}  ${path}`)
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
