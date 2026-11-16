#!/usr/bin/env node
// 실사용 시나리오 스모크 테스트 — 완료 기준(DoD) 2·3·5·6번을 실제 브라우저에서 확인한다.
//
//   2) 계열이 다른 학원 2곳(영어학원/태권도장)을 custom 필드만 바꿔 운영
//   3) 로고·학원명·컬러 변경이 헤더/리포트/설치 아이콘에 반영
//   5) 백업 → 초기화 → 복원 왕복
//   6) 인증키(시디키) 게이트: 키 없이는 못 들어가고, 발급한 키로 열린다

import { spawn } from 'node:child_process'
import { existsSync, readdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'

const PORT = 5198
const PROFILE_DIR = join(tmpdir(), 'academy-note-smoke-profile')
const results = []
const KEY_INPUT = '.cover.activation [data-act="key"]'
const NAME_INPUT = '.cover.activation [data-act="name"]'
const SUBMIT = '.cover.activation [data-act="submit"]'

// detached: npx 가 vite 를 자식으로 또 띄우기 때문에, 프로세스 그룹째 종료해야
// 측정이 끝난 뒤 dev 서버가 고아 프로세스로 남지 않는다
// 인증 게이트를 매번 처음 상태에서 확인하려면 프로필(=IndexedDB)이 깨끗해야 한다
rmSync(PROFILE_DIR, { recursive: true, force: true })

const server = spawn('npx', ['vite', '--port', String(PORT), '--strictPort'], { stdio: ['ignore', 'pipe', 'pipe'], detached: true })
const kill = () => { try { process.kill(-server.pid, 'SIGTERM') } catch {} }
process.on('exit', kill)

await waitForServer(`http://localhost:${PORT}/lite.html`, 30000)
const context = await chromium.launchPersistentContext(PROFILE_DIR, {
  viewport: { width: 1280, height: 900 },
  ...(chromeExecutable() ? { executablePath: chromeExecutable() } : {})
})
const page = context.pages()[0] || await context.newPage()
page.setDefaultTimeout(60000)
page.on('pageerror', (e) => console.error('  [page error]', e.message))

await page.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'domcontentloaded' })

// ── 0. 첫 화면 (체험 · 구매 · 인증) ─────────────────────────
await page.waitForSelector('.cover.activation')
check('첫 화면: 키가 없으면 앱 대신 첫 화면이 뜬다', await page.isVisible(KEY_INPUT))
check('첫 화면: 인증 전에는 앱 화면(메뉴)이 없다', !(await page.$('.app-rail button, .app-nav button')))
check('첫 화면: "14일 무료로 써 보기"가 가장 큰 버튼으로 보인다', await page.isVisible('[data-act="trial"].primary'))
const buyHref = await page.getAttribute('.cover.activation [data-act="buy"]', 'href')
check('첫 화면: 구매하러 가는 길이 있다 (어디서 눌렀는지 주소에 남는다)', /^https?:\/\/.+from=app-activation/.test(buyHref || ''))
check('첫 화면: 무엇을 해 주는 프로그램인지 세 줄로 알려 준다', (await page.locator('.act-points li').count()) === 3)

await page.fill(KEY_INPUT, 'ZZZZ-ZZZZ-ZZZZ')
await page.click(SUBMIT)
const badMsg = await page.textContent('.activation-msg')
check('인증: 잘못된 키는 이유를 알려 주고 막는다', /검증번호|자리|문자/.test(badMsg || ''))

// 먼저 피아노 관리노트 발급 키가 그대로 열리는지 본다 (그쪽 앱을 고치지 않는 길)
const { generatePianoKey, pianoKeyForName } = await import('../src/core/license-piano.js')
const pianoNameKey = pianoKeyForName('아첼음악학원')
await page.fill(KEY_INPUT, pianoNameKey)
await page.click(SUBMIT)
const needName = await page.textContent('.activation-msg')
check('인증: 피아노 학원명 키는 학원명을 함께 넣으라고 안내한다', /학원명/.test(needName || ''))
check('인증: 안내와 함께 학원명 칸이 열린다', await page.isVisible(NAME_INPUT))

await page.fill(NAME_INPUT, '아첼음악학원')
await page.click(SUBMIT)
await page.waitForSelector('.cover.activation', { state: 'detached' })
check('인증: 피아노 학원명 키 + 학원명으로 앱이 열린다', !(await page.$('.cover.activation')))
await page.click('[data-wiz="mine"]')
const prefilled = await page.inputValue('[data-wiz="name"]')
check('인증: 키에 담긴 학원명이 처음 설정에 미리 채워진다', prefilled === '아첼음악학원')

// 이 세션은 다시 처음 상태로 돌려 두고, 실제 스모크는 Pro 통합키로 진행한다
await resetLicense(['pendingAcademyName'])

