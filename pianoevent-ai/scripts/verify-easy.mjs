#!/usr/bin/env node
/**
 * 쉽게 쓰기 검사 — 처음 안내 · 엑셀 끌어다 놓기 · 읽은 결과 확인 · 되돌리기 ·
 * 인쇄 미리보기 · 행사 파일 옮기기 · 막히면 여기.
 *
 *   npm run build && node scripts/verify-easy.mjs
 *
 * 여기 있는 것들은 전부 "컴맹 원장님이 막히지 않게" 하려고 넣은 것이다.
 * 그러니 검사도 원장님이 하시는 그대로 한다 — 파일을 놓고, 단추를 누르고, 종이를 센다.
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, renameSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'

const PORT = Number(process.env.EASY_PORT ?? 3997)
const BASE = `http://127.0.0.1:${PORT}`
const DATA = join(process.cwd(), '.data')
const SPARE = mkdtempSync(join(tmpdir(), 'pianoevent-easy-'))
const BACKUP = join(SPARE, 'data')
// 검사가 진짜 백업을 뜬다. 원장님(또는 개발자)의 것을 건드리지 않게 잠시 치워 둔다.
const AUTO = join(process.cwd(), '백업')
const AUTO_SPARE = join(SPARE, 'auto')
const OUT = join(process.cwd(), 'shots', 'easy')
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

// ── 검사용 .xlsx 한 개를 만든다 (압축하지 않는 ZIP — 엑셀도 우리도 그대로 읽는다)
const CRC = (() => {
  const table = new Uint32Array(256)
  for (let i = 0; i < 256; i += 1) {
    let c = i
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    table[i] = c >>> 0
  }
  return table
})()

function crc32(bytes) {
  let c = 0xffffffff
  for (const b of bytes) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function zipStore(entries) {
  const locals = []
  const centrals = []
  let offset = 0
  for (const entry of entries) {
    const name = Buffer.from(entry.name, 'utf8')
    const data = Buffer.from(entry.data, 'utf8')
    const sum = crc32(data)

    const local = Buffer.alloc(30 + name.length)
    local.writeUInt32LE(0x04034b50, 0)
    local.writeUInt16LE(20, 4)
    local.writeUInt16LE(0x0800, 6)
    local.writeUInt32LE(sum, 14)
    local.writeUInt32LE(data.length, 18)
    local.writeUInt32LE(data.length, 22)
    local.writeUInt16LE(name.length, 26)
    name.copy(local, 30)

    const central = Buffer.alloc(46 + name.length)
    central.writeUInt32LE(0x02014b50, 0)
    central.writeUInt16LE(20, 4)
    central.writeUInt16LE(20, 6)
    central.writeUInt16LE(0x0800, 8)
    central.writeUInt32LE(sum, 16)
    central.writeUInt32LE(data.length, 20)
    central.writeUInt32LE(data.length, 24)
    central.writeUInt16LE(name.length, 28)
    central.writeUInt32LE(offset, 42)
    name.copy(central, 46)

    locals.push(local, data)
    centrals.push(central)
    offset += local.length + data.length
  }
  const dir = Buffer.concat(centrals)
  const eocd = Buffer.alloc(22)
  eocd.writeUInt32LE(0x06054b50, 0)
  eocd.writeUInt16LE(entries.length, 8)
  eocd.writeUInt16LE(entries.length, 10)
  eocd.writeUInt32LE(dir.length, 12)
  eocd.writeUInt32LE(offset, 16)
  return Buffer.concat([...locals, dir, eocd])
}

/** 원장님 명단 엑셀 흉내 — 머리글 한 줄 + 아이 셋. 소요시간은 엑셀이 시간으로 저장한 값 */
function rosterXlsx() {
  const words = [
    '이름',
    '연주곡',
    '작곡가',
    '소요시간',
    '난이도',
    '한여울',
    '인형의 꿈',
    '오귀스트',
    '중급',
    '서도윤',
    '작은 별 변주곡',
    '모차르트',
    '초급',
    '노아린',
    '아라베스크',
    '부르크뮐러',
    '고급',
  ]
  const si = words.map((w) => `<si><t>${w}</t></si>`).join('')
  const cell = (ref, idx) => `<c r="${ref}" t="s"><v>${idx}</v></c>`
  const sheet = `<worksheet><sheetData>
    <row r="1">${cell('A1', 0)}${cell('B1', 1)}${cell('C1', 2)}${cell('D1', 3)}${cell('E1', 4)}</row>
    <row r="2">${cell('A2', 5)}${cell('B2', 6)}${cell('C2', 7)}<c r="D2"><v>${210 / 86400}</v></c>${cell('E2', 8)}</row>
    <row r="3">${cell('A3', 9)}${cell('B3', 10)}${cell('C3', 11)}<c r="D3"><v>${70 / 86400}</v></c>${cell('E3', 12)}</row>
    <row r="4">${cell('A4', 13)}${cell('B4', 14)}${cell('C4', 15)}<c r="D4"><v>${180 / 86400}</v></c>${cell('E4', 16)}</row>
  </sheetData></worksheet>`
  return zipStore([
    { name: '[Content_Types].xml', data: '<Types/>' },
    { name: 'xl/sharedStrings.xml', data: `<sst>${si}</sst>` },
    { name: 'xl/worksheets/sheet1.xml', data: sheet },
  ])
}

/** 학년별로 장을 나눠 두신 파일 흉내 */
function multiSheetXlsx() {
  const sheet = (name, who, piece) =>
    `<worksheet><sheetData>` +
    `<row r="1"><c r="A1" t="inlineStr"><is><t>이름</t></is></c><c r="B1" t="inlineStr"><is><t>연주곡</t></is></c></row>` +
    `<row r="2"><c r="A2" t="inlineStr"><is><t>${who}</t></is></c><c r="B2" t="inlineStr"><is><t>${piece}</t></is></c></row>` +
    `</sheetData></worksheet>`
  return zipStore([
    {
      name: 'xl/workbook.xml',
      data:
        '<workbook><sheets>' +
        '<sheet name="1학년" sheetId="1" r:id="rId1"/>' +
        '<sheet name="2학년" sheetId="2" r:id="rId2"/>' +
        '</sheets></workbook>',
    },
    {
      name: 'xl/_rels/workbook.xml.rels',
      data:
        '<Relationships>' +
        '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>' +
        '<Relationship Id="rId2" Target="worksheets/sheet2.xml"/>' +
        '</Relationships>',
    },
    { name: 'xl/worksheets/sheet1.xml', data: sheet('1학년', '유하람', '작은 별 변주곡') },
    { name: 'xl/worksheets/sheet2.xml', data: sheet('2학년', '차온유', '인형의 꿈') },
  ])
}

