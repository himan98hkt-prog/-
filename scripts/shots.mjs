#!/usr/bin/env node
// 데모 데이터를 넣고 각 화면을 캡처한다 — 결과물 확인용 스크린샷 생성기.
//   node scripts/shots.mjs [시나리오: english|taekwondo|piano]

import { mkdirSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { startDevServer } from './lib/dev-server.mjs'
import { openContext } from './lib/browser.mjs'

const SCENARIO = process.argv[2] || 'english'
const PORT = 5197
const OUT = 'screenshots'
const PROFILE_DIR = join(tmpdir(), `academy-note-shots-${SCENARIO}`)

mkdirSync(OUT, { recursive: true })

const devServer = await startDevServer(PORT)
const kill = () => { devServer.close().catch(() => {}) }
process.on('SIGINT', () => { kill(); process.exit(130) })
const context = await openContext(PROFILE_DIR, {
  viewport: { width: 1280, height: 900 },
  deviceScaleFactor: 2
})
const page = context.pages()[0] || await context.newPage()

await page.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'domcontentloaded' })

// 첫 화면(체험·인증)과 시작 마법사도 판매 자료에 필요하므로 찍고 지나간다
await page.waitForSelector('.cover.activation, .app-rail button, .app-nav button')
if (await page.$('.cover.activation')) {
  await page.screenshot({ path: `${OUT}/00-첫화면.png` })
  console.log('  ✓ 00-첫화면.png')
  await page.click('[data-act="trial"]')
  await page.waitForSelector('.cover.wizard')
  await page.waitForTimeout(250)
  await page.screenshot({ path: `${OUT}/00-시작-1.png` })
  console.log('  ✓ 00-시작-1.png')
  await page.click('[data-wiz="mine"]')
  await page.waitForSelector('[data-wiz="name"]')
  await page.fill('[data-wiz="name"]', '아첼 음악학원')
  await page.waitForTimeout(200)
  await page.screenshot({ path: `${OUT}/00-시작-2.png` })
  console.log('  ✓ 00-시작-2.png')
  await page.click('[data-wiz="next"]')
  await page.waitForTimeout(250)
  await page.screenshot({ path: `${OUT}/00-시작-3.png` })
  console.log('  ✓ 00-시작-3.png')
  await page.click('[data-wiz="next"]')
  await page.waitForSelector('.setup')
  await page.waitForTimeout(300)
  if (await page.$('.coach')) {
    await page.screenshot({ path: `${OUT}/00-첫안내.png` })
    console.log('  ✓ 00-첫안내.png')
    await page.click('.coach .btn.ghost')
  }
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${OUT}/00-빈학원-오늘.png` })
  console.log('  ✓ 00-빈학원-오늘.png')
}

await page.evaluate(async (key) => {
  const { seedDemo } = await import('/src/data/seed.js')
  await seedDemo(key, { students: 36 })
  const { db } = await import('/src/data/db.js')
  const { generateKey, verifyKey, hashKey } = await import('/src/core/license.js')
  const res = verifyKey(generateKey('lite', 'A'))
  await db.settings.put({
    key: 'license',
    value: { key: res.key, key_hash: hashKey(res.key), plan: res.plan, product: res.product, activated_at: new Date().toISOString() }
  })
  await db.settings.put({ key: 'coachDone', value: true })
  await db.settings.put({ key: 'setupDone', value: true })
  await db.settings.delete('trialStartedAt')
  const owner = (await db.users.toArray()).find((u) => u.role === 'owner')
  if (owner) {
    const payload = JSON.stringify({ userId: owner.id, at: Date.now() })
    localStorage.setItem('academy-note:session', payload)
    sessionStorage.setItem('academy-note:session', payload)
  }
}, SCENARIO)

await page.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'load' })
await page.waitForSelector('.app-rail button, .app-nav button')

const VIEWS = [
  ['today', '00-오늘'],
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
  const { bookPairs } = await import('/src/core/books.js')
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
    customPairs: [...bookPairs(s), ...displayPairs(repo.getSetting('customFields', []), s.custom, 'report')],
    comment: '이번 달 수업 태도가 좋았고 진도도 계획대로 나갔습니다. 다음 달에는 발표 활동을 늘려 보겠습니다.',
    teacherName: repo.cache.users[1]?.name || ''
  })
  return canvas.toDataURL('image/png')
})
writeFileSync(`${OUT}/${SCENARIO}-10-학부모리포트.png`, Buffer.from(reportDataUrl.split(',')[1], 'base64'))
console.log(`  ✓ ${SCENARIO}-10-학부모리포트.png`)

// 원생 등록 창 · 도움말 · 학부모 문자 — 처음 쓰는 사람이 보게 될 장면들
await page.keyboard.press('Escape')
await page.click('[data-act="add-student"]')
await page.waitForSelector('.modal .more-fields')
await page.waitForTimeout(250)
await page.screenshot({ path: `${OUT}/${SCENARIO}-15-원생등록.png` })
console.log(`  ✓ ${SCENARIO}-15-원생등록.png`)
await page.keyboard.press('Escape')

await page.click('.app-rail [data-act="help"]')
await page.waitForSelector('.modal .howto')
await page.click('.modal .howto details:nth-child(1) summary')
await page.waitForTimeout(250)
await page.screenshot({ path: `${OUT}/${SCENARIO}-16-도움말.png` })
console.log(`  ✓ ${SCENARIO}-16-도움말.png`)
await page.keyboard.press('Escape')

await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  const { openBulkNotice } = await import('/src/ui/views/bulk-notice.js')
  openBulkNotice({ studentIds: repo.cache.students.slice(0, 6).map((s) => s.id), templateId: 'lesson', title: '학부모 안내 문자 (6명)' })
})
await page.waitForSelector('.modal textarea.msg')
await page.waitForTimeout(300)
await page.screenshot({ path: `${OUT}/${SCENARIO}-17-학부모문자.png` })
console.log(`  ✓ ${SCENARIO}-17-학부모문자.png`)
await page.keyboard.press('Escape')

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
await mobile.screenshot({ path: `${OUT}/${SCENARIO}-12-모바일-오늘.png` })
console.log(`  ✓ ${SCENARIO}-12-모바일-오늘.png`)

// 모바일 출결 — 실제로 가장 많이 쓰는 화면
await mobile.click('.app-nav button[data-view="attendance"]')
await mobile.waitForSelector('.att-cell, .toolbar-sub input[type=checkbox]')
// 샘플 학원은 평일에만 수업이 있다 — 주말에 찍으면 모든 반을 보이게 한다
if (!(await mobile.$('.att-cell'))) await mobile.uncheck('.toolbar-sub input[type=checkbox]')
await mobile.waitForSelector('.att-cell')
await mobile.waitForTimeout(400)
await mobile.screenshot({ path: `${OUT}/${SCENARIO}-13-모바일-출결.png` })
console.log(`  ✓ ${SCENARIO}-13-모바일-출결.png`)

// 모바일 '더보기' 시트
await mobile.click('.app-nav button[data-view="more"]')
await mobile.waitForSelector('.modal')
await mobile.waitForTimeout(300)
await mobile.screenshot({ path: `${OUT}/${SCENARIO}-14-모바일-더보기.png` })
console.log(`  ✓ ${SCENARIO}-14-모바일-더보기.png`)

await context.close()
await devServer.close()