const pianoKey = generatePianoKey()
await page.fill(KEY_INPUT, pianoKey)
await page.click(SUBMIT)
await page.waitForSelector('.cover.activation', { state: 'detached' })
check('인증: 피아노 자기검증 키는 학원명 없이 바로 열린다', !(await page.$('.cover.activation')))
const pianoPlan = await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  return repo.getSetting('license')?.plan
})
check('인증: 피아노 키는 Pro 로 열린다', pianoPlan === 'pro')
await resetLicense()

const { generateKey } = await import('../src/core/license.js')

// 구매 메일을 통째로 붙여 넣는 경우 — 12자리를 골라 적지 않아도 된다
const mailKey = generateKey('lite', 'A')
await page.fill(KEY_INPUT, `김원장님, 구매해 주셔서 감사합니다.\n내 인증키\n${mailKey}\n눌러서 바로 시작하기\n주문 wc:1001:11:1`)
check('인증: 메일을 통째로 붙여 넣으면 키만 골라 칸에 넣는다', (await page.inputValue(KEY_INPUT)) === mailKey)
await page.click(SUBMIT)
await page.waitForSelector('.cover.activation', { state: 'detached' })
check('인증: 그렇게 골라낸 키로 열린다', !(await page.$('.cover.activation')))
await resetLicense()

// 구매 메일의 "눌러서 바로 시작하기" 로 들어온 경우 — 아무것도 입력하지 않는다
const linkKey = generateKey('pro', 'A')
await page.goto('about:blank')   // 메일에서 누르면 새 창으로 열린다 — 처음부터 불러오는 상황을 만든다
await page.goto(`http://localhost:${PORT}/lite.html#key=${linkKey}`, { waitUntil: 'load' })
await page.waitForSelector('.cover.wizard')
const linked = await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  return { key: repo.getSetting('license')?.key, hash: location.hash, gate: !!document.querySelector('.cover.activation') }
})
check('바로 시작 링크: 키를 입력하지 않아도 인증된 채로 열린다', linked.key === linkKey && !linked.gate)
check('바로 시작 링크: 인증 뒤 주소에서 키를 지운다', linked.hash === '')
await resetLicense()

// 첫 화면이 떠 있는 채로 같은 창에서 링크가 열린 경우 (설치한 앱이 링크를 받아 여는 상황)
const linkKey2 = generateKey('lite', 'A')
await page.evaluate((k) => { location.hash = `key=${k}` }, linkKey2)
await page.waitForSelector('.cover.activation', { state: 'detached' })
check('바로 시작 링크: 첫 화면이 떠 있는 채로 링크가 열려도 인증된다',
  await page.evaluate(async (k) => (await import('/src/data/repo.js')).getSetting('license')?.key === k && location.hash === '', linkKey2))
await resetLicense()

const proKey = generateKey('pro', 'A')   // 통합키(A) — 학원 관리노트 방식
await page.fill(KEY_INPUT, proKey)
await page.click(SUBMIT)
await page.waitForSelector('.cover.activation', { state: 'detached' })
check('인증: 발급한 통합키를 넣으면 앱이 열린다', !(await page.$('.cover.activation')))

// 인증 직후에는 처음 설정이 이어진다 (시작 방법 → 학원 이름·종류 → 색)
const asked = await runWizard('스모크 학원')
check('처음 설정: 세 번 답하면 앱이 준비된다', await page.isVisible('.app-rail button, .app-nav button'))
check('처음 설정: 혼자 쓰는 원장에게는 잠금 번호를 묻지 않는다 (Pro 여도)', asked.pin === false)
check('인증: Pro 키는 학원 이름 옆에 Pro 로 표시된다', (await page.textContent('.app-header .sub'))?.includes('Pro'))
const fresh = await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  return { category: repo.getSetting('category'), fields: (repo.getSetting('customFields') || []).map((f) => f.key), subjects: repo.cache.subjects.map((s) => s.name) }
})
check('처음 설정: 고른 종류(피아노·음악)에 맞춰 과목과 기록 항목이 준비된다',
  fresh.category === '음악' && fresh.subjects.includes('피아노') && fresh.fields.includes('contest'))

// 처음 들어온 선생님에게 뜨는 안내 — 확인하고 닫는다
await page.waitForSelector('.coach .box')
const coachText = await page.textContent('.coach .box')
check('첫 사용 안내: 앱을 처음 열면 3장짜리 안내가 뜬다', /오늘|출석|문자/.test(coachText || ''))
for (let i = 0; i < 3; i++) {
  await page.click('.coach .btn.primary')
  await page.waitForTimeout(120)
}
check('첫 사용 안내: 끝까지 넘기면 사라진다', !(await page.$('.coach')))