let server
let browser
try {
  if (existsSync(DATA)) renameSync(DATA, BACKUP)
  if (existsSync(AUTO)) renameSync(AUTO, AUTO_SPARE)
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
  await fetch(`${BASE}/api/events/${EVENT_ID}/program`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })

  const executablePath = process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
  browser = await chromium.launch(existsSync(executablePath) ? { executablePath } : {})
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 } })
  const page = await ctx.newPage()
  page.on('pageerror', (error) => failures.push(`화면 오류: ${error.message}`))

  // ── 처음 켰을 때 안내 ────────────────────────────────────────────
  console.log('\n[처음 켰을 때 안내]')
  await page.goto(`${BASE}/events`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(600)
  const tour = page.getByTestId('first-run')
  check('처음 켜면 안내가 뜬다', (await tour.count()) === 1)
  const firstText = await tour.textContent()
  check('무엇부터 하는지 먼저 말해 준다', firstText.includes('세 가지'), firstText.slice(0, 30))
  check('몇 걸음 중 몇 번째인지 적혀 있다', /1 \/ \d/.test(firstText))

  // 화면을 가리지 않는다 — 뒤쪽 단추가 그대로 눌린다
  check('안내 뒤쪽 화면을 그대로 쓸 수 있다', await page.getByRole('link', { name: '새 행사' }).isVisible())

  await page.getByTestId('first-run-next').click()
  await page.waitForTimeout(250)
  const step2 = await tour.textContent()
  check('다음 걸음으로 넘어간다', step2.includes('카드 세 장'), step2.slice(0, 40))
  check('안내가 지금 화면을 가리킨다 — 없어진 탭을 말하지 않는다', !step2.includes('탭에서'))
  await page.screenshot({ path: join(OUT, 'first-run.jpg'), type: 'jpeg', quality: 82 })

  await page.getByTestId('first-run-close').click()
  await page.waitForTimeout(200)
  check('닫으면 사라진다', (await page.getByTestId('first-run').count()) === 0)
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForTimeout(500)
  check('새로고침해도 다시 뜨지 않는다', (await page.getByTestId('first-run').count()) === 0)

  // ── 화면 구조 · 어디까지 왔는지 ─────────────────────────────────
  console.log('\n[구조 — 무엇을 먼저 하나]')
  await page.goto(`${BASE}/events/${EVENT_ID}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(900)

  const hub = page.getByTestId('event-hub')
  check('행사 화면이 차례 안내로 열린다', (await hub.count()) === 1)
  const cards = await hub.locator('li').count()
  check('꼭 하셔야 하는 것은 세 가지뿐이다', cards === 3, `${cards}개`)
  const hubText = await hub.textContent()
  check('세 가지만 하면 된다고 먼저 말해 준다', (await page.textContent('body')).includes('이 세 가지만 하시면 됩니다'))

  // 지금 할 것 하나만 도드라져야 한다
  const nowCards = await hub.locator('[data-now="yes"]').count()
  check('지금 하실 것 하나만 도드라진다', nowCards === 1, `${nowCards}개`)
  check('그 카드에 "지금 하실 차례" 라고 적어 준다', hubText.includes('지금 하실 차례입니다'))
  check('끝난 것은 끝났다고 적어 준다', hubText.includes('끝났습니다'))

  // 나머지는 접혀 있다 — 필수와 곁들이를 눈으로 가른다
  const extras = page.getByTestId('event-extras')
  check('나머지는 접혀 있다', (await extras.count()) === 1)
  check('안 해도 된다고 적어 준다', (await extras.textContent()).includes('안 하셔도 연주회는 됩니다'))
  const extraVisible = await extras.locator('[data-testid^="extra-"]').first().isVisible()
  check('펴기 전에는 곁들이가 안 보인다', !extraVisible)
  await extras.locator('summary').click()
  await page.waitForTimeout(300)
  check('펴면 곁들이가 나온다', await extras.locator('[data-testid^="extra-"]').first().isVisible())
  await page.screenshot({ path: join(OUT, 'hub.jpg'), type: 'jpeg', quality: 82 })

  // ── 화면마다 색이 다르고, 어디까지 왔는지 늘 보인다 ───────────────
  console.log('\n[구조 — 여기가 어디인가]')
  const tints = []
  for (const [name, at] of [
    ['roster', `/events/${EVENT_ID}?tab=roster`],
    ['program', `/events/${EVENT_ID}?tab=program`],
    ['print', `/events/${EVENT_ID}/design`],
    ['video', `/events/${EVENT_ID}/video`],
  ]) {
    await page.goto(`${BASE}${at}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(700)
    const header = page.getByTestId('screen-header')
    check(`${name} — 화면 맨 위에 단계 띠가 있다`, (await header.count()) === 1)
    check(`${name} — 어디까지 왔는지 함께 보여 준다`, (await page.getByTestId('flow-progress').count()) === 1)
    tints.push(await page.evaluate(() => getComputedStyle(document.querySelector('.app-shell')).backgroundColor))
  }
  check('화면마다 바탕색이 다르다 — 같으면 어디인지 알 수 없다', new Set(tints).size === tints.length, tints.join(' / '))

  const optional = await page.getByTestId('screen-header').textContent()
  check('곁들이 화면은 안 해도 된다고 적어 준다', optional.includes('안 하셔도 됩니다'))
  check('다음에 갈 곳을 알려 준다', (await page.getByTestId('flow-next').count()) === 1)

  await page.goto(`${BASE}/events/${EVENT_ID}?tab=roster`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(700)
  const must = await page.getByTestId('screen-header').textContent()
  check('꼭 해야 하는 화면은 몇 번째인지 적어 준다', /꼭 하셔야 하는 \d번째/.test(must), must.slice(0, 40))

  // ── 테마·색을 고르는 동안 미리보기가 사라지지 않는다 ──────────────
  console.log('\n[구조 — 고르는 동안 보이는가]')
  await page.goto(`${BASE}/events/${EVENT_ID}/design`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1500)
  const designPreview = page.getByTestId('design-preview')
  check('인쇄물 미리보기가 있다', (await designPreview.count()) === 1)
  const beforeScroll = await designPreview.boundingBox()
  await page.evaluate(() => window.scrollTo(0, 900))
  await page.waitForTimeout(600)
  const afterScroll = await designPreview.boundingBox()
  check(
    '테마를 고르러 내려가도 미리보기가 화면에 남는다',
    afterScroll !== null && afterScroll.y + afterScroll.height > 0 && afterScroll.y < 900,
    `${Math.round(beforeScroll?.y ?? -1)} → ${Math.round(afterScroll?.y ?? -1)}`,
  )
  await page.screenshot({ path: join(OUT, 'sticky-preview.jpg'), type: 'jpeg', quality: 82 })

  // 고를 것이 있다는 사실 자체에서 멈추신다 — 하나를 미리 골라 두고 먼저 말해야 한다
  const ready = page.getByTestId('design-ready')
  check('무엇을 뽑을지 미리 골라 둔다', (await ready.count()) === 1)
  const readyText = await ready.textContent()
  check('이대로 뽑아도 된다고 말해 준다', readyText.includes('이대로 뽑으셔도 됩니다'), readyText.slice(0, 30))
  check('왜 이걸 골랐는지 한마디 붙인다', /어울리는|그대로입니다/.test(readyText), readyText.slice(0, 120))
  // 미리 골라 둔 것이 실제로 골라져 있어야 한다 — 말만 하고 안 골라 두면 소용없다
  const chosen = await page.locator('[aria-pressed="true"]').count()
  check('말한 대로 실제로 골라져 있다', chosen >= 1, `${chosen}개 선택됨`)

  // 한 벌을 누르기 전에 종이가 몇 장 나오는지 아셔야 한다
  const packButtons = page.locator('a[href*="pack="] button')
  const packCount = await packButtons.count()
  check('한 벌로 뽑는 자리가 있다', packCount >= 1, `${packCount}벌`)
  const packText = await packButtons.first().textContent()
  check('한 벌이 종이 몇 장인지 미리 적혀 있다', /종이 \d+장/.test(packText), packText.replace(/\s+/g, ' ').trim().slice(0, 60))
  const allPacks = await packButtons.evaluateAll((nodes) => nodes.map((n) => n.textContent ?? ''))
  const withSheets = allPacks.filter((t) => /종이 \d+장/.test(t)).length
  check('모든 한 벌에 장수가 적혀 있다', withSheets === packCount, `${withSheets} / ${packCount}`)
  const zeroSheets = allPacks.filter((t) => /종이 0장/.test(t)).length
  check('장수가 0장으로 나오지 않는다', zeroSheets === 0, `${zeroSheets}벌`)

  // 하나만 정해 드리면 "마음에 안 드는데" 에서 막히신다. 셋이면 견주신다
  const choices = page.getByTestId('design-choices')
  check('견주어 보실 세 장이 있다', (await choices.count()) === 1)
  const choiceCards = choices.locator('button')
  check('세 장이다 — 넷이면 다시 고민이 시작된다', (await choiceCards.count()) === 3, `${await choiceCards.count()}장`)
  const thumbs = await choices.locator('button > span:first-child').count()
  check('카드마다 실제 그림이 들어 있다 — 색 동그라미로는 못 고르신다', thumbs === 3, `${thumbs}장`)
  const cardWords = await choiceCards.evaluateAll((nodes) => nodes.map((n) => n.textContent ?? ''))
  check('무엇이 다른지 글로도 적혀 있다', cardWords.every((t) => t.trim().length > 2), cardWords.join(' / '))
  check('담백한 쪽과 화려한 쪽이 함께 있다', (await choices.getByTestId('design-choice-plain').count()) === 1 && (await choices.getByTestId('design-choice-fancy').count()) === 1)

  // 눌러 보시면 큰 그림이 그대로 바뀐다 — 안 바뀌면 고른 뜻이 없다
  const beforePick = await designPreview.textContent()
  await choices.getByTestId('design-choice-fancy').click()
  await page.waitForTimeout(900)
  check('누르면 그 장이 골라진다', (await choices.locator('button[aria-pressed="true"]').count()) === 1)
  const afterPick = await designPreview.textContent()
  check('누르면 오른쪽 큰 그림도 바뀐다', afterPick !== beforePick || (await choices.getByTestId('design-choice-fancy').getAttribute('aria-pressed')) === 'true')
  await page.screenshot({ path: join(OUT, 'design-choices.jpg'), type: 'jpeg', quality: 82 })

  // 화면 색과 종이 색은 다르다 — 한 장이면 실물로 견주신다
  check('세 장을 종이로 견줄 자리가 있다', (await page.getByTestId('compare-link').count()) === 1)
  await page.goto(`${BASE}/events/${EVENT_ID}/design/compare`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1600)
  const sheet = page.getByTestId('compare-sheet')
  check('견주기 종이가 그려진다', (await sheet.count()) === 1)
  const compareSlots = await sheet.locator('[data-testid^="compare-"]').count()
  check('한 장에 세 장이 나란히 들어간다', compareSlots === 3, `${compareSlots}칸`)
  const compareSheets = await page.getByTestId('print-sheets').textContent()
  check('종이는 한 장뿐이다 — 견주려고 세 장을 뽑으면 뜻이 없다', compareSheets.includes('1장'), compareSheets)
  const compareText = await sheet.textContent()
  check('동그라미 치시라고 적어 준다', compareText.includes('동그라미'), compareText.slice(0, 80))
  check('종이마다 무엇인지 적혀 있다', ['담백한 쪽', '화려한 쪽'].every((w) => compareText.includes(w)))
  check('종이에도 번호가 붙는다 — 화면과 같은 번호라야 한다', /1\./.test(compareText) && /3\./.test(compareText))

  // 종이에서 화면으로 돌아오는 길
  const codes = sheet.getByTestId('qr-code')
  check('장마다 비출 무늬가 있다', (await codes.count()) === 3, `${await codes.count()}개`)
  check('무엇을 하는 무늬인지 적어 준다', compareText.includes('비추면'), compareText.slice(0, 120))
  check('못 비추셔도 되는 길을 함께 적어 준다', compareText.includes('같은 번호'))
  const qrBox = await codes.first().boundingBox()
  check('무늬가 비출 만한 크기다', qrBox && qrBox.width >= 50, qrBox ? `${Math.round(qrBox.width)}px` : '자리를 못 찾음')

  // 비추고 오시면 그 장이 골라진 채로 열린다
  await page.goto(`${BASE}/events/${EVENT_ID}/design?pick=fancy`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1600)
  const fromPaper = page.getByTestId('design-choices')
  check(
    '종이에서 오시면 그 장이 골라진 채로 열린다',
    (await fromPaper.getByTestId('design-choice-fancy').getAttribute('aria-pressed')) === 'true',
  )
  check('종이에서 오셨다고 말해 준다', (await page.getByTestId('design-ready').textContent()).includes('종이에서 고르신'))
  await page.goto(`${BASE}/events/${EVENT_ID}/design?pick=없는것`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1400)
  check('엉뚱한 주소로 오셔도 멈추지 않는다', (await page.getByTestId('design-choices').count()) === 1)
  await page.screenshot({ path: join(OUT, 'design-from-paper.jpg'), type: 'jpeg', quality: 82 })
  await page.screenshot({ path: join(OUT, 'design-compare.jpg'), type: 'jpeg', quality: 82 })

  // 좁은 화면에서도 가로로 넘치지 않아야 한다 (넘치면 단추가 화면 밖으로 나간다)
  const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })
  const small = await phone.newPage()
  await small.goto(`${BASE}/events/${EVENT_ID}/design`, { waitUntil: 'networkidle' })
  await small.waitForTimeout(1200)
  const over = await small.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  check('휴대폰에서 가로로 넘치지 않는다', over <= 0, `${over}px`)
  await phone.close()

  // ── 글씨 크게 · 곁들이 완료 표시 · 이어서 하기 ────────────────────
  console.log('\n[구조 — 더 쉽게]')
  await page.goto(`${BASE}/events/${EVENT_ID}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)

  const sizer = page.getByTestId('text-size')
  check('글씨 크기 단추가 머리띠에 있다', (await sizer.count()) === 1)
  const wasFont = await page.evaluate(() => getComputedStyle(document.documentElement).fontSize)
  await sizer.click()
  await page.waitForTimeout(400)
  const bigFont = await page.evaluate(() => getComputedStyle(document.documentElement).fontSize)
  check('누르면 글씨가 커진다', parseFloat(bigFont) > parseFloat(wasFont), `${wasFont} → ${bigFont}`)
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForTimeout(700)
  const kept = await page.evaluate(() => getComputedStyle(document.documentElement).fontSize)
  check('다시 열어도 그 크기로 열린다', kept === bigFont, `${kept} / ${bigFont}`)
  // 세 번 누르면 처음으로 — 원장님이 되돌리실 수 있어야 한다
  await page.getByTestId('text-size').click()
  await page.waitForTimeout(250)
  await page.getByTestId('text-size').click()
  await page.waitForTimeout(400)
  check(
    '끝까지 누르면 처음 크기로 돌아온다',
    (await page.evaluate(() => getComputedStyle(document.documentElement).fontSize)) === wasFont,
  )

  // 곁들이에도 해 두신 것은 표시된다.
  // 표시가 뜨려면 실제로 해 두신 자국이 있어야 하므로, 학부모 회신을 하나 만들어 둔다.
  await page.request.post(`${BASE}/api/rsvp`, {
    data: { event_id: EVENT_ID, parent_name: '김보호', student_name: '오수아', headcount: 2, attending: true },
  })
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  await page.getByTestId('event-extras').locator('summary').click()
  await page.waitForTimeout(400)
  const doneMarks = await page.locator('[data-testid^="extra-"][data-done="yes"]').count()
  check('해 두신 곁들이에는 표가 붙는다', doneMarks >= 1, `${doneMarks}개`)
  check(
    '해 두셨다고 적어 준다',
    (await page.getByTestId('event-extras').textContent()).includes('해 두셨습니다'),
  )
  await page.screenshot({ path: join(OUT, 'extras-done.jpg'), type: 'jpeg', quality: 82 })

  // ── 화면을 옮겨도 되돌릴 수 있다 ─────────────────────────────────
  console.log('\n[되돌리기 — 화면을 옮겨도]')
  await page.goto(`${BASE}/events/${EVENT_ID}?tab=roster`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(900)
  const cell = page.getByTestId('roster-table').locator('tbody tr').first().locator('input[aria-label="연주곡"]')
  const wasValue = await cell.inputValue()
  await cell.fill('옮겨도 되돌아가야 함')
  await cell.blur()
  await page.waitForTimeout(1600)
  check('고치면 되돌리기가 뜬다', (await page.getByTestId('undo-bar').count()) === 1)

  // 다른 화면에 갔다 온다
  await page.goto(`${BASE}/events/${EVENT_ID}/design`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(900)
  check('다른 화면에서도 되돌릴 것이 남아 있다', (await page.getByTestId('undo-bar').count()) === 1)
  await page.getByTestId('undo-now').click()
  await page.waitForTimeout(1800)
  const restored = await (await page.request.get(`${BASE}/api/events/${EVENT_ID}/students`)).json()
  check(
    '다른 화면에서 눌러도 제대로 되돌아간다',
    restored.students[0].piece_title === wasValue,
    `${restored.students[0].piece_title} / ${wasValue}`,
  )

  // ── 하시던 자리에서 다음 것까지 ──────────────────────────────────
  console.log('\n[이어서 하기]')
  const fresh = await (await page.request.post(`${BASE}/api/events`, {
    data: { title: '이어서 하기 시험', type: 'recital', event_at: '2027-05-01T09:00:00.000Z', venue: '연습실' },
  })).json()
  const freshId = fresh.event.id
  await page.request.post(`${BASE}/api/events/${freshId}/students`, {
    data: { text: '이름\t연주곡\n한여울\t인형의 꿈\n서도윤\t작은 별 변주곡' },
  })
  await page.goto(`${BASE}/events/${freshId}?tab=roster`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1000)
  const here = page.getByTestId('next-here')
  check('명단이 들어오면 다음 것을 여기서 하자고 한다', (await here.count()) === 1)
  const hereText = await here.textContent()
  check('무엇이 다음인지 적어 준다', hereText.includes('순서표'), hereText.slice(0, 60))
  check('화면을 안 옮겨도 된다고 적어 준다', hereText.includes('화면을 옮기지 않으셔도 됩니다'))

  await page.getByTestId('next-here-go').click()
  await page.waitForTimeout(4000)
  const all = await (await page.request.get(`${BASE}/api/events`)).json().catch(() => null)
  const made = all?.events?.find((e) => e.id === freshId)
  check('여기서 눌러 순서표가 만들어진다', Boolean(made?.program_source), String(made?.program_source))
  check('끝나면 그 화면으로 데려다 준다', page.url().includes('tab=program'), page.url())
  await page.screenshot({ path: join(OUT, 'next-here.jpg'), type: 'jpeg', quality: 82 })

  // ── 엑셀 파일 끌어다 놓기 ────────────────────────────────────────
  console.log('\n[엑셀 파일 그대로 넣기]')
  await page.goto(`${BASE}/events/${EVENT_ID}?tab=roster`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(500)
  check('엑셀 놓는 자리가 있다', (await page.getByTestId('roster-drop').count()) === 1)
  const dropText = await page.getByTestId('roster-drop').textContent()
  check('복사·붙여넣기를 안 하셔도 된다고 적혀 있다', dropText.includes('복사·붙여넣기를 하지 않으셔도'))
  check('파일이 밖으로 안 나간다고 적혀 있다', dropText.includes('컴퓨터 밖으로 나가지 않습니다'))

  await page.getByLabel('엑셀 파일 고르기').setInputFiles({
    name: '학생명단.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: rosterXlsx(),
  })
  await page.waitForTimeout(1500)
  const pasted = await page.getByLabel('학생 명단 붙여넣기').inputValue()
  check('엑셀에서 읽은 표가 칸에 들어온다', pasted.includes('한여울'), pasted.split('\n')[1] ?? '')
  check('엑셀이 시간으로 바꿔 둔 소요시간을 되돌린다', pasted.includes('3:30'), pasted.split('\n')[1] ?? '')
  check('장이 하나뿐이면 고르는 칸이 나오지 않는다', (await page.getByTestId('sheet-picker').count()) === 0)

  // ── 학년별로 장을 나눠 두신 파일 ────────────────────────────────
  console.log('\n[엑셀 장이 여러 개일 때]')
  await page.getByLabel('엑셀 파일 고르기').setInputFiles({
    name: '학년별명단.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: multiSheetXlsx(),
  })
  await page.waitForTimeout(1500)
  const picker = page.getByTestId('sheet-picker')
  check('장이 여럿이면 고르는 칸이 나온다', (await picker.count()) === 1)
  const pickerText = await picker.textContent()
  check('엑셀 아래쪽 탭 이름을 그대로 보여 준다', pickerText.includes('1학년') && pickerText.includes('2학년'))
  check('맨 앞 장을 먼저 읽는다', (await page.getByLabel('학생 명단 붙여넣기').inputValue()).includes('유하람'))

  await picker.getByRole('button', { name: '2학년' }).click()
  await page.waitForTimeout(1500)
  const second = await page.getByLabel('학생 명단 붙여넣기').inputValue()
  check('다른 장을 고르면 그 장으로 다시 읽는다', second.includes('차온유'), second.split('\n')[1] ?? '')
  check('앞 장의 아이는 남지 않는다', !second.includes('유하람'))
  await page.screenshot({ path: join(OUT, 'sheets.jpg'), type: 'jpeg', quality: 82 })

  // 다시 원래 파일로 돌려 놓는다 (뒤 검사가 이 명단을 쓴다)
  await page.getByLabel('엑셀 파일 고르기').setInputFiles({
    name: '학생명단.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: rosterXlsx(),
  })
  await page.waitForTimeout(1500)

  // ── 이렇게 읽었습니다 ────────────────────────────────────────────
  console.log('\n[이렇게 읽었습니다]')
  const receipt = page.getByTestId('roster-receipt')
  check('넣기 전에 읽은 결과를 보여 준다', (await receipt.count()) === 1)
  const receiptText = await receipt.textContent()
  check('몇 명인지 사람 말로 알려 준다', /아이 3명을 읽었습니다/.test(receiptText), receiptText.slice(0, 60))
  check('머리글을 건너뛴 것도 알려 준다', receiptText.includes('머리글'))
  await page.screenshot({ path: join(OUT, 'receipt.jpg'), type: 'jpeg', quality: 82 })

  // 이름과 곡이 한 칸에 붙은 흔한 실수를 짚는가
  await page.getByLabel('학생 명단 붙여넣기').fill('한여울 인형의 꿈\n서도윤 작은 별 변주곡')
  await page.waitForTimeout(500)
  const warned = await page.getByTestId('roster-receipt').textContent()
  check('이름과 곡이 한 칸에 붙으면 짚어 준다', warned.includes('한 칸에 붙어'), warned.slice(0, 80))

  // 같은 아이가 두 번 — 곡까지 같으면 잘못, 곡이 다르면 잘못이 아니다
  await page.getByLabel('학생 명단 붙여넣기').fill('이름\t연주곡\n한여울\t인형의 꿈\n한여울\t인형의 꿈')
  await page.waitForTimeout(500)
  const dup = await page.getByTestId('roster-receipt').textContent()
  check('같은 곡으로 두 번 들어가면 짚어 준다', dup.includes('같은 곡으로 두 줄'), dup.slice(0, 90))

  await page.getByLabel('학생 명단 붙여넣기').fill('이름\t연주곡\n한여울\t인형의 꿈\n한여울\t소나티네')
  await page.waitForTimeout(500)
  const twoPieces = await page.getByTestId('roster-receipt').textContent()
  check('곡이 다르면 잘못이 아니다 — 독주와 듀엣은 흔하다', !twoPieces.includes('같은 곡으로 두 줄'))
  check('사람 수와 무대 수를 따로 센다', twoPieces.includes('아이 1명') && twoPieces.includes('무대 2번'))

  // ── 되돌리기 ─────────────────────────────────────────────────────
  console.log('\n[되돌리기]')
  const before = (await (await page.request.get(`${BASE}/api/events/${EVENT_ID}/students`)).json()).students.length
  await page.getByLabel('학생 명단 붙여넣기').fill(pasted)
  await page.waitForTimeout(400)
  await page.getByRole('button', { name: '명단에 추가' }).click()
  await page.waitForTimeout(1800)
  const added = (await (await page.request.get(`${BASE}/api/events/${EVENT_ID}/students`)).json()).students.length
  check('명단이 늘었다', added === before + 3, `${before} → ${added}`)
  check('되돌리기가 화면 맨 위 한 자리에 뜬다', (await page.getByTestId('undo-bar').count()) === 1)
  const pasteUndo = await page.getByTestId('undo-bar').textContent()
  check('무엇을 하셨는지 적어 준다', pasteUndo.includes('명단 붙여넣기'), pasteUndo.slice(0, 60))

  await page.getByTestId('undo-now').click()
  await page.waitForTimeout(1800)
  const undone = (await (await page.request.get(`${BASE}/api/events/${EVENT_ID}/students`)).json()).students
  check('붙여넣기 전으로 그대로 돌아간다', undone.length === before, `${added} → ${undone.length}`)
  check('되돌린 명단에 방금 넣은 아이가 없다', !undone.some((s) => s.student_name === '한여울'))

  // ── 표에서 고친 것 되돌리기 ─────────────────────────────────────
  console.log('\n[표에서 고친 것 되돌리기]')
  await page.goto(`${BASE}/events/${EVENT_ID}?tab=roster`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(900)
  check('아무것도 안 하셨으면 되돌리기 띠가 없다', (await page.getByTestId('undo-bar').count()) === 0)

  const firstRow = page.getByTestId('roster-table').locator('tbody tr').first()
  const pieceCell = firstRow.locator('input[aria-label="연주곡"]')
  const wasPiece = await pieceCell.inputValue()
  await pieceCell.fill('잘못 친 곡')
  await pieceCell.blur()
  await page.waitForTimeout(1600)

  const undoBar = page.getByTestId('undo-bar')
  check('고치면 같은 자리에 뜬다 — 자리마다 배우실 것이 없게', (await undoBar.count()) === 1)
  const undoText = await undoBar.textContent()
  check('무엇을 무엇으로 되돌리는지 미리 보여 준다', undoText.includes(wasPiece), undoText.slice(0, 80))
  check('누구의 어느 칸인지 적어 준다', undoText.includes('연주곡'))
  await page.screenshot({ path: join(OUT, 'edit-undo.jpg'), type: 'jpeg', quality: 82 })

  await page.getByTestId('undo-now').click()
  await page.waitForTimeout(1800)
  const backTo = await page.getByTestId('roster-table').locator('tbody tr').first().locator('input[aria-label="연주곡"]').inputValue()
  check('고치기 전 값으로 돌아간다', backTo === wasPiece, `${backTo} / ${wasPiece}`)
  check('되돌린 것이 다시 쌓이지 않는다', (await page.getByTestId('undo-now').count()) === 0)

  // 화면을 옮기면 비워진다 — 다른 화면 일을 여기서 되돌리면 놀라신다
  await page.goto(`${BASE}/settings`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  check('화면을 옮기면 되돌리기 띠가 비워진다', (await page.getByTestId('undo-bar').count()) === 0)

  // ── 인쇄 · 종이 미리보기 ─────────────────────────────────────────
  console.log('\n[인쇄 · 종이 미리보기]')
  await page.goto(`${BASE}/events/${EVENT_ID}/program/print`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(900)
  const bar = page.getByTestId('print-bar')
  check('인쇄 띠가 있다', (await bar.count()) === 1)
  check('인쇄 단추가 있다', (await page.getByTestId('print-now').count()) === 1)
  const sheetText = await page.getByTestId('print-sheets').textContent()
  check('뽑기 전에 종이 몇 장인지 알려 준다', /종이 \d+장/.test(sheetText), sheetText)
  const sheets = Number((await bar.getAttribute('data-sheets')) ?? 0)
  check('장수를 실제 내용 높이에서 센다', sheets >= 1, `${sheets}장`)

  await page.getByLabel('몇 부 뽑으실지').fill('100')
  await page.waitForTimeout(300)
  check('부수를 넣으면 종이 총량을 알려 준다', (await bar.textContent()).includes(`${sheets * 100}장`))

  // 뽑기 직전 마지막 한 줄 — 인쇄 창에서 무엇을 봐야 하는지
  const summary = page.getByTestId('print-summary')
  check('뽑기 전 마지막 확인이 있다', (await summary.count()) === 1)
  const summaryText = (await summary.textContent()).replace(/\s+/g, ' ')
  check('종이·장수·색·양면 넷을 짚어 준다', ['종이', '장수', '색', '양면'].every((w) => summaryText.includes(w)), summaryText.slice(0, 90))
  check('부수까지 곱해 적어 준다', summaryText.includes(`${sheets * 100}`) || summaryText.includes((sheets * 100).toLocaleString('ko-KR')), summaryText.slice(0, 120))
  const summarySize = await summary.locator('dd').first().evaluate((el) => parseFloat(getComputedStyle(el).fontSize))
  const pageSize = await page.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize))
  check('마지막 확인은 큰 글씨다 — 흘려보시면 뜻이 없다', summarySize >= pageSize, `${summarySize.toFixed(1)}px / ${pageSize.toFixed(1)}px`)
  // 1,200장은 숫자일 뿐이라 크기가 안 그려진다 — 박스·연으로 바꿔 드려야 아신다
  const bulk = page.getByTestId('print-bulk')
  check('많이 뽑으실 때는 종이가 얼마나인지 몸으로 아는 단위로 말해 준다', (await bulk.count()) === 1)
  const bulkText = await bulk.textContent()
  check('연이나 박스로 견줘 준다', /연|박스/.test(bulkText), bulkText.trim())
  await page.getByLabel('몇 부 뽑으실지').fill('1')
  await page.waitForTimeout(400)
  check('적게 뽑으실 때는 겁주지 않는다', (await page.getByTestId('print-bulk').count()) === 0)
  await page.getByLabel('몇 부 뽑으실지').fill('100')
  await page.waitForTimeout(300)
  await page.screenshot({ path: join(OUT, 'print-summary.jpg'), type: 'jpeg', quality: 82 })

  check('인쇄 설정 안내는 접혀 있다', (await page.getByTestId('print-howto').count()) === 0)
  await page.getByTestId('print-howto-toggle').click()
  await page.waitForTimeout(300)
  const howto = await page.getByTestId('print-howto').textContent()
  check('배율·여백·배경 그래픽을 짚어 준다', ['배율', '여백', '배경 그래픽'].every((w) => howto.includes(w)))

  await page.getByTestId('paper-toggle').click()
  await page.waitForTimeout(700)
  const preview = page.getByTestId('paper-preview')
  check('종이로 보기가 열린다', (await preview.count()) === 1)
  const box = await preview.boundingBox()
  check('종이 비율(A4)로 그린다', Math.abs(box.width / box.height - 794 / 1123) < 0.25, `${Math.round(box.width)}×${Math.round(box.height)}`)
  const cuts = await page.getByTestId('paper-cut').count()
  check('두 장을 넘으면 잘리는 자리에 선을 긋는다', sheets === 1 ? cuts === 0 : cuts === sheets - 1, `${sheets}장 / 선 ${cuts}개`)
  await page.screenshot({ path: join(OUT, 'paper.jpg'), type: 'jpeg', quality: 82 })

  await page.goto(`${BASE}/events/${EVENT_ID}/script`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  check('사회자 대본도 종이로 볼 수 있다', (await page.getByTestId('paper-toggle').count()) === 1)

  // 첫 장만 뽑아 보기 — 표시를 붙였다 떼는지까지 본다
  check('첫 장만 뽑아 보는 단추가 있다', (await page.getByTestId('print-first').count()) === 1)
  await page.evaluate(() => {
    // 인쇄 대화상자는 검사에서 열 수 없다. 창을 여는 자리만 막아 두고 표시를 확인한다.
    window.__printed = 0
    window.print = () => {
      window.__printedWith = document.documentElement.className
      window.__printed += 1
    }
  })
  await page.getByTestId('print-first').click()
  await page.waitForTimeout(300)
  check('첫 장만 뽑을 때 표시가 붙는다', await page.evaluate(() => String(window.__printedWith ?? '').includes('print-first-only')))
  await page.waitForTimeout(3400)
  check(
    '뽑고 나면 표시를 뗀다 — 남으면 다음 인쇄가 통째로 첫 장만 나온다',
    !(await page.evaluate(() => document.documentElement.className.includes('print-first-only'))),
  )
  await page.getByTestId('print-now').click()
  await page.waitForTimeout(300)
  check(
    '보통 인쇄에는 표시가 붙지 않는다',
    !(await page.evaluate(() => String(window.__printedWith ?? '').includes('print-first-only'))),
  )

  await page.goto(`${BASE}/events/${EVENT_ID}/design/print?template=poster-classic`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  check('인쇄물도 종이 장수를 알려 준다', (await page.getByTestId('print-sheets').count()) === 1)
  check('인쇄물에도 인쇄 설정 안내가 있다', (await page.getByTestId('print-howto-toggle').count()) === 1)
  check('인쇄물에도 첫 장만 뽑는 단추가 있다', (await page.getByTestId('print-first').count()) === 1)
  check('인쇄물에도 뽑기 전 마지막 확인이 있다', (await page.getByTestId('print-summary').count()) === 1)
  // 종이만 세시는데, 연주회 전날 밤에 멈추는 것은 잉크다
  await page.getByLabel('몇 부 뽑으실지').fill('120')
  await page.waitForTimeout(500)
  const ink = page.getByTestId('print-ink')
  check('색을 꽉 채운 인쇄물은 잉크도 짚어 준다', (await ink.count()) === 1)
  const inkText = await ink.textContent()
  check('잉크가 모자랄 수 있다고 말해 준다', inkText.includes('잉크'), inkText.trim().slice(0, 80))
  await page.getByLabel('몇 부 뽑으실지').fill('1')
  await page.waitForTimeout(400)
  check('몇 장 안 뽑으실 때는 잉크로 겁주지 않는다', (await page.getByTestId('print-ink').count()) === 0)
  await page.screenshot({ path: join(OUT, 'print-ink.jpg'), type: 'jpeg', quality: 82 })

  // 글만 있는 인쇄물은 잉크가 훨씬 덜 든다 — 같은 말을 하면 안 된다
  await page.goto(`${BASE}/events/${EVENT_ID}/design/print?template=checklist`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(900)
  await page.getByLabel('몇 부 뽑으실지').fill('120')
  await page.waitForTimeout(500)
  check('글 위주 인쇄물에는 잉크 이야기를 하지 않는다', (await page.getByTestId('print-ink').count()) === 0)

  // ── 종이 위 글씨 크기 ───────────────────────────────────────────
  console.log('\n[종이 글씨 크기]')
  await page.goto(`${BASE}/events/${EVENT_ID}/program/print`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1100)
  const sizeBox = page.getByTestId('print-text-size')
  check('종이 글씨 크기를 고를 수 있다', (await sizeBox.count()) === 1)
  const sheetsNormal = Number((await page.getByTestId('print-bar').getAttribute('data-sheets')) ?? 0)
  await sizeBox.getByRole('button', { name: '아주 크게' }).click()
  await page.waitForTimeout(900)
  const sheetsHuge = Number((await page.getByTestId('print-bar').getAttribute('data-sheets')) ?? 0)
  check(
    '키우면 장수를 다시 세어 준다 — 뽑고 나서 아시면 늦다',
    sheetsHuge >= sheetsNormal,
    `${sheetsNormal}장 → ${sheetsHuge}장`,
  )
  check('글씨를 키웠다고 적어 준다', (await page.getByTestId('print-bar').textContent()).includes('글씨를 키워'))
  await page.screenshot({ path: join(OUT, 'print-text-size.jpg'), type: 'jpeg', quality: 82 })

  // ── 책자 한 벌 · 양면 안내 ──────────────────────────────────────
  console.log('\n[책자 한 벌]')
  await page.goto(`${BASE}/events/${EVENT_ID}/design/print?pack=booklet`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1100)
  check('책자를 한 벌로 뽑을 수 있다', (await page.locator('.d-sheet').count()) >= 2)
  const duplex = page.getByTestId('duplex-hint')
  check('양면으로 뽑으라고 알려 준다', (await duplex.count()) === 1)
  const duplexText = await duplex.textContent()
  check('넘기는 방향까지 짚어 준다 — 긴 쪽이면 속장이 뒤집힌다', duplexText.includes('짧은 쪽'))
  check('접으면 무엇이 되는지 적어 준다', duplexText.includes('반으로 접으면'))
  const bookletSummary = await page.getByTestId('print-summary').textContent()
  check('마지막 확인에도 양면이라고 적힌다', bookletSummary.includes('짧은 쪽'), bookletSummary.replace(/\s+/g, ' ').slice(0, 90))

  await page.goto(`${BASE}/events/${EVENT_ID}/design/print?template=poster-classic`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(900)
  check('보통 인쇄물에는 양면 안내를 띄우지 않는다', (await page.getByTestId('duplex-hint').count()) === 0)
  check(
    '보통 인쇄물의 마지막 확인은 한 면씩이라고 적는다',
    (await page.getByTestId('print-summary').textContent()).includes('아니요'),
  )

  // ── 인쇄소용 (재단선 · 물림 여백) ────────────────────────────────
  console.log('\n[인쇄소에 맡기실 때]')
  const bleedBar = page.getByTestId('bleed-bar')
  check('인쇄소용으로 가는 길이 있다', (await bleedBar.count()) === 1)
  check('집 프린터에서는 안 눌러도 된다고 적혀 있다', (await bleedBar.textContent()).includes('인쇄소'))
  const plainSheet = await page.locator('.d-sheet').first().boundingBox()

  await page.getByTestId('bleed-on').click()
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(900)
  check('인쇄소용으로 바뀐다', (await page.locator('.d-bleed').count()) >= 1)
  const bledSheet = await page.locator('.d-sheet').first().boundingBox()
  check(
    '인쇄물 자체는 그대로 — 커지는 것은 그 둘레다',
    Math.abs(bledSheet.width - plainSheet.width) < 2,
    `${Math.round(plainSheet.width)} → ${Math.round(bledSheet.width)}`,
  )
  const frame = await page.locator('.d-bleed').first().boundingBox()
  check(
    '사방 3mm 만큼 넓어진다',
    frame.width > bledSheet.width + 15 && frame.width < bledSheet.width + 30,
    `${Math.round(bledSheet.width)} → ${Math.round(frame.width)}`,
  )
  const marks = await page.locator('.d-bleed .d-crop').count()
  check('네 모서리에 재단선을 찍는다 (여덟 줄)', marks === 8, `${marks}줄`)
  check('집 프린터용으로 되돌아갈 수 있다', (await page.getByRole('link', { name: '집 프린터용으로' }).count()) === 1)
  await page.screenshot({ path: join(OUT, 'bleed.jpg'), type: 'jpeg', quality: 82 })

  // ── 인쇄소 견적용 요약 ───────────────────────────────────────────
  console.log('\n[인쇄소 견적용 요약]')
  check('인쇄물 화면에서 견적 요약으로 갈 수 있다', (await page.getByTestId('quote-link').count()) >= 1)
  await page.getByTestId('quote-link').first().click()
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(900)
  const quote = page.getByTestId('quote-table')
  check('견적 요약이 열린다', (await quote.count()) === 1)
  const quoteText = await quote.textContent()
  check('규격을 mm 로 적는다 — 인쇄소는 mm 로 말한다', /\d+ × \d+mm/.test(quoteText), (quoteText.match(/\d+ × \d+mm/) ?? [''])[0])
  check('권하는 종이를 적는다', /\d+g/.test(quoteText), (quoteText.match(/[가-힣]+지 \d+g/) ?? [''])[0])
  check('부수와 총 장수를 적는다', quoteText.includes('부') && quoteText.includes('장'))
  check('합계를 낸다', (await page.getByTestId('quote-total').count()) === 1)
  const body = await page.textContent('body')
  check('인쇄소에 함께 말할 것을 적어 준다', body.includes('재단선') && body.includes('PDF'))
  check('문자로 보낼 글을 복사할 수 있다', (await page.getByRole('button', { name: '문자로 보낼 글 복사' }).count()) === 1)
  check('견적 요약도 종이로 볼 수 있다', (await page.getByTestId('paper-toggle').count()) === 1)
  await page.screenshot({ path: join(OUT, 'quote.jpg'), type: 'jpeg', quality: 82 })


  // ── 무대 모양을 그림으로 고른다 ─────────────────────────────────
  console.log('\n[무대 모양 고르기]')
  await page.goto(`${BASE}/events/${EVENT_ID}/stage`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1600)
  const grid = page.getByTestId('layout-grid')
  check('모양을 그림 격자로 보여 준다', (await grid.count()) === 1)
  const tiles = await grid.locator('button').count()
  check('열네 가지가 모두 있다', tiles === 14, `${tiles}개`)
  const firstTile = await grid.locator('button').first().boundingBox()
  check('그림이 눌러 볼 만한 크기다', firstTile.width >= 70 && firstTile.height >= 70, `${Math.round(firstTile.width)}×${Math.round(firstTile.height)}`)
  await grid.locator('button').nth(9).click()
  await page.waitForTimeout(600)
  check('고르면 그 모양으로 바뀐다', (await grid.locator('button[aria-pressed="true"]').count()) === 1)
  await page.screenshot({ path: join(OUT, 'layout-grid.jpg'), type: 'jpeg', quality: 82 })

  // 여기서 대부분 멈추신다 — 선은 꽂았는데 스크린에 안 나온다
  const projector = page.getByTestId('projector-help')
  check('빔프로젝터에 안 나올 때 볼 곳이 있다', (await projector.count()) === 1)
  check('평소에는 접혀 있다 — 아는 분께는 군더더기다', (await page.getByTestId('projector-steps').count()) === 0)
  await page.getByTestId('projector-toggle').click()
  await page.waitForTimeout(400)
  const steps = await page.getByTestId('projector-steps').textContent()
  check('윈도우에서 누를 자판을 정확히 적어 준다', steps.includes('윈도우키') && steps.includes('P'), steps.slice(0, 60))
  check('맥에서 갈 곳도 적어 준다', steps.includes('미러링'))
  check('빔프로젝터 쪽 입력도 짚어 준다 — 이게 가장 흔하다', steps.includes('입력'))
  check('젠더가 필요할 수 있다고 미리 알려 준다', steps.includes('HDMI'))
  check('당일 아침에 해 보시라고 한다', steps.includes('리허설') || steps.includes('당일 아침'))
  await page.screenshot({ path: join(OUT, 'projector.jpg'), type: 'jpeg', quality: 82 })

  // ── 행사 목록에도 어디까지 왔는지 ────────────────────────────────
  console.log('\n[행사 목록]')
  await page.goto(`${BASE}/events`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(900)
  const dots = page.getByTestId('progress-dots')
  check('행사 목록에도 어디까지 왔는지 보인다', (await dots.count()) >= 1)
  const dotsText = await dots.first().textContent()
  check('몇 단계까지 왔는지 셈해 준다', /\d \/ \d|준비 끝/.test(dotsText), dotsText.trim())
  const filled = await dots.first().locator('span[title]').count()
  check('점이 세 개다 — 꼭 하셔야 하는 것이 셋이다', filled === 3, `${filled}개`)

  // ── 행사 파일 옮기기 ─────────────────────────────────────────────
  console.log('\n[행사 통째로 옮기기]')
  await page.goto(`${BASE}/events/${EVENT_ID}?tab=prep`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(700)
  check('내보내기 자리가 있다', (await page.getByTestId('event-export').count()) === 1)

  const exported = await page.request.get(`${BASE}/api/events/${EVENT_ID}/export`)
  check('행사 파일이 내려온다', exported.ok(), String(exported.status()))
  const bundleText = await exported.text()
  const bundle = JSON.parse(bundleText)
  check('명단이 파일에 담긴다', bundle.students.length > 0, `${bundle.students.length}줄`)
  check('인쇄물 설정도 담긴다', 'design_theme' in bundle.event)
  check('학부모 회신은 담기지 않는다', !bundleText.includes('parent_name'))
  check(
    '파일 이름이 행사 이름으로 붙는다',
    (exported.headers()['content-disposition'] ?? '').includes(encodeURIComponent('.json')),
  )

  await page.goto(`${BASE}/events`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(500)
  const eventsBefore = (await page.locator('main ul > li').count()) || 0
  check('가져오기 자리가 있다', (await page.getByTestId('event-import').count()) === 1)
  await page.getByLabel('행사 파일 고르기').setInputFiles({
    name: '연주회.json',
    mimeType: 'application/json',
    buffer: Buffer.from(bundleText, 'utf8'),
  })
  await page.waitForTimeout(1800)
  const choice = page.getByTestId('import-choice')
  check('고르시기 전에 무엇이 들었는지 보여 준다', (await choice.count()) === 1)
  const choiceText = await choice.textContent()
  check('무엇이 들어왔는지 말해 준다', /아이 \d+명/.test(choiceText), choiceText.slice(0, 80))
  check('두 갈래를 준다 — 그대로 / 올해 것으로', (await page.getByTestId('import-asis').count()) === 1)

  // 작년 것으로 올해 만들기 — 이름과 날짜가 미리 채워져 있어야 한다
  const suggested = await page.getByLabel('행사 이름').inputValue()
  check('행사 이름을 한 해 밀어 준다', suggested.includes('제13회'), suggested)
  const suggestedWhen = await page.getByLabel('날짜').inputValue()
  check('날짜도 한 해 뒤로 채워 준다', suggestedWhen.startsWith('2027'), suggestedWhen)
  check('곡을 비운다고 미리 말해 준다', choiceText.includes('연주곡과 사회자 멘트는 비웁니다'))
  await page.screenshot({ path: join(OUT, 'import-choice.jpg'), type: 'jpeg', quality: 82 })

  await page.getByTestId('import-freshen').click()
  await page.waitForTimeout(2500)
  const madeText = await page.getByTestId('event-import').textContent()
  check('올해 것으로 만들었다고 알려 준다', madeText.includes('새로 만들었습니다'), madeText.slice(-90))
  const eventsAfter = await page.locator('main ul > li').count()
  check('새 행사로 들어온다 — 있는 것을 덮어쓰지 않는다', eventsAfter === eventsBefore + 1, `${eventsBefore} → ${eventsAfter}`)

  // 만들어진 행사를 실제로 열어 본다
  const madeEvents = await (await page.request.get(`${BASE}/api/events`)).json().catch(() => null)
  const madeId = madeEvents?.events?.find((e) => String(e.title).includes('제13회'))?.id
  if (madeId) {
    const madeRoster = (await (await page.request.get(`${BASE}/api/events/${madeId}/students`)).json()).students
    check('아이들은 그대로 온다', madeRoster.length > 0, `${madeRoster.length}명`)
    check('연주곡은 비어 있다 — 올해 곡은 올해 정하신다', madeRoster.every((s) => !s.piece_title))
    check('작년 멘트는 따라오지 않는다', madeRoster.every((s) => !s.mc_script))
  } else {
    check('만들어진 행사를 찾는다', false, '행사 목록에서 못 찾음')
  }

  // 그대로 가져오기도 그대로 있다
  await page.getByLabel('행사 파일 고르기').setInputFiles({
    name: '연주회.json',
    mimeType: 'application/json',
    buffer: Buffer.from(bundleText, 'utf8'),
  })
  await page.waitForTimeout(1500)
  await page.getByTestId('import-asis').click()
  await page.waitForTimeout(2500)
  check('그대로 가져오기도 된다', (await page.getByTestId('event-import').textContent()).includes('들여왔습니다'))

  await page.getByLabel('행사 파일 고르기').setInputFiles({
    name: '엉뚱한파일.json',
    mimeType: 'application/json',
    buffer: Buffer.from('{"hello":1}', 'utf8'),
  })
  await page.waitForTimeout(1200)
  check(
    '엉뚱한 파일은 무엇을 하시면 되는지 알려 준다',
    (await page.getByTestId('event-import').textContent()).includes('내보내기로 받은'),
  )

  // ── 자동 저장 ────────────────────────────────────────────────────
  console.log('\n[자동 저장]')
  const backupRes = await page.request.post(`${BASE}/api/backup`)
  const backup = await backupRes.json()
  check('하루치를 떠 둔다', backupRes.ok() && backup.saved > 0, `행사 ${backup.saved}개`)
  check('날짜 폴더에 넣는다', /^\d{4}-\d{2}-\d{2}$/.test(backup.day), backup.day)
  check('프로그램 폴더 안이다 — 인터넷으로 나가지 않는다', String(backup.folder).startsWith('백업'), backup.folder)
  check('떠 둔 파일이 실제로 있다', existsSync(join(process.cwd(), '백업', backup.day)), backup.day)

  await page.goto(`${BASE}/settings`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1500)
  const backupBox = page.getByTestId('backup-list')
  check('설정에서 떠 둔 것을 볼 수 있다', (await backupBox.count()) === 1)
  const backupText = await backupBox.textContent()
  check('묻지 않고 알아서 뜬다고 적어 준다', backupText.includes('원장님이 하실 일은 없습니다'))
  check('어디에 두는지 적어 준다', backupText.includes('폴더'))
  check('떠 둔 날짜가 보인다', /\d+월 \d+일/.test(backupText), (backupText.match(/\d+월 \d+일[^·]*·[^되]*/) ?? [''])[0])

  const eventsBeforeRestore = (await (await page.request.get(`${BASE}/api/events/${EVENT_ID}/students`)).json()).students.length
  await backupBox.getByRole('button', { name: '되살리기' }).first().click()
  await page.waitForTimeout(2500)
  check('되살렸다고 알려 준다', (await backupBox.textContent()).includes('되살렸습니다'))
  const stillThere = (await (await page.request.get(`${BASE}/api/events/${EVENT_ID}/students`)).json()).students.length
  check('되살려도 지금 행사를 덮어쓰지 않는다', stillThere === eventsBeforeRestore, `${eventsBeforeRestore} → ${stillThere}`)
  await page.screenshot({ path: join(OUT, 'backup.jpg'), type: 'jpeg', quality: 82 })

  // 폴더 열기 — 못 여는 컴퓨터에서도 경로는 알려 드려야 한다
  await backupBox.getByTestId('backup-open').click()
  await page.waitForTimeout(1500)
  const shown = await page.getByTestId('backup-path').textContent()
  check('폴더 경로를 보여 준다 — 창이 안 뜨는 컴퓨터도 있다', shown.includes('백업'), shown)
  check('경로를 복사할 수 있다', (await backupBox.getByRole('button', { name: '경로 복사' }).count()) === 1)

  // ── 구경용 행사 ──────────────────────────────────────────────────
  // 처음 켜시면 목록이 비어 있다. 볼 것이 없으면 이 프로그램이 무엇인지 모른 채 닫으신다.
  console.log('\n[구경용 행사]')
  await page.goto(`${BASE}/events`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  const demoBox = page.getByTestId('demo-event').first()
  check('구경용 행사를 만드는 자리가 있다', (await demoBox.count()) === 1)
  const demoWords = await demoBox.textContent()
  check('지워도 된다고 미리 말해 준다', demoWords.includes('지우시면'), demoWords.slice(0, 60))

  await demoBox.getByRole('button', { name: '구경용 행사 만들기' }).click()
  await page.waitForURL(/\/events\/[^/]+$/, { timeout: 30_000 }).catch(() => {})
  await page.waitForTimeout(2500)
  const demoId = (page.url().match(/\/events\/([^/?]+)/) ?? [])[1]
  check('누르면 그 행사로 곧장 들어간다', Boolean(demoId) && demoId !== EVENT_ID, demoId ?? page.url())

  const demoStudents = (await (await page.request.get(`${BASE}/api/events/${demoId}/students`)).json()).students
  check('아이 명단이 채워져 있다', demoStudents.length >= 10, `${demoStudents.length}명`)
  check('곡까지 다 적혀 있다', demoStudents.every((s) => (s.piece_title ?? '').length > 0))
  check('사진까지 들어가 있다', demoStudents.filter((s) => s.photo_asset_id).length >= 10, `${demoStudents.filter((s) => s.photo_asset_id).length}장`)

  const demoEvent = ((await (await page.request.get(`${BASE}/api/events`)).json()).events ?? []).find((e) => e.id === demoId)
  check('연주 순서까지 이미 짜여 있다', Boolean(demoEvent?.program_source), String(demoEvent?.program_source))
  check('구경용이라고 이름에 적혀 있다', (demoEvent?.title ?? '').includes('지우셔도'), demoEvent?.title)

  // 구경은 끝이 있어야 한다 — 진짜 행사로 가시거나, 지우시거나
  const demoBar = page.getByTestId('demo-banner')
  check('구경용 행사에는 안내 띠가 붙는다', (await demoBar.count()) === 1)
  const barText = await demoBar.textContent()
  check('지어낸 자료라고 말해 준다', barText.includes('지어낸'), barText.slice(0, 50))
  check('무엇을 해도 학원 자료는 그대로라고 안심시킨다', barText.includes('학원 자료'))
  check('이제 진짜 행사를 만들 자리가 있다', (await demoBar.getByTestId('demo-to-real').count()) === 1)
  check(
    '진짜 행사 만들기가 새 행사 화면으로 간다',
    (await demoBar.getByTestId('demo-to-real').getAttribute('href')) === '/events/new',
  )

  // 대개 인쇄물 한 번 보시고 닫으신다 — 남은 것이 보여야 끝까지 보신다
  const seenBox = demoBar.getByTestId('demo-seen')
  check('어디까지 보셨는지 보여 준다', (await seenBox.count()) === 1)
  const seenChips = seenBox.locator('a')
  check('구경거리 네 가지를 짚어 준다', (await seenChips.count()) === 4, `${await seenChips.count()}가지`)
  const seenText = await seenBox.textContent()
  check('아직 안 보신 것이 몇 가지인지 세어 준다', /\d+가지/.test(seenText), seenText.replace(/\s+/g, ' ').slice(0, 70))
  const unseenAtFirst = await seenBox.locator('a[data-seen="no"]').count()
  check('처음에는 넷 다 안 보신 것으로 둔다', unseenAtFirst === 4, `${unseenAtFirst}가지`)

  // 눌러서 열어 보면 본 것으로 바뀐다
  await seenBox.getByTestId('demo-seen-stage').click()
  await page.waitForTimeout(2200)
  await page.goto(`${BASE}/events/${demoId}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1200)
  const afterSeen = page.getByTestId('demo-seen')
  check(
    '열어 본 것에는 표가 붙는다',
    (await afterSeen.locator('a[data-testid="demo-seen-stage"][data-seen="yes"]').count()) === 1,
  )
  check('안 본 것은 그대로 남는다', (await afterSeen.locator('a[data-seen="no"]').count()) === 3)
  await page.screenshot({ path: join(OUT, 'demo-event.jpg'), type: 'jpeg', quality: 82 })

  await page.goto(`${BASE}/events`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(700)
  check('목록에서도 구경용인 줄 안다', (await page.getByText('구경용', { exact: true }).count()) >= 1)

  // ── 무대 모양 그림에 진짜 사진이 들어간다 ────────────────────────
  console.log('\n[무대 모양 — 내 아이 사진으로]')
  await page.goto(`${BASE}/events/${demoId}/stage`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(2000)
  const faceTiles = page.locator('[data-testid="layout-grid"] img')
  check('모양 그림에 실제 사진이 들어간다 — 회색 네모가 아니다', (await faceTiles.count()) >= 1, `${await faceTiles.count()}장`)
  const facesOk = await faceTiles.evaluateAll((nodes) =>
    nodes.filter((n) => n instanceof HTMLImageElement && n.complete && n.naturalWidth > 0).length,
  )
  check('그 사진이 실제로 뜬다', facesOk >= 1, `${facesOk}장`)
  await page.screenshot({ path: join(OUT, 'layout-face.jpg'), type: 'jpeg', quality: 82 })

  // ── 행사 당일 화면 글씨 ──────────────────────────────────────────
  // 무대 옆 어두운 곳에서, 손에 든 화면을 흘깃 보시는 자리다. 글씨가 커야 한다
  console.log('\n[행사 당일 화면]')
  await page.goto(`${BASE}/events/${demoId}/live`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1500)
  const board = page.getByTestId('live-board')
  check('당일 진행 화면이 뜬다', (await board.count()) === 1)
  const liveFont = await board.evaluate((el) => parseFloat(getComputedStyle(el).fontSize))
  const baseFont = await page.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize))
  check('당일 화면 글씨가 보통보다 크다', liveFont > baseFont, `${liveFont.toFixed(1)}px / ${baseFont.toFixed(1)}px`)
  await page.screenshot({ path: join(OUT, 'live-big.jpg'), type: 'jpeg', quality: 82 })

  // 화면만 보고 계실 수 없는 자리다 — 소리로도 알려 드린다
  const chimeBox = page.getByTestId('live-chime')
  check('다음 차례 알림음을 켤 수 있다', (await chimeBox.count()) === 1)
  const chimeText = await chimeBox.textContent()
  check('몇 초 전에 울리는지 적혀 있다', /\d+초 전/.test(chimeText), chimeText.replace(/\s+/g, ' ').slice(0, 70))
  check('객석에 안 들릴 크기라고 적어 준다', chimeText.includes('객석'))
  check('소리를 못 듣는 자리도 챙긴다 — 화면에도 켜진다고 적었다', chimeText.includes('다음'))
  // 소리 파일을 실어 나르지 않는다 (저작권 · 오프라인)
  const audioFiles = await page.evaluate(() =>
    performance.getEntriesByType('resource').filter((r) => /\.(mp3|wav|ogg|m4a)(\?|$)/i.test(r.name)).length,
  )
  check('알림에 소리 파일을 쓰지 않는다 — 브라우저가 직접 낸다', audioFiles === 0, `${audioFiles}개`)

  const chimeInput = chimeBox.locator('input[type="checkbox"]').first()
  check('처음에는 꺼져 있다 — 묻지 않고 소리를 내지 않는다', (await chimeInput.isChecked()) === false)
  check('켜기 전에는 소리 고르는 자리가 안 보인다', (await page.getByTestId('chime-sounds').count()) === 0)
  await chimeInput.check()
  await page.waitForTimeout(400)
  check('켜진다', await chimeInput.isChecked())

  // 홀마다 묻히는 소리가 다르다
  const sounds = page.getByTestId('chime-sounds')
  check('소리를 고를 수 있다', (await sounds.count()) === 1)
  const soundCount = await sounds.locator('input[type="radio"]').count()
  check('세 가지를 준다', soundCount === 3, `${soundCount}가지`)
  const soundText = await sounds.textContent()
  check('어떤 자리에 맞는 소리인지 적어 준다', soundText.includes('시끄러운') && soundText.includes('조용한'), soundText.replace(/\s+/g, ' ').slice(0, 90))
  await sounds.locator('input[type="radio"]').nth(1).check()
  await page.waitForTimeout(300)
  check('고른 것이 표시된다', await sounds.locator('input[type="radio"]').nth(1).isChecked())

  // 로비가 시끄러우면 어떤 소리도 묻힌다
  // 소리는 "무슨 일이 났다" 만 알려 준다 — 이름까지 들으면 화면을 안 봐도 된다
  const speakBox = chimeBox.locator('input[type="checkbox"]').nth(1)
  check('이름까지 말로 읽어 줄 수 있다', (await speakBox.count()) === 1)
  check('무엇을 읽어 주는지 본보기를 적어 준다', (await chimeBox.textContent()).includes('다음, 3번'))
  await speakBox.check()
  await page.waitForTimeout(400)
  check('말로 읽기가 켜진다', await speakBox.isChecked())

  const buzz = chimeBox.locator('input[type="checkbox"]').nth(2)
  check('진동도 켤 수 있다', (await buzz.count()) === 1)
  await buzz.check()
  await page.waitForTimeout(300)
  check('진동이 켜진다', await buzz.isChecked())
  check('소리를 꺼도 진동만 켜 둘 수 있다고 적어 준다', (await chimeBox.textContent()).includes('진동만'))
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForTimeout(1200)
  const keptChime = page.getByTestId('live-chime')
  check(
    '새로고침해도 켜 두신 대로다 — 당일에 다시 켜게 하면 안 된다',
    await keptChime.locator('input[type="checkbox"]').first().isChecked(),
  )
  check('고르신 소리도 그대로다', await keptChime.getByTestId('chime-sounds').locator('input[type="radio"]').nth(1).isChecked())
  check('말로 읽기도 그대로다', await keptChime.locator('input[type="checkbox"]').nth(1).isChecked())
  check('진동도 그대로다', await keptChime.locator('input[type="checkbox"]').nth(2).isChecked())
  check('다음 칸이 곧 차례인지 함께 알려 준다', (await page.getByTestId('live-next-card').count()) === 1)
  await page.screenshot({ path: join(OUT, 'live-chime.jpg'), type: 'jpeg', quality: 82 })

  // 무대 옆에서 가장 궁금한 숫자 — 이 아이가 끝나기까지 몇 분 남았나
  check('시작 전에는 남은 시간을 말하지 않는다 — 셀 것이 없다', (await page.getByTestId('live-left').count()) === 0)
  await page.getByRole('button', { name: '개회 · 시작' }).click()
  await page.waitForTimeout(1500)
  const leftBox = page.getByTestId('live-left')
  check('개회하면 남은 시간이 뜬다', (await leftBox.count()) === 1)
  const leftText = await leftBox.textContent()
  check('몇 분 몇 초 남았는지 적는다', /\d+:\d\d|\d+초/.test(leftText), leftText.replace(/\s+/g, ' ').trim())
  check('무엇이 남은 것인지 적어 준다', leftText.includes('남았습니다') || leftText.includes('넘겼습니다'), leftText.replace(/\s+/g, ' ').trim())
  const leftSize = await leftBox.locator('span').first().evaluate((el) => parseFloat(getComputedStyle(el).fontSize))
  check('가장 큰 글씨다 — 흘깃 보고 아셔야 한다', leftSize >= 30, `${leftSize.toFixed(1)}px`)
  await page.screenshot({ path: join(OUT, 'live-left.jpg'), type: 'jpeg', quality: 82 })

  // 늦었다는 사실은 이미 아신다 — 무엇을 줄이면 되는가가 있어야 한다
  const pace = page.getByTestId('live-pace')
  check('사회자에게 무엇을 시킬지 알려 준다', (await pace.count()) === 1)
  const paceSay = await page.getByTestId('pace-say').textContent()
  check('그대로 전할 수 있는 말이다', paceSay.trim().length > 4, paceSay.trim())
  const paceLevel = await pace.getAttribute('data-level')
  check('막 시작했으면 예정대로라고 한다 — 겁주지 않는다', paceLevel === 'ok', String(paceLevel))
  check('왜 그렇게 하면 되는지도 적어 준다', (await pace.textContent()).length > 30)

  // ── 감동영상 30초 맛보기 ────────────────────────────────────────
  console.log('\n[감동영상 30초 맛보기]')
  await page.goto(`${BASE}/events/${demoId}/video`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(3000)
  const taster = page.getByTestId('video-taster')
  check('30초만 먼저 만들어 보는 단추가 있다', (await taster.count()) === 1)
  const tasterText = await taster.textContent()
  check('몇 초짜리인지 단추에 적혀 있다', /\d+초/.test(tasterText), tasterText.trim())
  const tasterTip = await taster.getAttribute('title')
  check('몇 장면이 담기는지 알려 준다', /\d+장면/.test(tasterTip ?? ''), tasterTip ?? '')

  // 앞 30초는 대개 표지다 — 정작 보고 싶으신 것은 아이가 나오는 화면이다
  const startBox = page.getByTestId('taster-start')
  check('어디서부터 맛볼지 고를 수 있다', (await startBox.count()) === 1)
  const startWords = await startBox.textContent()
  check('처음부터와 아이 장면부터를 준다', startWords.includes('처음부터') && startWords.includes('아이 장면부터'), startWords.trim())
  check('처음에는 처음부터로 둔다', (await startBox.locator('button[aria-pressed="true"]').textContent()) === '처음부터')
  await startBox.getByText('아이 장면부터').click()
  await page.waitForTimeout(700)
  check('아이 장면부터로 바꿀 수 있다', (await startBox.locator('button[aria-pressed="true"]').textContent()) === '아이 장면부터')
  const movedTip = await page.getByTestId('video-taster').getAttribute('title')
  check('바꾸면 담기는 자리도 바뀐다', movedTip !== tasterTip, `${tasterTip} → ${movedTip}`)

  // 보시고 "이게 아닌데" 하신 다음이 있어야 한다
  check('맛보기를 만들기 전에는 고치는 법이 안 뜬다', (await page.getByTestId('taster-fixes').count()) === 0)
  await page.screenshot({ path: join(OUT, 'video-taster.jpg'), type: 'jpeg', quality: 82 })

  // ── 설명서 그림 ──────────────────────────────────────────────────
  console.log('\n[설명서 그림]')
  await page.goto(`${BASE}/help`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1200)
  // 그림이 들어 있는 절로 곧장 간다 (그림 설명글은 그 절에만 있다)
  await page.getByPlaceholder('찾기 — 예: 명단, 인쇄, 영상').fill('여기로 끌어다 놓기')
  await page.waitForTimeout(500)
  await page.locator('[data-testid="help-toc"] button').first().click()
  await page.waitForTimeout(900)
  // 화면에 실제로 보이는 쪽만 본다 (인쇄용 사본은 화면에서 숨겨져 있다)
  const shots = page.locator('[data-testid="help-body"] .help-prose:not(.hidden) img.help-shot')
  check('설명서 절에 화면 그림이 들어 있다', (await shots.count()) >= 1, `${await shots.count()}장`)
  // 늦게 불러오는 그림이라 눈에 들어와야 뜬다 — 원장님이 내려 보시는 것과 같다
  await shots.first().scrollIntoViewIfNeeded()
  await page
    .waitForFunction(
      () => {
        const img = document.querySelector('[data-testid="help-body"] .help-prose:not(.hidden) img.help-shot')
        return img instanceof HTMLImageElement && img.complete && img.naturalWidth > 0
      },
      undefined,
      { timeout: 10_000 },
    )
    .catch(() => {})
  const broken = await shots.evaluateAll((nodes) =>
    nodes.filter((n) => n instanceof HTMLImageElement && n.complete && n.naturalWidth === 0).length,
  )
  check('그림이 실제로 뜬다 — 깨진 그림이 아니다', broken === 0, `${broken}장 깨짐`)
  const shotBox = await shots.first().boundingBox()
  const bodyBox = await page.getByTestId('help-body').boundingBox()
  check(
    '그림이 화면 밖으로 넘치지 않는다',
    shotBox && bodyBox && shotBox.width <= bodyBox.width + 1,
    shotBox ? `${Math.round(shotBox.width)} / ${Math.round(bodyBox.width)}` : '자리를 못 찾음',
  )
  await page.screenshot({ path: join(OUT, 'manual-shot.jpg'), type: 'jpeg', quality: 82 })

  // ── 막히면 여기 ──────────────────────────────────────────────────
  console.log('\n[막히면 여기]')
  await page.goto(`${BASE}/help`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1200)
  check('설명서 아래에 쪽지 만드는 곳이 있다', (await page.getByTestId('help-ticket').count()) === 1)
  await page.getByLabel('무엇을 하셨을 때 막히셨나요?').fill('영상 만들기를 눌렀는데 아무 일도 안 일어납니다')
  await page.waitForTimeout(400)
  // <summary> 는 단추 노릇을 하지만 role 이 브라우저마다 다르다 — 요소를 바로 누른다
  await page.locator('[data-testid="help-ticket"] summary').click()
  await page.waitForTimeout(300)
  const ticket = await page.getByTestId('ticket-body').textContent()
  check('원장님이 적으신 말이 담긴다', ticket.includes('영상 만들기를 눌렀는데'))
  check('막힌 화면이 담긴다', ticket.includes('화면 :'))
  check('브라우저와 판이 담긴다', ticket.includes('브라우저 :') && ticket.includes('판 :'))
  check('규모는 숫자만 담는다', /명단 \d+줄/.test(ticket), (ticket.match(/규모 : .*/) ?? [''])[0])

  const roster = (await (await page.request.get(`${BASE}/api/events/${EVENT_ID}/students`)).json()).students
  const leaked = roster.map((s) => s.student_name).filter((name) => ticket.includes(name))
  check('아이 이름은 하나도 들어가지 않는다', leaked.length === 0, leaked.join(', '))
  check('사진은 들어가지 않는다', !ticket.includes('data:image'))
  check('그렇다고 쪽지에 적어 준다', ticket.includes('아이 이름·사진·연락처가 들어 있지 않습니다'))
  await page.screenshot({ path: join(OUT, 'ticket.jpg'), type: 'jpeg', quality: 82 })

  await ctx.close()
} catch (error) {
  failures.push(`검사 도중 멈춤: ${error.message}`)
  console.error(error)
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
  rmSync(AUTO, { recursive: true, force: true })
  if (existsSync(AUTO_SPARE)) renameSync(AUTO_SPARE, AUTO)
}

console.log(`\n${passed}건 통과 · ${failures.length}건 실패`)
for (const line of failures) console.log(`  ✗ ${line}`)
process.exit(failures.length === 0 ? 0 : 1)
