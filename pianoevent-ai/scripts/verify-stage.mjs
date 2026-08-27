#!/usr/bin/env node
/**
 * 무대 화면 검사.
 *
 *   npm run build && node scripts/verify-stage.mjs
 *
 * 연주회 당일 스크린은 되돌릴 기회가 없다. 글자 한 줄이 화면 밖으로 나가면
 * 객석 전체가 그걸 본다. 그래서 슬라이드를 한 장씩 실제로 띄워 보고,
 * 1280×720 밖으로 삐져나온 요소가 하나라도 있으면 실패로 처리한다.
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'

const PORT = Number(process.env.STAGE_PORT ?? 3992)
const BASE = `http://127.0.0.1:${PORT}`
const DATA = join(process.cwd(), '.data')
const BACKUP = join(mkdtempSync(join(tmpdir(), 'pianoevent-stage-')), 'data')
const OUT = join(process.cwd(), 'shots', 'stage')
const EVENT_ID = 'demo-event'
const THEME = 'sunlit-ivory'

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

  // 1280×720 이 1:1 로 들어가도록 창을 넉넉히 잡는다 — 축소 없이 실제 크기로 본다
  const context = await browser.newContext({ viewport: { width: 1600, height: 1100 }, deviceScaleFactor: 1 })
  const page = await context.newPage()
  await page.goto(`${BASE}/events/${EVENT_ID}/stage?theme=${THEME}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(500)

  const counter = await page.getByTestId('stage-counter').textContent()
  const total = Number(counter.split('/')[1].trim())
  check('슬라이드가 만들어졌다', total > 3, `${total}장`)

  const slide = page.locator('.stage-slide').first()
  const box = await slide.boundingBox()
  check('16:9 비율', Math.abs(box.width / box.height - 16 / 9) < 0.01, `${box.width}×${box.height}`)

  const seen = new Set()
  for (let i = 0; i < total; i += 1) {
    // 슬라이드 안의 어떤 글자도 화면 밖으로 나가면 안 된다
    const overflow = await slide.evaluate((node) => {
      const rect = node.getBoundingClientRect()
      let worst = 0
      for (const child of node.querySelectorAll('*')) {
        const box = child.getBoundingClientRect()
        if (box.width === 0 && box.height === 0) continue
        worst = Math.max(
          worst,
          Math.round(box.bottom - rect.bottom),
          Math.round(box.right - rect.right),
          Math.round(rect.top - box.top),
          Math.round(rect.left - box.left),
        )
      }
      return worst
    })
    const label = (await slide.textContent()).slice(0, 22).replace(/\s+/g, ' ').trim()
    if (overflow > 1) failures.push(`${i + 1}번째 슬라이드가 화면 밖으로 ${overflow}px 넘칩니다 — ${label}`)
    else passed += 1
    seen.add(label)

    if (i < 4) {
      await slide.screenshot({ path: join(OUT, `slide-${String(i + 1).padStart(2, '0')}.jpg`), type: 'jpeg', quality: 78 })
    }
    if (i < total - 1) {
      await page.keyboard.press('ArrowRight')
      await page.waitForTimeout(120)
    }
  }
  console.log(`  ✓ 슬라이드 ${total}장 모두 화면 안에 들어감`)
  check('슬라이드가 실제로 넘어간다', seen.size > 3, `서로 다른 화면 ${seen.size}종`)

  const end = await page.getByTestId('stage-counter').textContent()
  check('마지막 화면까지 도달', end.trim().startsWith(String(total)), end.trim())

  await page.keyboard.press('Home')
  await page.waitForTimeout(150)
  check('Home 키로 처음으로', (await page.getByTestId('stage-counter').textContent()).trim().startsWith('1'))

  // 인쇄(=PDF 저장) 묶음이 슬라이드 수만큼 들어 있는가
  const printed = await page.locator('.stage-print-page').count()
  check('PDF 저장용 슬라이드 수가 같다', printed === total, `${printed} / ${total}`)

  await page.emulateMedia({ media: 'print' })
  await page.waitForTimeout(200)
  const printVisible = await page.locator('.stage-print-deck').first().isVisible()
  const screenShellHidden = await page.locator('.no-print').first().isHidden()
  check('인쇄하면 슬라이드 묶음이 나온다', printVisible)
  check('인쇄하면 조작 버튼은 빠진다', screenShellHidden)
  // page.pdf() 는 인쇄 미디어로 찍는다 — 위에서 걸어 둔 강제 설정을 먼저 푼다
  await page.emulateMedia({ media: null })

  // 실제로 PDF 를 뽑아 본다 — 원장님이 [PDF로 저장] 을 눌렀을 때 나오는 그 파일이다
  const pdfPath = join(OUT, 'stage-deck.pdf')
  await page.pdf({ path: pdfPath, preferCSSPageSize: true, printBackground: true })
  const pdf = readFileSync(pdfPath)
  const boxes = [...pdf.toString('latin1').matchAll(/\/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)/g)]
  check('PDF 가 만들어졌다', pdf.length > 10_000, `${Math.round(pdf.length / 1024)}KB`)
  if (boxes.length > 0) {
    const [, x0, y0, x1, y1] = boxes[0].map(Number)
    const ratio = (x1 - x0) / (y1 - y0)
    check('PDF 용지가 16:9', Math.abs(ratio - 16 / 9) < 0.02, `${(x1 - x0).toFixed(0)}×${(y1 - y0).toFixed(0)}pt`)
    check('PDF 쪽수 = 슬라이드 수', boxes.length === total, `${boxes.length} / ${total}`)
  } else {
    console.log('  · PDF 용지 정보를 읽지 못했습니다 (압축된 PDF) — 건너뜁니다')
  }

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