// 빈 학원에서는 "다음에 뭘 할지" 를 짚어 준다
await page.waitForSelector('.setup')
const guide = await page.evaluate(() => ({
  steps: document.querySelectorAll('.setup-steps li').length,
  next: document.querySelector('.setup-steps li.next')?.dataset.step,
  cta: document.querySelector('.setup-steps li.next .btn')?.textContent
}))
check('시작 가이드: 빈 학원에는 네 단계 안내가 뜨고 첫 단계(반 만들기)를 짚는다', guide.steps === 4 && guide.next === 'class' && /반/.test(guide.cta || ''))
await page.click('.setup-steps li.next .btn')
await page.waitForFunction(() => location.hash === '#timetable')
check('시작 가이드: 버튼을 누르면 그 일을 하는 화면으로 간다', await page.isVisible('[data-act="add-class"]'))

// ── 1. 영어학원 시나리오 ────────────────────────────────────
await seed('english')
await reload()
let info = await snapshot()
check('영어학원: 헤더에 학원명 반영', info.headerTitle === '아라 잉글리시')
check('영어학원: 브랜드 컬러가 CSS 변수에 반영', info.brand === '#2c4a7c')
check('영어학원: custom 필드는 어학 세트', info.fieldKeys.join() === 'level,level_test,book')
check('영어학원: 원생 목록 렌더', info.students > 0)

// 출결 체크(첫 원생 탭)
await goTo('attendance')
await page.waitForSelector('.att-cell')
const before = await page.getAttribute('.att-cell', 'data-status')
await page.click('.att-cell')
await page.waitForFunction((b) => document.querySelector('.att-cell')?.dataset.status !== b, before)
check('출결: 탭 한 번으로 상태가 바뀐다', (await page.getAttribute('.att-cell', 'data-status')) !== before)

// 리포트 이미지 생성
const report = await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  const { drawReportCard } = await import('/src/ui/report.js')
  const { summarize } = await import('/src/core/attendance.js')
  const { displayPairs } = await import('/src/core/customfields.js')
  const s = repo.cache.students[0]
  const att = await repo.attendanceOfStudentRange(s.id, '2000-01-01', '2100-01-01')
  const base = {
    student: s, month: '2026-08', attendance: summarize(att),
    payment: { amount: 180000, status: '완납' },
    customPairs: displayPairs(repo.getSetting('customFields', []), s.custom, 'report'),
    comment: '이번 달 수업 태도가 좋았습니다.', teacherName: '김강사'
  }
  const canvas = await drawReportCard(base)
  // 학습 항목이 늘어나면 리포트 높이도 늘어나야 한다(잘림 방지)
  const tall = await drawReportCard({
    ...base,
    customPairs: Array.from({ length: 8 }, (_, i) => ({ label: `항목 ${i + 1}`, value: `값 ${i + 1}` }))
  })
  return { w: canvas.width, h: canvas.height, tallH: tall.height, bytes: canvas.toDataURL('image/png').length }
})
check('리포트: Canvas 이미지 생성', report.w === 760 && report.h > 700 && report.bytes > 20000)
check('리포트: 학습 항목이 많아지면 높이가 늘어난다 (내용 잘림 방지)', report.tallH > report.h)

// ── 2. 브랜딩 변경 반영 ─────────────────────────────────────
const branded = await page.evaluate(async () => {
  const { saveBranding } = await import('/src/ui/branding.js')
  await saveBranding({ name: '테스트 학원', brand_color: '#a63a3a' })
  const manifestHref = document.querySelector('link[rel=manifest]')?.href || ''
  const manifest = manifestHref.startsWith('blob:') ? await (await fetch(manifestHref)).json() : null
  return {
    header: document.querySelector('.app-header .title')?.textContent,
    brand: getComputedStyle(document.documentElement).getPropertyValue('--brand').trim(),
    title: document.title,
    manifestName: manifest?.name,
    manifestColor: manifest?.theme_color,
    iconIsPng: (manifest?.icons?.[0]?.src || '').startsWith('data:image/png')
  }
})
check('브랜딩: 헤더 학원명 변경', branded.header === '테스트 학원')
check('브랜딩: --brand CSS 변수 변경', branded.brand === '#a63a3a')
check('브랜딩: 문서 제목 변경', branded.title === '테스트 학원')
check('브랜딩: 동적 manifest 에 학원명·컬러 반영', branded.manifestName === '테스트 학원' && branded.manifestColor === '#a63a3a')
check('브랜딩: 로고 미업로드 시 이니셜 아이콘 생성', branded.iconIsPng)

