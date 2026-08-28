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
  check('개회를 누르면 시계가 흐른다', (await board.textContent()).includes('전체 0:'))
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
  check('새로고침해도 시계가 이어진다', (await board.textContent()).includes('전체 0:'))

  // 전체 순서에서 건너뛰기
  const rows = board.locator('ol li button')
  const rowCount = await rows.count()
  check('전체 순서를 모두 보여 준다', rowCount >= 12, `${rowCount}개`)
  await rows.nth(rowCount - 1).click()
  await page.waitForTimeout(400)
  check('마지막 순서로 건너뛰면 "다음 없음" 이 된다', (await page.getByTestId('live-next').textContent()).includes('없음'))

  // 실제로 걸린 시간이 쌓이는가 — 다음 해 순서표가 이 학원 아이들에 맞게 되는 장치
  const actuals = page.getByTestId('live-actuals')
  check('실제로 걸린 시간이 쌓인다', (await actuals.count()) === 1)
  const actualText = await actuals.textContent()
  check('예정과 실제를 나란히 보여 준다', actualText.includes('예정') && actualText.includes('실제'), actualText.slice(0, 60))
  check('이 순서 시계와 전체 시계를 따로 보여 준다', (await page.getByTestId('live-stage-clock').count()) === 1)

  // 함께 보기 — 다른 화면이 따라오는가
  console.log('\n[함께 보기]')
  const share = page.getByTestId('live-share')
  check('함께 보기 칸이 있다', (await share.count()) === 1)
  await share.locator('input[type="checkbox"]').check()
  await page.waitForTimeout(1200)

  // 대기실 화면(로그인 없이 여는 곳)을 따로 띄운다
  const followerCtx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true })
  const follower = await followerCtx.newPage()
  follower.on('pageerror', (error) => failures.push(`따라보기 화면 오류: ${error.message}`))
  await follower.goto(`${BASE}/e/${EVENT_ID}/live`, { waitUntil: 'networkidle' })
  await follower.waitForTimeout(800)
  check('따라보기 화면이 로그인 없이 열린다', (await follower.getByTestId('live-board').count()) === 1)
  check('따라보기 화면에는 넘기는 단추가 없다', (await follower.getByRole('button', { name: '다음 순서로' }).count()) === 0)
  check('따라보기 화면이 진행 중인 순서를 보여 준다', (await follower.getByTestId('live-now').textContent()).trim().length > 0)

  // 무대 옆에서 넘기면 대기실 화면도 따라오는가
  // (앞선 검사에서 마지막 순서로 건너뛰어 두었으므로 넘길 수 있는 자리로 되돌린다)
  await board.locator('ol li button').nth(1).click()
  await page.waitForTimeout(4500)
  const followerFirst = (await follower.getByTestId('live-now').textContent()).trim()
  check('되돌린 자리도 대기실 화면에 그대로 온다', followerFirst.length > 0, followerFirst)

  await page.getByRole('button', { name: '다음 순서로' }).click()
  await page.waitForTimeout(5000)
  const followerAfter = (await follower.getByTestId('live-now').textContent()).trim()
  const leaderNow = (await page.getByTestId('live-now').textContent()).trim()
  check(
    '무대 옆에서 넘기면 대기실 화면도 따라 넘어간다',
    followerAfter === leaderNow && followerAfter !== followerFirst,
    `${followerFirst} → 무대 ${leaderNow} / 대기실 ${followerAfter}`,
  )
  await follower.screenshot({ path: join(OUT, 'live-follower.jpg'), type: 'jpeg', quality: 82 })
  await followerCtx.close()

  // 되돌리기
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '처음으로 되돌리기' }).click()
  await page.waitForTimeout(500)
  check('처음으로 되돌린다', (await board.textContent()).includes('아직 시작 전입니다'))

  // ── 실제 시간을 명단에 되돌리기 ──────────────────────────────────
  console.log('\n[실제 시간 되돌리기]')
  const roster = await (await page.request.get(`${BASE}/api/events/${EVENT_ID}/students`)).json()
  const first = roster.students.find((row) => row.order_no === 1) ?? roster.students[0]
  const beforeSec = first.duration_sec

  // 개회 → 1분 30초 걸린 것처럼 표를 찍고 넘긴다 (실제로 기다릴 수는 없다)
  const T = Date.now() - 200_000
  await page.request.post(`${BASE}/api/events/${EVENT_ID}/live`, {
    data: { live: { index: 1, started_at: T, marks: [T, T + 90_000], updated_at: Date.now() } },
  })
  await page.goto(`${BASE}/events/${EVENT_ID}/live`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(900)
  const applyButton = page.getByRole('button', { name: '실제 시간을 명단에 반영' })
  check('실제 시간을 명단에 반영하는 단추가 뜬다', (await applyButton.count()) === 1)
  await applyButton.click()
  await page.waitForTimeout(1200)
  const afterRoster = await (await page.request.get(`${BASE}/api/events/${EVENT_ID}/students`)).json()
  const afterSec = afterRoster.students.find((row) => row.id === first.id).duration_sec
  check('명단의 연주 시간이 실제 시간으로 바뀐다', afterSec === 90, `${beforeSec}초 → ${afterSec}초`)

  // 이상한 시간은 받지 않는다
  const silly = await page.request.post(`${BASE}/api/events/${EVENT_ID}/durations`, {
    data: { updates: [{ student_id: first.id, duration_sec: 3 }] },
  })
  check('3초짜리는 명단에 넣지 않는다', silly.status() >= 400, String(silly.status()))

  // ── 아이 사진 여러 장 ────────────────────────────────────────────
  console.log('\n[아이 사진 여러 장]')
  const shot = async (hue) =>
    page.evaluate((h) => {
      const canvas = document.createElement('canvas')
      canvas.width = 300
      canvas.height = 300
      const ctx = canvas.getContext('2d')
      ctx.fillStyle = `hsl(${h}, 70%, 55%)`
      ctx.fillRect(0, 0, 300, 300)
      return canvas.toDataURL('image/jpeg', 0.8)
    }, hue)
  const madeAssets = []
  for (const hue of [10, 60, 120, 180, 240, 280, 320]) {
    const res = await page.request.post(`${BASE}/api/academy/assets`, {
      data: { kind: 'photo', label: `검사 사진 ${hue}`, url: await shot(hue) },
    })
    madeAssets.push((await res.json()).asset.id)
  }

  // 먼저 받아 주면 안 되는 것부터 — 뒤에 넣을 좋은 값을 덮어쓰지 않도록
  const unknown = await page.request.patch(`${BASE}/api/students/${first.id}`, {
    data: { photo_asset_ids: [madeAssets[0], '보관함에-없는-id'] },
  })
  check('보관함에 없는 사진은 거절한다', unknown.status() >= 400, String(unknown.status()))
  const tooMany = await page.request.patch(`${BASE}/api/students/${first.id}`, {
    data: { photo_asset_ids: madeAssets },
  })
  check('한 아이당 정해진 장수를 넘기면 거절한다', tooMany.status() >= 400, String(tooMany.status()))

  const multi = await page.request.patch(`${BASE}/api/students/${first.id}`, {
    data: { photo_asset_id: madeAssets[0], photo_asset_ids: madeAssets.slice(0, 3) },
  })
  check('아이 한 명에 사진 여러 장을 붙인다', multi.ok(), String(multi.status()))
  const storedIds = (await multi.json()).student?.photo_asset_ids ?? []
  check('붙인 사진이 그대로 남는다', storedIds.length === 3, `${storedIds.length}장`)

  const wide2 = await browser.newContext({ viewport: { width: 1400, height: 1000 } })
  const rosterPage = await wide2.newPage()
  rosterPage.on('pageerror', (error) => failures.push(`명단 화면 오류: ${error.message}`))
  await rosterPage.goto(`${BASE}/events/${EVENT_ID}?tab=roster`, { waitUntil: 'networkidle' })
  await rosterPage.waitForTimeout(600)
  const cellText = await rosterPage.locator('table tbody tr').first().textContent()
  check('명단에 사진 장수가 표시된다', cellText.includes('3'), cellText.slice(0, 40))

  await rosterPage.goto(`${BASE}/events/${EVENT_ID}/video`, { waitUntil: 'networkidle' })
  await rosterPage.waitForTimeout(2000)
  const storyText = await rosterPage.getByTestId('storyboard').textContent()
  check('영상 콘티가 여전히 만들어진다', /장면 \d+개/.test(storyText), storyText.slice(0, 40))
  // 사진 3장을 넣은 아이의 장면이 길어졌는가 (한 장에 1.4초 이상)
  const lengths = await rosterPage.evaluate(() =>
    Array.from(document.querySelectorAll('[data-testid="storyboard"] span.absolute')).map((node) => node.textContent),
  )
  check('사진이 여러 장인 장면은 더 오래 머문다', lengths.some((text) => Number(String(text).replace('초', '')) >= 4.2), lengths.slice(0, 6).join(' '))

  // ── 만들 구간 나누기 · 응원 메시지 ───────────────────────────────
  console.log('\n[구간 나누기 · 응원 메시지]')
  const rangeBox = rosterPage.getByTestId('record-range')
  check('만들 구간을 고르는 칸이 있다', (await rangeBox.count()) === 1)
  const wholeText = await rangeBox.textContent()
  await rangeBox.getByLabel('끝 장면').selectOption({ index: 2 })
  await rosterPage.waitForTimeout(400)
  const cutText = await rangeBox.textContent()
  check('구간을 좁히면 만들 길이가 줄어든다', cutText !== wholeText, cutText.match(/고른 구간[^·]*·[^전]*/)?.[0]?.trim() ?? '')
  check('구간을 고르면 단추 이름도 바뀐다', (await rosterPage.getByRole('button', { name: '고른 구간 만들기' }).count()) === 1)
  await rangeBox.getByRole('button', { name: '전체로 되돌리기' }).click()
  await rosterPage.waitForTimeout(300)

  // 응원 메시지 — 학부모 회신을 남기고 영상에 들어가는지 본다
  await rosterPage.request.post(`${BASE}/api/rsvp`, {
    data: {
      event_id: EVENT_ID,
      parent_name: '김서연 어머니',
      student_name: '김서연',
      headcount: 2,
      attending: true,
      message: '일 년 동안 정말 수고 많았어요.',
    },
  })
  await rosterPage.goto(`${BASE}/events/${EVENT_ID}/video`, { waitUntil: 'networkidle' })
  await rosterPage.waitForTimeout(2000)
  const withCheer = await rosterPage.getByTestId('storyboard').textContent()
  check('학부모 응원이 영상 장면으로 들어간다', withCheer.includes('응원'), withCheer.slice(-90))
  const cheerToggle = rosterPage.getByLabel('학부모 응원 메시지 넣기')
  check('응원 메시지 넣기 칸이 있다', (await cheerToggle.count()) === 1)
  await cheerToggle.uncheck()
  await rosterPage.waitForTimeout(1500)
  const withoutCheer = await rosterPage.getByTestId('storyboard').textContent()
  check('끄면 응원 장면이 빠진다', !withoutCheer.includes('응원'), withoutCheer.slice(-60))
  await cheerToggle.check()
  await rosterPage.waitForTimeout(1200)

  // 지난 행사에서 명단을 가져오면 사진도 따라오는가
  const carried = await rosterPage.request.post(`${BASE}/api/events/${EVENT_ID}/students/import`, {
    data: { from_event_id: EVENT_ID },
  })
  check('같은 행사에서는 명단을 가져오지 않는다', carried.status() >= 400, String(carried.status()))

  // ── 지난 행사에서 디자인 가져오기 ────────────────────────────────
  console.log('\n[디자인 가져오기]')
  await rosterPage.request.patch(`${BASE}/api/events/${EVENT_ID}`, {
    data: { design_theme: 'blossom-white', design_template: 'program-cover', design_copy: { subtitle: '작년 부제' } },
  })
  const born = await rosterPage.request.post(`${BASE}/api/events`, {
    data: { title: '제13회 정기 연주회', type: 'recital', event_at: '2027-09-18 15:00', venue: '구민회관' },
  })
  const newEvent = (await born.json()).event
  const imported = await rosterPage.request.post(`${BASE}/api/events/${newEvent.id}/design-import`, {
    data: { from_event_id: EVENT_ID },
  })
  const importedBody = await imported.json()
  check('지난 행사 디자인을 가져온다', imported.ok(), JSON.stringify(importedBody).slice(0, 90))
  check('테마가 그대로 따라온다', importedBody.event?.design_theme === 'blossom-white', importedBody.event?.design_theme ?? '')
  check('양식이 그대로 따라온다', importedBody.event?.design_template === 'program-cover', importedBody.event?.design_template ?? '')
  check('문구도 함께 따라온다', importedBody.event?.design_copy?.subtitle === '작년 부제')

  await rosterPage.goto(`${BASE}/events/${newEvent.id}/design`, { waitUntil: 'networkidle' })
  await rosterPage.waitForTimeout(700)
  check('디자인 화면에 가져오기 칸이 있다', (await rosterPage.getByTestId('design-import').count()) === 1)
  const sameAcademyOnly = await rosterPage.request.post(`${BASE}/api/events/${newEvent.id}/design-import`, {
    data: { from_event_id: newEvent.id },
  })
  check('같은 행사에서는 가져오지 않는다', sameAcademyOnly.status() >= 400)

  // 명단을 가져오면 아이 사진도 따라오는가 — 30명 얼굴을 해마다 다시 짝지을 이유가 없다
  const brought = await rosterPage.request.post(`${BASE}/api/events/${newEvent.id}/students/import`, {
    data: { from_event_id: EVENT_ID },
  })
  const broughtBody = await brought.json()
  check('지난 행사에서 명단을 가져온다', brought.ok(), String(brought.status()))
  check('아이 사진도 함께 따라온다', (broughtBody.with_photo ?? 0) > 0, `${broughtBody.with_photo}명`)
  const multiCarried = broughtBody.students.find((row) => (row.photo_asset_ids ?? []).length > 1)
  check('사진 여러 장도 그대로 따라온다', !!multiCarried, multiCarried ? `${multiCarried.photo_asset_ids.length}장` : '없음')
  await wide2.close()

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
