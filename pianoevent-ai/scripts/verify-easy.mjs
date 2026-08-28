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
  check('다음 걸음으로 넘어간다', (await tour.textContent()).includes('학생 명단 넣기'))
  await page.screenshot({ path: join(OUT, 'first-run.jpg'), type: 'jpeg', quality: 82 })

  await page.getByTestId('first-run-close').click()
  await page.waitForTimeout(200)
  check('닫으면 사라진다', (await page.getByTestId('first-run').count()) === 0)
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForTimeout(500)
  check('새로고침해도 다시 뜨지 않는다', (await page.getByTestId('first-run').count()) === 0)

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

  // ── 되돌리기 ─────────────────────────────────────────────────────
  console.log('\n[되돌리기]')
  const before = (await (await page.request.get(`${BASE}/api/events/${EVENT_ID}/students`)).json()).students.length
  await page.getByLabel('학생 명단 붙여넣기').fill(pasted)
  await page.waitForTimeout(400)
  await page.getByRole('button', { name: '명단에 추가' }).click()
  await page.waitForTimeout(1800)
  const added = (await (await page.request.get(`${BASE}/api/events/${EVENT_ID}/students`)).json()).students.length
  check('명단이 늘었다', added === before + 3, `${before} → ${added}`)
  check('되돌리기 단추가 뜬다', (await page.getByTestId('roster-undo').count()) === 1)

  await page.getByRole('button', { name: '되돌리기' }).click()
  await page.waitForTimeout(1800)
  const undone = (await (await page.request.get(`${BASE}/api/events/${EVENT_ID}/students`)).json()).students
  check('붙여넣기 전으로 그대로 돌아간다', undone.length === before, `${added} → ${undone.length}`)
  check('되돌린 명단에 방금 넣은 아이가 없다', !undone.some((s) => s.student_name === '한여울'))

  // ── 표에서 고친 것 되돌리기 ─────────────────────────────────────
  console.log('\n[표에서 고친 것 되돌리기]')
  await page.goto(`${BASE}/events/${EVENT_ID}?tab=roster`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(900)
  check('아무것도 안 고쳤으면 되돌리기 띠가 없다', (await page.getByTestId('edit-undo').count()) === 0)

  const firstRow = page.getByTestId('roster-table').locator('tbody tr').first()
  const pieceCell = firstRow.locator('input[aria-label="연주곡"]')
  const wasPiece = await pieceCell.inputValue()
  await pieceCell.fill('잘못 친 곡')
  await pieceCell.blur()
  await page.waitForTimeout(1600)

  const undoBar = page.getByTestId('edit-undo')
  check('고치면 되돌리기 띠가 뜬다', (await undoBar.count()) === 1)
  const undoText = await undoBar.textContent()
  check('무엇을 무엇으로 되돌리는지 미리 보여 준다', undoText.includes(wasPiece), undoText.slice(0, 80))
  check('누구의 어느 칸인지 적어 준다', undoText.includes('연주곡'))
  await page.screenshot({ path: join(OUT, 'edit-undo.jpg'), type: 'jpeg', quality: 82 })

  await undoBar.getByRole('button', { name: '되돌리기' }).click()
  await page.waitForTimeout(1800)
  const backTo = await page.getByTestId('roster-table').locator('tbody tr').first().locator('input[aria-label="연주곡"]').inputValue()
  check('고치기 전 값으로 돌아간다', backTo === wasPiece, `${backTo} / ${wasPiece}`)
  check('되돌린 것이 다시 쌓이지 않는다', (await page.getByTestId('edit-undo').count()) === 0)

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
  await page.waitForTimeout(2000)
  const importText = await page.getByTestId('event-import').textContent()
  check('무엇이 들어왔는지 말해 준다', /아이 \d+명/.test(importText), importText.slice(-80))
  const eventsAfter = await page.locator('main ul > li').count()
  check('새 행사로 들어온다 — 있는 것을 덮어쓰지 않는다', eventsAfter === eventsBefore + 1, `${eventsBefore} → ${eventsAfter}`)

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

  // ── 설명서 그림 ──────────────────────────────────────────────────
  console.log('\n[설명서 그림]')
  await page.goto(`${BASE}/help`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1200)
  // 그림이 들어 있는 절로 곧장 간다 (그림 설명글은 그 절에만 있다)
  await page.getByPlaceholder('찾기 — 예: 명단, 인쇄, 영상').fill('엑셀 파일 놓는 자리')
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