// ── 3. 백업 → 초기화 → 복원 ────────────────────────────────
const roundTrip = await page.evaluate(async () => {
  const { db } = await import('/src/data/db.js')
  const { buildBackup, parseBackup, BACKUP_TABLES } = await import('/src/core/backup.js')
  const { restoreFromBackup } = await import('/src/data/restore.js')
  const tables = {}
  for (const t of BACKUP_TABLES) tables[t] = db[t] ? await db[t].toArray() : []
  const json = JSON.stringify(buildBackup(tables, { plan: 'lite', academy: '테스트 학원' }))
  const beforeCounts = { students: tables.students.length, attendance: tables.attendance.length }

  // 자료가 날아간 상황을 흉내 낸다 (인증은 기기에 남아 있는 상태)
  await db.transaction('rw', [db.students, db.attendance, db.payments], async () => {
    await Promise.all([db.students.clear(), db.attendance.clear(), db.payments.clear()])
  })
  const emptied = await db.students.count()

  await restoreFromBackup(parseBackup(json))
  return {
    beforeCounts,
    emptied,
    after: { students: await db.students.count(), attendance: await db.attendance.count() },
    licenseKept: !!(await db.settings.get('license'))
  }
})
check('백업: 복원 후에도 이 기기 인증은 그대로 유지된다', roundTrip.licenseKept === true)
check('백업: 초기화 후 복원으로 원생/출결이 그대로 돌아온다',
  roundTrip.emptied === 0 &&
  roundTrip.after.students === roundTrip.beforeCounts.students &&
  roundTrip.after.attendance === roundTrip.beforeCounts.attendance)

// ── 4. 인증 상태 유지 / 백업에 키가 새지 않는지 ─────────────
const license = await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  const { db } = await import('/src/data/db.js')
  const { buildBackup, BACKUP_TABLES } = await import('/src/core/backup.js')
  const { verifyKey, generateKey } = await import('/src/core/license.js')
  const tables = {}
  for (const t of BACKUP_TABLES) tables[t] = db[t] ? await db[t].toArray() : []
  const backup = buildBackup(tables, { plan: repo.getPlan() })
  const pianoOnly = generateKey('lite', 'K')
  return {
    plan: repo.getPlan(),
    stored: repo.getSetting('license')?.plan,
    product: repo.getSetting('license')?.product,
    device: repo.getSetting('license')?.device,
    backupHasKey: JSON.stringify(backup).includes(repo.getSetting('license')?.key || 'x'),
    pianoRejected: verifyKey(pianoOnly).ok,
    pianoReason: verifyKey(pianoOnly).reason
  }
})
check('인증: 데모 시드·초기화 뒤에도 인증이 유지된다', license.plan === 'pro' && license.stored === 'pro')
check('인증: 통합키(A)로 인식된다', license.product === 'A')
check('인증: 기기번호가 함께 저장된다', !!license.device)
check('인증: 백업 파일에 인증키가 들어가지 않는다', license.backupHasKey === false)
check('인증: 피아노 전용 키(K)는 이 제품에서 거부', license.pianoRejected === false && /피아노/.test(license.pianoReason || ''))

// Pro 플랜에서 동기화 설정 UI 노출
await reload()
await goTo('settings')
await page.waitForSelector('details')
const hasProSection = await page.evaluate(() =>
  [...document.querySelectorAll('details summary')].some((s) => s.textContent.includes('Pro 동기화')))
check('Pro: 설정에 동기화 섹션이 나타난다', hasProSection)

// ── 4-2. 원장 반복업무 기능 ─────────────────────────────────
await goTo('today')
await page.waitForSelector('.todo-item, .todo-empty')
const todo = await page.evaluate(() => ({
  items: [...document.querySelectorAll('.todo-item b')].map((b) => b.textContent),
  hasAction: !!document.querySelector('.todo-item .btn')
}))
check('오늘: 할 일 목록이 그려진다', todo.items.length > 0 && todo.hasAction)

const bulk = await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  const { openBulkNotice } = await import('/src/ui/views/bulk-notice.js')
  openBulkNotice({ studentIds: repo.cache.students.slice(0, 5).map((s) => s.id), templateId: 'payment', amounts: {} })
  await new Promise((r) => setTimeout(r, 50))
  return {
    rows: document.querySelectorAll('.modal .pick-row').length,
    preview: document.querySelector('.modal textarea.msg')?.value || '',
    actions: [...document.querySelectorAll('.modal-actions button')].map((b) => b.textContent)
  }
})
check('일괄 안내: 대상 목록과 문구가 만들어진다', bulk.rows === 5 && bulk.preview.length > 10)
check('일괄 안내: 번호 복사·CSV·문자앱 버튼 제공', bulk.actions.join().includes('번호만 복사') && bulk.actions.join().includes('CSV'))
await page.keyboard.press('Escape')

const billing = await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  const { toMonth, toYmd, addMonths } = await import('/src/core/date.js')
  const month = addMonths(toMonth(toYmd()), 1)
  await repo.setSetting('billing', { sibling: { enabled: true, type: 'percent', value: 10 }, roundUnit: 100, dueDay: 10 })
  const plain = await repo.previewMonthlyBills(month)
  await repo.setSetting('billing', null)
  const noDiscount = await repo.previewMonthlyBills(month)
  const withSibling = plain.rows.filter((r) => r.bill.discount > 0)
  return {
    count: plain.rows.length,
    discounted: withSibling.length,
    sample: withSibling[0]?.bill?.lines?.at(-1)?.label || '',
    cheaper: plain.total < noDiscount.total,
    saved: 0
  }
})
check('청구: 미리보기가 재원생별 금액을 계산한다', billing.count > 0)
check('청구: 형제 할인이 자동 반영된다', billing.discounted > 0 && billing.cheaper && /형제 할인/.test(billing.sample))

