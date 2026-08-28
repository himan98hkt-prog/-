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
import { spawn, spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs'
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
  // 리브레오피스가 있으면 만든 pptx 를 실제로 열어 본다 (없는 환경에서는 그 검사만 건너뛴다)
  const soffice = spawnSync('which', ['soffice'], { encoding: 'utf8' }).stdout.trim()

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

  // 테마를 바꾸면 화면이 그 자리에서 바뀌는가
  const slideBefore = await slide.evaluate((node) => getComputedStyle(node).backgroundColor)
  await page.getByRole('button', { name: '테마 바꾸기' }).click()
  await page.waitForTimeout(250)
  check('테마 고르는 목록이 열린다', (await page.getByPlaceholder('테마 찾기 — 봄, 금색, 아이, 격식…').count()) === 1)
  await page.getByPlaceholder('테마 찾기 — 봄, 금색, 아이, 격식…').fill('크리스마스')
  await page.waitForTimeout(300)
  const found = await page.locator('button[aria-pressed]').filter({ hasText: '크리스마스' }).count()
  check('이름으로 테마를 찾을 수 있다', found > 0, `${found}종`)
  await page.locator('button[aria-pressed]').filter({ hasText: '크리스마스' }).first().click()
  await page.waitForTimeout(350)
  const slideAfter = await slide.evaluate((node) => getComputedStyle(node).backgroundColor)
  check('테마를 바꾸면 화면 색이 그 자리에서 바뀐다', slideAfter !== slideBefore, `${slideBefore} → ${slideAfter}`)
  const pptxHref = await page.getByRole('link', { name: '파워포인트로 받기' }).getAttribute('href')
  check('내려받기 주소가 고른 테마를 따라간다', (pptxHref ?? '').includes('theme='), pptxHref ?? '')

  // 화면에 넣을 것 끄기
  const beforeToggle = Number((await page.getByTestId('stage-counter').textContent()).split('/')[1].trim())
  await page.getByText('오늘의 순서').first().click()
  await page.waitForTimeout(300)
  const afterToggle = Number((await page.getByTestId('stage-counter').textContent()).split('/')[1].trim())
  check('항목을 끄면 슬라이드가 줄어든다', afterToggle < beforeToggle, `${beforeToggle} → ${afterToggle}`)
  await page.getByText('오늘의 순서').first().click()
  await page.waitForTimeout(300)
  check(
    '다시 켜면 되돌아온다',
    Number((await page.getByTestId('stage-counter').textContent()).split('/')[1].trim()) === beforeToggle,
  )

  // ── 아이 사진 ────────────────────────────────────────────────
  // 실제로 사진을 올려 아이에게 붙이고, 화면과 파워포인트 파일에 얼굴이 들어가는지 본다
  const madePhoto = await page.evaluate(async () => {
    const canvas = document.createElement('canvas')
    canvas.width = 400
    canvas.height = 400
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#C86A4A'
    ctx.fillRect(0, 0, 400, 400)
    ctx.fillStyle = '#fff'
    ctx.beginPath()
    ctx.arc(200, 170, 70, 0, Math.PI * 2)
    ctx.fill()
    return canvas.toDataURL('image/jpeg', 0.8)
  })
  const uploaded = await page.request.post(`${BASE}/api/academy/assets`, {
    data: { kind: 'photo', label: '검사용 아이 사진', url: madePhoto },
  })
  const uploadedBody = await uploaded.json()
  check('아이 사진 올리기', uploaded.ok(), String(uploaded.status()))
  const roster = await (await page.request.get(`${BASE}/api/events/${EVENT_ID}/students`)).json()
  const firstStudent = roster.students?.[0]
  const assigned = await page.request.patch(`${BASE}/api/students/${firstStudent?.id}`, {
    data: { photo_asset_id: uploadedBody.asset?.id },
  })
  check('아이에게 사진 붙이기', assigned.ok(), String(assigned.status()))
  // 화면 모양 검사를 위해 나머지 아이에게도 붙여 둔다 (연주 순서가 바뀌어도 사진이 있는 화면이 나오게)
  for (const student of (roster.students ?? []).slice(1)) {
    await page.request.patch(`${BASE}/api/students/${student.id}`, { data: { photo_asset_id: uploadedBody.asset?.id } })
  }
  const rejected = await page.request.patch(`${BASE}/api/students/${firstStudent?.id}`, {
    data: { photo_asset_id: 'no-such-asset' },
  })
  check('보관함에 없는 사진은 거절한다', rejected.status() === 400, String(rejected.status()))

  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForTimeout(500)
  const photoSlides = await page.evaluate(async () => {
    const res = await fetch(location.href)
    const html = await res.text()
    return html.includes('data:image/jpeg')
  })
  check('무대 화면에 아이 사진이 실린다', photoSlides)

  const pptxPhoto = await page.request.get(`${BASE}/api/events/${EVENT_ID}/pptx?theme=${THEME}`)
  const pptxPhotoPath = join(OUT, 'stage-photo.pptx')
  writeFileSync(pptxPhotoPath, Buffer.from(await pptxPhoto.body()))
  const photoNames = spawnSync('unzip', ['-Z1', pptxPhotoPath], { encoding: 'utf8' }).stdout.trim().split('\n')
  check('파워포인트 파일 안에 사진이 들어감', photoNames.some((name) => name.startsWith('ppt/media/')), photoNames.filter((n) => n.startsWith('ppt/media/')).join(', '))
  if (soffice) {
    const photoDir = join(OUT, 'pptx-photo')
    rmSync(photoDir, { recursive: true, force: true })
    mkdirSync(photoDir, { recursive: true })
    spawnSync(soffice, ['--headless', '--norestore', '--convert-to', 'pdf', '--outdir', photoDir, pptxPhotoPath], {
      encoding: 'utf8',
      timeout: 300_000,
    })
    check('사진이 든 파워포인트도 실제로 열린다', existsSync(join(photoDir, 'stage-photo.pdf')))
  }

  // ── 연주자 화면 모양 ──────────────────────────────────────
  // 이름이 아래쪽(피아노가 가리는 자리)에 놓이지 않는지, 사진 둘레에 빈 자리가 없는지
  const LAYOUT_NAMES = ['사진 반쪽', '사진 전체 · 오른쪽 판', '사진 전체 · 위쪽 띠', '사진 전체 · 큰 번호', '이름만 크게', '큰 번호 · 이름', '이름 · 곡 · 해설 카드']
  check('연주자 화면 모양이 여러 종이다', LAYOUT_NAMES.length === 7)

  // 사진이 붙은 연주자 화면으로 간다.
  // 테마 검색칸에 focus 가 남아 있으면 화살표·Home 이 화면을 넘기지 않는다(글자를 치는 중으로 본다)
  await page.evaluate(() => (document.activeElement instanceof HTMLElement ? document.activeElement.blur() : undefined))
  await page.keyboard.press('Home')
  await page.waitForTimeout(200)
  for (let i = 0; i < 12; i += 1) {
    const text = await slide.textContent()
    if (text && text.includes('번째 무대')) break
    await page.keyboard.press('ArrowRight')
    await page.waitForTimeout(150)
  }

  for (const name of LAYOUT_NAMES) {
    await page.getByRole('button', { name: new RegExp('^' + name) }).first().click()
    await page.waitForTimeout(300)
    const report = await slide.evaluate((node) => {
      const rect = node.getBoundingClientRect()
      let lowest = 0
      let photoArea = 0
      for (const child of node.querySelectorAll('*')) {
        const box = child.getBoundingClientRect()
        if (box.width === 0 || box.height === 0) continue
        const text = (child.textContent ?? '').trim()
        const isLeaf = child.children.length === 0
        if (isLeaf && text) lowest = Math.max(lowest, box.bottom - rect.top)
        if (child.tagName === 'IMG') photoArea = Math.max(photoArea, (box.width * box.height) / (rect.width * rect.height))
      }
      return { lowest, height: rect.height, photoArea }
    })
    // 아래 24% 는 그랜드피아노 뚜껑이 가린다 — 글자가 거기 내려가면 안 된다
    const limit = report.height * 0.78
    check(`${name} — 글자가 피아노에 가리지 않는다`, report.lowest <= limit, `${Math.round(report.lowest)} / ${Math.round(limit)}`)
    if (name.startsWith('사진')) {
      check(`${name} — 사진이 화면을 채운다`, report.photoArea >= 0.45, `${Math.round(report.photoArea * 100)}%`)
    }
    await slide.screenshot({ path: join(OUT, `layout-${name.replace(/[^가-힣]/g, '')}.jpg`), type: 'jpeg', quality: 78 })
  }
  // 사진 창 모양 · 무대 배경
  await page.getByRole('button', { name: /^배경 위 사진 액자/ }).first().click()
  await page.waitForTimeout(300)
  const SHAPES = ['원형', '둥근 사각', '사각', '아치', '타원', '육각', '나뭇잎', '마름모']
  check('사진 창 모양이 여러 종이다', SHAPES.length === 8)
  const shapeLooks = new Set()
  for (const name of SHAPES) {
    await page.getByRole('button', { name: new RegExp('^' + name + '$') }).first().click()
    await page.waitForTimeout(220)
    const look = await slide.evaluate((node) => {
      const box = node.querySelector('img')?.parentElement
      if (!box) return ''
      const style = getComputedStyle(box)
      return `${style.borderRadius}|${style.clipPath}`
    })
    shapeLooks.add(look)
  }
  check('모양마다 실제로 다르게 잘린다', shapeLooks.size === SHAPES.length, `${shapeLooks.size} / ${SHAPES.length}`)

  const BACKDROPS = ['단색', '건반', '무대 커튼', '무대 조명', '악보', '조명 방울', '그랜드피아노', '별밤', '리본 띠', '아치 무대']
  check('무대 배경이 여러 종이다', BACKDROPS.length === 10)
  const drawn = []
  for (const name of BACKDROPS) {
    await page.getByRole('button', { name: new RegExp('^' + name + '$') }).first().click()
    await page.waitForTimeout(250)
    const marks = await slide.evaluate((node) => {
      const svg = node.querySelector('svg.stage-backdrop')
      return svg ? svg.querySelectorAll('rect, circle, path, ellipse, line').length : 0
    })
    drawn.push([name, marks])
    await slide.screenshot({ path: join(OUT, `backdrop-${name.replace(/[^가-힣]/g, '')}.jpg`), type: 'jpeg', quality: 76 })
  }
  check('단색은 아무것도 그리지 않는다', drawn[0][1] === 0, String(drawn[0][1]))
  check(
    '나머지 배경은 실제로 그려진다',
    drawn.slice(1).every(([, marks]) => marks > 0),
    drawn.slice(1).map(([name, marks]) => `${name}:${marks}`).join(' '),
  )

  // 글자가 배경에 묻히지 않는지 — 배경을 켠 채 다시 잰다
  const withBackdrop = await slide.evaluate((node) => {
    const rect = node.getBoundingClientRect()
    let lowest = 0
    for (const child of node.querySelectorAll('*')) {
      const box = child.getBoundingClientRect()
      const text = (child.textContent ?? '').trim()
      if (child.children.length === 0 && text && box.height > 0) lowest = Math.max(lowest, box.bottom - rect.top)
    }
    return { lowest, height: rect.height }
  })
  check(
    '배경을 켜도 글자는 피아노 자리에 내려가지 않는다',
    withBackdrop.lowest <= withBackdrop.height * 0.78,
    `${Math.round(withBackdrop.lowest)} / ${Math.round(withBackdrop.height * 0.78)}`,
  )

  // 파워포인트에도 같은 배경·모양이 들어가는가
  const decorated = await page.request.get(
    `${BASE}/api/events/${EVENT_ID}/pptx?layout=photo-frame&shape=hexagon&backdrop=keys`,
  )
  const decoratedPath = join(OUT, 'stage-decorated.pptx')
  writeFileSync(decoratedPath, Buffer.from(await decorated.body()))
  const decoratedXml = spawnSync('unzip', ['-p', decoratedPath, 'ppt/slides/slide4.xml'], { encoding: 'utf8' }).stdout
  check('파워포인트에 사진 창 모양이 들어감', decoratedXml.includes('prst="hexagon"'))
  check('파워포인트에 무대 배경이 들어감', decoratedXml.includes('검은건반') && decoratedXml.includes('흰건반'))
  if (soffice) {
    const decDir = join(OUT, 'pptx-decorated')
    rmSync(decDir, { recursive: true, force: true })
    mkdirSync(decDir, { recursive: true })
    spawnSync(soffice, ['--headless', '--norestore', '--convert-to', 'pdf', '--outdir', decDir, decoratedPath], {
      encoding: 'utf8',
      timeout: 300_000,
    })
    check('배경·모양이 든 파워포인트도 실제로 열린다', existsSync(join(decDir, 'stage-decorated.pdf')))
  }

  await page.getByRole('button', { name: /^단색$/ }).first().click()
  await page.getByRole('button', { name: /^사진 전체 · 오른쪽 판/ }).first().click()
  await page.waitForTimeout(250)

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

  // 진짜 파워포인트 파일이 나오는가 — 원장님이 [파워포인트로 받기] 를 눌렀을 때 받는 그 파일이다
  const pptxRes = await page.request.get(`${BASE}/api/events/${EVENT_ID}/pptx?theme=${THEME}`)
  check('파워포인트 내려받기 응답', pptxRes.ok(), String(pptxRes.status()))
  check(
    '파워포인트 파일 형식으로 내려옴',
    (pptxRes.headers()['content-type'] ?? '').includes('presentationml.presentation'),
    pptxRes.headers()['content-type'] ?? '',
  )
  const pptxPath = join(OUT, 'stage.pptx')
  writeFileSync(pptxPath, Buffer.from(await pptxRes.body()))
  const listed = spawnSync('unzip', ['-Z1', pptxPath], { encoding: 'utf8' })
  const names = listed.status === 0 ? listed.stdout.trim().split('\n') : []
  check('ZIP 으로 열린다', names.length > 0, listed.stderr.trim().slice(0, 120))
  for (const required of [
    '[Content_Types].xml',
    '_rels/.rels',
    'ppt/presentation.xml',
    'ppt/_rels/presentation.xml.rels',
    'ppt/slideMasters/slideMaster1.xml',
    'ppt/slideLayouts/slideLayout1.xml',
    'ppt/theme/theme1.xml',
  ]) {
    check(`pptx 안에 ${required}`, names.includes(required))
  }
  const slideParts = names.filter((name) => /^ppt\/slides\/slide\d+\.xml$/.test(name))
  check('pptx 슬라이드 수 = 화면 슬라이드 수', slideParts.length === total, `${slideParts.length} / ${total}`)

  const firstSlide = spawnSync('unzip', ['-p', pptxPath, 'ppt/slides/slide1.xml'], { encoding: 'utf8' }).stdout
  check('첫 장에 행사 제목이 글자로 들어감', firstSlide.includes('<a:t>제12회 정기 연주회</a:t>'))
  check('글상자로 들어감 (그림이 아님)', firstSlide.includes('txBox="1"'))
  const anySlide = slideParts
    .map((name) => spawnSync('unzip', ['-p', pptxPath, name], { encoding: 'utf8' }).stdout)
    .join('')
  check('연주자 이름이 글자로 들어감', anySlide.includes('<a:t>윤채원</a:t>'))
  check('XML 이 깨지지 않음', !/&(?!amp;|lt;|gt;|quot;|apos;|#)/.test(anySlide))

  // 테마를 바꾸면 파일 색도 바뀌는가
  const other = await page.request.get(`${BASE}/api/events/${EVENT_ID}/pptx?theme=blush-romance`)
  const otherPath = join(OUT, 'stage-other.pptx')
  writeFileSync(otherPath, Buffer.from(await other.body()))
  const otherTheme = spawnSync('unzip', ['-p', otherPath, 'ppt/theme/theme1.xml'], { encoding: 'utf8' }).stdout
  const baseTheme = spawnSync('unzip', ['-p', pptxPath, 'ppt/theme/theme1.xml'], { encoding: 'utf8' }).stdout
  check('테마를 바꾸면 파워포인트 색·서체도 바뀐다', otherTheme !== baseTheme && otherTheme.length > 200)

  // 글자가 실제로 그려지는가 — XML 이 맞아도 파워포인트가 안 보여 줄 수 있다.
  // 리브레오피스가 깔려 있을 때만 돌린다 (판매용 프로그램에는 필요 없다).
  if (soffice) {
    const renderDir = join(OUT, 'pptx-render')
    rmSync(renderDir, { recursive: true, force: true })
    mkdirSync(renderDir, { recursive: true })
    const converted = spawnSync(
      soffice,
      ['--headless', '--norestore', '--convert-to', 'pdf', '--outdir', renderDir, pptxPath],
      { encoding: 'utf8', timeout: 300_000 },
    )
    const rendered = join(renderDir, 'stage.pdf')
    check('파워포인트 파일이 실제로 열린다', existsSync(rendered), (converted.stderr ?? '').trim().slice(0, 160))
    if (existsSync(rendered)) {
      const text = spawnSync('pdftotext', [rendered, '-'], { encoding: 'utf8' }).stdout ?? ''
      if (text) {
        check('열어 보면 행사 제목이 보인다', text.includes('정기 연주회'))
        check('열어 보면 연주자 이름이 보인다', text.includes('윤채원'))
        // 줄 간격 단위를 틀리면 본문이 통째로 사라진다 — 그걸 잡는 검사다
        check('열어 보면 안내 문구가 보인다', text.includes('휴대전화'))
        check('열어 보면 곡 해설이 보인다', text.includes('선율') || text.includes('곡입니다'))
      }
    }
  } else {
    console.log('  · 리브레오피스가 없어 실제 열림 검사는 건너뜁니다')
  }


  // 항목을 끄면 슬라이드도 줄어드는가
  const bare = await page.request.get(`${BASE}/api/events/${EVENT_ID}/pptx?agenda=0&sections=0&commentary=0`)
  const barePath = join(OUT, 'stage-bare.pptx')
  writeFileSync(barePath, Buffer.from(await bare.body()))
  const bareSlides = spawnSync('unzip', ['-Z1', barePath], { encoding: 'utf8' })
    .stdout.trim()
    .split('\n')
    .filter((name) => /^ppt\/slides\/slide\d+\.xml$/.test(name))
  check('항목을 끄면 파워포인트도 줄어든다', bareSlides.length < slideParts.length, `${bareSlides.length}장`)

  // ── 설정 저장 · 불러오기 ────────────────────────────────────────
  await page.goto(`${BASE}/events/${EVENT_ID}/stage`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(700)
  const prefs = page.getByTestId('prefs-stage_prefs')
  check('무대 화면 설정 저장 칸이 있다', (await prefs.count()) === 1)

  // 배경과 배치를 바꾸고 저장한 뒤 다시 연다
  const backdropChip = page.getByRole('button', { name: '무대 커튼', exact: true })
  await backdropChip.click()
  await page.getByRole('button', { name: '밝은 화면' }).click().catch(() => undefined)
  await page.waitForTimeout(300)
  await prefs.getByRole('button', { name: '이 설정 저장' }).click()
  await page.waitForSelector('text=저장했습니다', { timeout: 8000 })
  check('무대 화면 설정을 저장한다', true)
  passed += 1

  await page.goto(`${BASE}/events/${EVENT_ID}/stage`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(700)
  check(
    '다시 열면 저장해 둔 배경으로 시작한다',
    (await page.getByRole('button', { name: '무대 커튼', exact: true }).getAttribute('aria-pressed')) === 'true',
  )
  check(
    '어두운/밝은 화면 선택도 그대로 열린다',
    (await page.getByRole('button', { name: '어두운 화면' }).count()) === 1,
  )

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
