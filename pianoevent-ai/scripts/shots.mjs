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
  ['22-poster-noir.png', print_('poster-classic', 'noir-gold'), 900, true],
  ['23-cover-burgundy.png', print_('program-cover', 'burgundy-velvet'), 900, true],
  ['24-poster-sepia.png', print_('poster-program', 'sepia-archive'), 900, true],
  ['25-social-spring.png', print_('social-card', 'spring-bloom'), 1000, true],
  ['26-cover-moonlit.png', print_('program-cover', 'moonlit-blue'), 900, true],
  ['27-ticket-pearl.png', print_('ticket-strip', 'pearl-mint'), 900, true],
  ['28-fullbleed-sunlit.png', print_('poster-fullbleed', 'sunlit-ivory'), 900, true],
  ['29-fullbleed-daylight.png', print_('poster-fullbleed', 'daylight-studio'), 900, true],
  ['30-photo-blossom.png', print_('poster-photo', 'blossom-white'), 900, true],
  ['31-cover-sky.png', print_('program-cover', 'sky-linen'), 900, true],
  ['32-cue-sheet.png', print_('cue-sheet', 'daylight-studio'), 900, true],
  ['33-checklist.png', print_('checklist', 'sunlit-ivory'), 900, true],
  ['34-prep-panel.png', `/events/${EVENT_ID}?tab=prep`, 1280, true],

  // ── 확장된 양식 17종 · 새 테마 ─────────────────────────────
  ['35-plan-panel.png', `/events/${EVENT_ID}?tab=plan`, 1280, true],
  ['36-poster-typographic.png', print_('poster-typographic', 'gallery-white'), 900, true],
  ['37-poster-duo.png', print_('poster-duo', 'marble-white'), 900, true],
  ['38-program-notes.png', print_('program-notes', 'vienna-hall'), 900, true],
  ['39-program-trifold.png', print_('program-trifold', 'royal-emerald'), 1240, true],
  ['40-invitation-card.png', print_('invitation-card', 'antique-rose'), 900, true],
  ['41-story-card.png', print_('story-card', 'cotton-candy'), 820, true],
  ['42-banner-stand.png', print_('banner-stand', 'cherry-spring'), 620, true],
  ['43-seating-chart.png', print_('seating-chart', 'platinum-grey'), 1240, true],
  ['44-backstage-board.png', print_('backstage-board', 'summer-marine'), 900, true],
  ['45-photo-zone.png', print_('photo-zone', 'lavender-dream'), 1240, true],
  ['46-award-sheet.png', print_('award-sheet', 'graduation-day'), 900, true],
  ['47-mc-script.png', print_('mc-script', 'steinway-black'), 900, true],
  ['48-rehearsal-sheet.png', print_('rehearsal-sheet', 'winter-snow'), 900, true],
  ['49-attendance-sheet.png', print_('attendance-sheet', 'autumn-maple'), 900, true],
  ['50-budget-sheet.png', print_('budget-sheet', 'newyear-red'), 900, true],
  ['51-parent-notice.png', print_('parent-notice', 'peach-blossom'), 900, true],
  ['52-student-notice.png', print_('student-notice', 'milky-bear'), 900, true],
  ['53-poster-opera.png', print_('poster-classic', 'opera-crimson'), 900, true],
  ['54-cover-ribbon.png', print_('program-cover', 'ribbon-cream'), 900, true],
  ['55-social-bonbon.png', print_('social-card', 'bonbon-mint'), 1000, true],
  ['56-design-studio-family.png', `/events/${EVENT_ID}/design`, 1440, true],
  ['57-asset-library.png', '/settings', 1280, true],
  ['58-roster-import.png', `/events/${EVENT_ID}?tab=roster`, 1280, true],

  // ── 새 양식 8종 · 새 테마 ──────────────────────────────────
  ['59-stage-map.png', print_('stage-map', 'blueprint'), 1240, true],
  ['60-banner-horizontal.png', print_('banner-horizontal', 'cathedral-navy'), 1560, true],
  ['61-signage.png', print_('signage', 'poster-red'), 900, true],
  ['62-practice-log.png', print_('practice-log', 'apricot-cream'), 900, true],
  ['63-performer-cards.png', print_('performer-cards', 'rosewood-cream'), 900, true],
  ['64-guestbook.png', print_('guestbook', 'marshmallow'), 900, true],
  ['65-thanks-letter.png', print_('thanks-letter', 'champagne-gold'), 1240, true],
  ['66-after-notice.png', print_('after-notice', 'harvest-gold'), 900, true],
  ['67-poster-onyx.png', print_('poster-classic', 'onyx-pearl'), 900, true],
  ['68-poster-plum.png', print_('poster-classic', 'plum-blossom'), 900, true],
  ['69-cover-oxford.png', print_('program-cover', 'oxford-green'), 900, true],
  ['70-theme-search.png', `/events/${EVENT_ID}/design`, 1440, true],
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
    body: JSON.stringify({ status: 'published', design_theme: 'daylight-studio' }),
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