const csv = await page.evaluate(async () => {
  const { parseStudentTable } = await import('/src/core/csv.js')
  const repo = await import('/src/data/repo.js')
  const text = '이름\t학년\t학부모 연락처\n스모크학생\t초3\t010-9999-8888\n' + repo.cache.students[0].name + '\t초4\t' + (repo.cache.students[0].parent_phone || '')
  const res = parseStudentTable(text, { existing: repo.cache.students })
  return { rows: res.rows.length, first: res.rows[0], dup: res.rows[1]?.duplicate }
})
check('엑셀 가져오기: 붙여넣은 표에서 원생을 인식한다', csv.rows === 2 && csv.first.name === '스모크학생' && csv.first.parent_phone === '010-9999-8888')
check('엑셀 가져오기: 이미 등록된 원생을 중복으로 표시한다', csv.dup === true)

const register = await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  const { monthlyRegister } = await import('/src/core/register.js')
  const { toMonth, toYmd } = await import('/src/core/date.js')
  const cls = repo.cache.classes[0]
  const month = toMonth(toYmd())
  const roster = repo.rosterOf(cls.id, toYmd())
  const records = await repo.attendanceOfClassMonth(cls.id, month)
  const t = monthlyRegister({ month, roster, records })
  return { headers: t.headers.length, rows: t.rows.length, tail: t.rows[0]?.slice(-3) }
})
check('출석부: 월간 표(원생 × 날짜 + 출석률)를 만든다', register.rows > 0 && register.headers > 4 && String(register.tail?.[2]).includes('%'))

const receipt = await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  const { drawReceipt } = await import('/src/ui/receipt.js')
  const { toMonth, toYmd } = await import('/src/core/date.js')
  const pays = await repo.paymentsOfMonth(toMonth(toYmd()))
  const paid = pays.find((p) => p.paid > 0) || pays[0]
  const canvas = await drawReceipt({ payment: paid, student: repo.cache.studentById.get(paid.student_id) })
  return { w: canvas.width, h: canvas.height, bytes: canvas.toDataURL('image/png').length }
})
check('영수증: 수납 영수증 이미지를 생성한다', receipt.w === 700 && receipt.h > 400 && receipt.bytes > 10000)

// ── 5. 태권도장 시나리오 (계열 전환) ────────────────────────
await seed('taekwondo')
await reload()
info = await snapshot()
check('태권도장: 학원명 전환', info.headerTitle === '성무 태권도')
check('태권도장: 브랜드 컬러 전환', info.brand === '#a63a3a')
check('태권도장: custom 필드가 체육 세트로 교체', info.fieldKeys.join() === 'belt,promo_at,goal')
check('태권도장: 원생 카드 항목이 띠 급수로 표시', info.samplePairs.some((p) => p.label === '띠 급수' && p.value))

// ── 6. 피아노학원 — 교재·진도 ───────────────────────────────
await seed('piano')
await reload()
info = await snapshot()
check('피아노학원: 기록 항목이 음악 세트로 준비된다', info.fieldKeys.join() === 'grade,contest,practice')
await goTo('students')
await page.waitForSelector('.student-row')
await page.click('.student-row')
await page.waitForSelector('.modal .books')
check('교재·진도: 원생 카드에 지금 하는 교재와 진도가 보인다', (await page.locator('.modal .book-row').count()) >= 2)

await page.fill('.modal [data-book="new-title"]', '스모크 교재')
await page.fill('.modal [data-book="new-progress"]', '7쪽')
await page.click('.modal [data-book="add"]')
await page.waitForSelector('.modal input[data-book="스모크 교재"]')
check('교재·진도: 교재를 추가하면 목록에 바로 나타난다', (await page.inputValue('.modal input[data-book="스모크 교재"]')) === '7쪽')

// 진도 칸을 고치고 다른 곳을 누르면 저장된다 (저장 버튼이 따로 없다)
await page.fill('.modal input[data-book="스모크 교재"]', '9쪽')
await page.locator('.modal input[data-book="스모크 교재"]').blur()
await page.waitForFunction(async () => {
  const repo = await import('/src/data/repo.js')
  const { booksOf } = await import('/src/core/books.js')
  return repo.cache.students.some((s) => booksOf(s).some((b) => b.title === '스모크 교재' && b.progress === '9쪽'))
})
const book = await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  const { booksOf, bookPairs, progressLine } = await import('/src/core/books.js')
  const { db } = await import('/src/data/db.js')
  const s = repo.cache.students.find((x) => booksOf(x).some((b) => b.title === '스모크 교재'))
  const stored = await db.students.get(s.id)
  const b = booksOf(stored).find((x) => x.title === '스모크 교재')
  return { id: s.id, progress: b.progress, log: b.log.map((l) => l.progress), pairs: bookPairs(stored).map((p) => `${p.label}=${p.value}`), line: progressLine(stored) }
})
check('교재·진도: 고친 진도가 기기에 저장되고 기록이 남는다', book.progress === '9쪽' && book.log.at(-1) === '9쪽')
check('교재·진도: 학부모 리포트에 실릴 항목에 들어간다', book.pairs.includes('스모크 교재=9쪽'))

// 새 원생 등록 창 — 아무 반도 골라져 있지 않아야 한다 (예전에는 모든 반이 골라진 채로 열렸다)
await page.keyboard.press('Escape')
await page.click('[data-act="add-student"]')
await page.waitForSelector('.modal .more-fields')
const newForm = await page.evaluate(() => ({
  chips: document.querySelectorAll('.modal .field .chip').length,
  picked: document.querySelectorAll('.modal .field .chip.active').length,
  moreOpen: document.querySelector('.modal .more-fields')?.open
}))
check('원생 등록: 새 원생은 반이 하나도 골라지지 않은 채로 시작한다', newForm.chips > 0 && newForm.picked === 0)
check('원생 등록: 처음에는 이름·학부모 번호·반만 보이고 나머지는 접혀 있다', newForm.moreOpen === false)
await page.fill('.modal .field input[type=text]', '스모크 신입')
await page.click('.modal-actions button:has-text("저장")')
await page.waitForFunction(() => !document.querySelector('.modal'))
const newbie = await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  const s = repo.cache.students.find((x) => x.name === '스모크 신입')
  return { found: !!s, classes: s ? repo.studentClasses(s.id).length : -1 }
})
check('원생 등록: 이름만 넣고 저장해도 등록되고, 고르지 않은 반에는 들어가지 않는다', newbie.found && newbie.classes === 0)
await page.fill('.searchbox input', '')
await page.click('.student-row')
await page.waitForSelector('.modal .books')

// 원생 정보를 고쳐 저장해도 진도가 지워지지 않아야 한다
await page.click('.modal-actions button:has-text("정보 고치기")')
await page.waitForSelector('.modal .more-fields')
await page.click('.modal-actions button:has-text("저장")')
await page.waitForFunction(() => !document.querySelector('.modal'))
const kept = await page.evaluate(async (id) => {
  const { db } = await import('/src/data/db.js')
  const { booksOf } = await import('/src/core/books.js')
  return booksOf(await db.students.get(id)).some((b) => b.title === '스모크 교재' && b.progress === '9쪽')
}, book.id)
check('교재·진도: 원생 정보를 고쳐 저장해도 진도는 그대로 남는다', kept)

const lesson = await page.evaluate(async (id) => {
  const repo = await import('/src/data/repo.js')
  const { openNoticeModal } = await import('/src/ui/views/notice-modal.js')
  await openNoticeModal({ student: repo.cache.studentById.get(id), templateId: 'lesson' })
  return document.querySelector('.modal textarea')?.value || ''
}, book.id)
check('교재·진도: 레슨 안내 문자에 진도가 채워진다', lesson.includes('스모크 교재 9쪽') && !lesson.includes('{진도}'))
await page.keyboard.press('Escape')

await goTo('attendance')
await page.waitForSelector('.att-cell')
check('교재·진도: 출결 화면의 이름 아래에 진도가 보인다',
  await page.evaluate(() => [...document.querySelectorAll('.att-cell .pg')].some((el) => el.textContent.trim().length > 0)))

// ── 7. 처음 온 사람 — 체험 → 샘플 학원 → 구매 → 내 학원 ────
console.log('\n▶ 처음 상태로 되돌려 체험 흐름 확인')
await page.evaluate(async () => {
  const { clearAll } = await import('/src/data/seed.js')
  await clearAll({ keepDeviceSettings: false })
  localStorage.clear()
  sessionStorage.clear()
})
await page.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'load' })
await page.waitForSelector('.cover.activation')
await page.click('[data-act="trial"]')
await page.waitForSelector('.cover.wizard')
check('체험: 키 없이 "무료로 써 보기"만 눌러 시작한다', await page.isVisible('[data-wiz="sample"]'))
await page.click('[data-wiz="sample"]')
await page.click('[data-wiz="next"]')
await page.waitForSelector('[data-bar="demo"]', { timeout: 60000 })
const demo = await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  return {
    students: repo.cache.students.length,
    academy: document.querySelector('.app-header .title')?.textContent,
    pinAsked: !!document.querySelector('.pin-pad'),
    trialBar: document.querySelector('[data-bar="trial"]')?.textContent || '',
    buy: document.querySelector('[data-bar="trial"] [data-act="buy"]')?.getAttribute('href') || '',
    setup: !!document.querySelector('.setup')
  }
})
check('샘플 학원: 원생이 들어 있는 연습용 학원이 바로 열린다', demo.students === 24 && demo.academy === '아첼 음악학원')
check('샘플 학원: 잠금 번호를 묻지 않고 들어간다', demo.pinAsked === false)
check('샘플 학원: 샘플 자료임을 맨 위에서 알려 준다', await page.isVisible('[data-bar="demo"] [data-act="leave-demo"]'))
check('샘플 학원: 시작 가이드는 띄우지 않는다 (이미 자료가 있다)', demo.setup === false)
check('체험: 며칠 남았는지와 구매 버튼이 항상 보인다', /14일/.test(demo.trialBar) && /from=app-trial/.test(demo.buy))
if (await page.$('.coach')) await page.click('.coach .btn.ghost')

// 체험 중에 구매한 사람 — 앱 안에서 키를 넣으면 자료 그대로 정식이 된다
await page.click('[data-act="enter-key"]')
await page.waitForSelector('.modal [data-act="key"]')
await page.fill('.modal [data-act="key"]', generateKey('lite', 'A'))
await page.click('.modal [data-act="submit"]')
await page.waitForSelector('[data-bar="trial"]', { state: 'detached' })
const upgraded = await page.evaluate(async () => {
  const repo = await import('/src/data/repo.js')
  return { badge: document.querySelector('.app-header .sub .badge')?.textContent, students: repo.cache.students.length, plan: repo.getSetting('license')?.plan }
})
check('구매 후: 앱 안에서 키를 넣으면 체험 안내가 사라지고 정식으로 바뀐다', upgraded.badge === 'Lite' && upgraded.plan === 'lite')
check('구매 후: 넣어 둔 자료는 그대로 남는다', upgraded.students === 24)

// 샘플을 다 본 뒤 — 샘플을 지우고 내 학원으로
await page.click('[data-act="leave-demo"]')
await page.click('.modal-actions .btn.primary')
await page.waitForSelector('.cover.wizard [data-wiz="name"]', { timeout: 60000 })
const afterDemo = await page.evaluate(async () => {
  const { db } = await import('/src/data/db.js')
  return {
    students: await db.students.count(),
    license: !!(await db.settings.get('license')),
    intro: !!document.querySelector('[data-wiz="sample"]')
  }
})
check('내 학원으로: 샘플 자료가 모두 지워진다', afterDemo.students === 0)
check('내 학원으로: 인증은 그대로 유지된다', afterDemo.license === true)
check('내 학원으로: "어떻게 시작할까요"를 다시 묻지 않고 이름부터 받는다', afterDemo.intro === false)
await page.fill('[data-wiz="name"]', '우리 피아노')
await page.click('[data-wiz="next"]')
await page.waitForSelector('.swatches')
await page.click('[data-wiz="next"]')
await page.waitForSelector('.setup')
check('내 학원으로: 빈 학원이 열리고 시작 가이드가 안내한다',
  (await page.textContent('.app-header .title')) === '우리 피아노' && !(await page.$('[data-bar="demo"]')))

// 체험이 끝난 사람 — 자료는 남아 있고, 구매 안내가 먼저 보인다
await page.evaluate(async () => {
  const { db } = await import('/src/data/db.js')
  await db.settings.delete('license')
  await db.settings.put({ key: 'trialStartedAt', value: new Date(Date.now() - 20 * 86400000).toISOString() })
})
await page.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'load' })
await page.waitForSelector('.cover.activation')
const expired = await page.evaluate(() => ({
  text: document.querySelector('.cover.activation .callout')?.textContent || '',
  trialBtn: !!document.querySelector('[data-act="trial"]'),
  buyPrimary: !!document.querySelector('.cover.activation a[data-act="buy"].primary')
}))
check('체험 종료: 다시 체험할 수는 없고, 자료가 남아 있음을 알려 준다', !expired.trialBtn && /그대로/.test(expired.text))
check('체험 종료: 구매하러 가는 버튼이 가장 크게 보인다', expired.buyPrimary)

// ── 정리 ────────────────────────────────────────────────────
const failed = results.filter((r) => !r.ok)
console.log(`\n─ 스모크 결과 ${'─'.repeat(40)}`)
for (const r of results) console.log(`  ${r.ok ? '✅' : '❌'} ${r.name}`)
console.log(`─${'─'.repeat(52)}`)
console.log(`  ${failed.length ? `${failed.length}건 실패` : `${results.length}건 전부 통과`}\n`)

await context.close()
kill()
process.exit(failed.length ? 1 : 0)

// ── 헬퍼 ────────────────────────────────────────────────────
function check(name, ok) {
  results.push({ name, ok: !!ok })
  console.log(`  ${ok ? '✅' : '❌'} ${name}`)
}

/**
 * 실제 사용자처럼 메뉴를 눌러 화면을 옮긴다.
 * 넓은 화면이면 왼쪽 사이드바, 좁으면 하단 탭(없으면 '더보기' 시트)을 쓴다.
 */
async function goTo(view) {
  const rail = await page.$(`.app-rail button[data-view="${view}"]`)
  if (rail && await rail.isVisible()) { await rail.click() } else {
    const tab = await page.$(`.app-nav button[data-view="${view}"]`)
    if (tab) await tab.click()
    else {
      await page.click('.app-nav button[data-view="more"]')
      await page.click(`.modal .list-row:has-text("${NAV_LABEL[view] || view}")`)
    }
  }
  await page.waitForFunction((v) => location.hash === `#${v}`, view)
  await page.waitForTimeout(150)
}

const NAV_LABEL = {
  today: '오늘', attendance: '출결', students: '원생', payments: '수납',
  timetable: '시간표', counsel: '상담', expenses: '지출', dashboard: '현황', settings: '설정'
}

/** 처음 설정(내 학원으로 시작)을 끝까지 진행한다. 잠금 번호를 물었는지 돌려준다. */
async function runWizard(name) {
  if (!(await page.$('.cover.wizard'))) return { pin: false }
  await page.click('[data-wiz="mine"]')
  await page.fill('[data-wiz="name"]', name)
  await page.click('[data-wiz="next"]')   // 이름·종류 → 색
  await page.waitForSelector('.swatches')
  await page.click('[data-wiz="next"]')   // 시작하기
  await page.waitForSelector('.pin-pad, .app-rail button, .app-nav button')
  const pin = !!(await page.$('.pin-pad'))
  if (pin) for (let i = 0; i < 4; i++) await page.click('.pin-pad button:has-text("0")')
  await page.waitForSelector('.app-rail button, .app-nav button')
  return { pin }
}

/** 인증만 지우고 첫 화면으로 돌아간다 (자료는 그대로) */
async function resetLicense(alsoDelete = []) {
  await page.evaluate(async (keys) => {
    const { db } = await import('/src/data/db.js')
    await db.settings.bulkDelete(['license', ...keys])
  }, alsoDelete)
  await page.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'load' })
  await page.waitForSelector('.cover.activation')
}

async function seed(scenario) {
  console.log(`\n▶ 데모 시드: ${scenario}`)
  await page.evaluate(async (key) => {
    const { seedDemo } = await import('/src/data/seed.js')
    await seedDemo(key, { students: 30 })
    const { db } = await import('/src/data/db.js')
    const owner = (await db.users.toArray()).find((u) => u.role === 'owner')
    // 시드로 사용자 id 가 바뀌므로 세션도 새 원장으로 갈아 끼운다
    // (Pro 는 sessionStorage 를 먼저 보기 때문에 둘 다 써 준다)
    await db.settings.put({ key: 'coachDone', value: true })
    await db.settings.put({ key: 'setupDone', value: true })
    if (owner) {
      const payload = JSON.stringify({ userId: owner.id, at: Date.now() })
      sessionStorage.setItem('academy-note:session', payload)
      localStorage.setItem('academy-note:session', payload)
    }
  }, scenario)
}

async function reload() {
  await page.goto(`http://localhost:${PORT}/lite.html`, { waitUntil: 'load' })
  await page.waitForSelector('.app-rail button, .app-nav button')
}

function snapshot() {
  return page.evaluate(async () => {
    const repo = await import('/src/data/repo.js')
    const { displayPairs } = await import('/src/core/customfields.js')
    const fields = repo.getSetting('customFields', [])
    const student = repo.cache.students.find((s) => Object.keys(s.custom || {}).length) || repo.cache.students[0]
    return {
      headerTitle: document.querySelector('.app-header .title')?.textContent,
      brand: getComputedStyle(document.documentElement).getPropertyValue('--brand').trim(),
      fieldKeys: fields.map((f) => f.key),
      students: repo.cache.students.length,
      samplePairs: displayPairs(fields, student?.custom || {}, 'card')
    }
  })
}

function chromeExecutable() {
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH
  if (!root || !existsSync(root)) return null
  const dir = readdirSync(root).filter((d) => /^chromium-\d+$/.test(d)).sort().pop()
  if (!dir) return null
  // 플레이라이트 버전에 따라 폴더 이름이 chrome-linux / chrome-linux64 로 갈린다
  const bin = ['chrome-linux', 'chrome-linux64'].map((d) => `${root}/${dir}/${d}/chrome`).find((p) => existsSync(p))
  return bin || null
}

async function waitForServer(url, timeoutMs) {
  const until = Date.now() + timeoutMs
  for (;;) {
    try { if ((await fetch(url)).ok) return } catch {}
    if (Date.now() > until) throw new Error(`개발 서버가 뜨지 않았습니다: ${url}`)
    await new Promise((r) => setTimeout(r, 300))
  }
}
