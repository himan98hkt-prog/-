#!/usr/bin/env node
/**
 * 감동영상 홍보용 캡처 — **만드는 과정**과 **실제로 나온 화면**.
 *
 *   npm run build && node scripts/video-shots.mjs
 *
 * 상세페이지와 카드뉴스에서 「영상도 만들어집니다」라고 글로만 적으면 아무도 안 믿는다.
 * 그래서 화면을 실제로 띄워 놓고 찍는다 — 고치는 칸, 시간 띠, 자르는 칸,
 * 그리고 **뽑히는 영상 그 화면**(미리보기와 녹화가 같은 함수를 쓰므로 똑같다).
 *
 * 아이 사진은 `detail/kids/` 에 둔 **AI 로 만든 예시 사진**을 쓴다. 실제 아이 얼굴은 한 장도 쓰지 않는다.
 * 그 폴더가 비어 있으면 상품에 딸려 가는 연습용 그림으로 대신한다 —
 * 다만 그것은 **자리 표시 그림**이라 「이렇게 나옵니다」를 보여 주기에는 모자란다.
 *
 * 사진은 16:9 로 준비한다. 영상이 16:9 이고 **꽉 채워 자르기** 때문에,
 * 정사각 사진을 넣으면 위아래 44% 가 잘려 아이 머리가 날아간다.
 */
import { spawn, spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, renameSync, rmSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'
import { requireFreePort, requireFreshBuild } from './lib/fresh-build.mjs'

requireFreshBuild()

const PORT = Number(process.env.VIDEO_SHOT_PORT ?? 3987)
await requireFreePort(PORT)
const BASE = `http://127.0.0.1:${PORT}`
const OUT = join(process.cwd(), 'promo', 'video')
const PHOTOS = join(process.cwd(), '배포', '연습용-사진')
/** AI 로 만든 예시 사진 — 아이 한 명씩(이름.jpg) · 연습 갤러리(연습/*.jpg) */
const KIDS = join(process.cwd(), 'detail', 'kids')
const KIDS_EXTRA = join(KIDS, '연습')
const DATA = join(process.cwd(), '.data')
const TMP = mkdtempSync(join(tmpdir(), 'pianoevent-video-shot-'))
const BACKUP = join(TMP, 'data')
const EVENT_ID = 'demo-event'
/** 따뜻한 테마로 찍는다 — 파는 화면이 어두우면 학원 분위기와 안 맞는다 */
const THEME = 'sunlit-ivory'

const kb = (file) => Math.round(statSync(join(OUT, file)).size / 1024)

async function waitForServer(timeoutMs = 60_000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      if ((await fetch(`${BASE}/`, { redirect: 'manual' })).status < 500) return true
    } catch {
      /* 아직 */
    }
    await new Promise((r) => setTimeout(r, 400))
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
  server.stderr.on('data', (c) => {
    const line = String(c).trim()
    if (line) console.error(`  [server] ${line}`)
  })
  if (!(await waitForServer())) throw new Error(`서버가 ${BASE} 에서 뜨지 않았습니다.`)

  await fetch(`${BASE}/api/events/${EVENT_ID}/program`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  await fetch(`${BASE}/api/events/${EVENT_ID}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'published', design_theme: THEME }),
  })
  // 학부모 응원 — 영상 뒤쪽 「응원 메시지」 장면이 실제로 만들어지게
  for (const reply of [
    { parent_name: '김○○', student_name: '김서연', headcount: 3, message: '연습한 만큼만 하고 오면 돼. 우리 딸 최고!' },
    { parent_name: '박○○', student_name: '박지호', headcount: 2, message: '첫 무대 축하해! 아빠가 맨 앞에서 볼게.' },
    { parent_name: '윤○○', student_name: '윤채원', headcount: 4, message: '일 년 동안 참 많이 늘었다.' },
  ]) {
    await fetch(`${BASE}/api/rsvp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_id: EVENT_ID, attending: true, ...reply }),
    })
  }

  const executablePath = process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
  browser = await chromium.launch(existsSync(executablePath) ? { executablePath } : {})
  const context = await browser.newContext({
    viewport: { width: 1480, height: 1000 },
    deviceScaleFactor: 1.5,
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul',
  })
  const page = await context.newPage()
  page.on('pageerror', (e) => console.error(`  [화면 오류] ${e.message}`))

  /*
   * 아이마다 사진을 붙인다.
   *
   * 사진이 없으면 이름만 지나가는 장면이 되어 「영상이 이렇게 나옵니다」를 보여 줄 수가 없다.
   * 연습용 그림은 SVG 라 캔버스에서 한 번 구워 PNG 로 올린다 —
   * 그림 파일 종류를 가리지 않고 받는다는 것도 이 자리에서 함께 확인된다.
   */
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' })
  const roster = await (await page.request.get(`${BASE}/api/events/${EVENT_ID}/students`)).json()
  const names = (roster.students ?? []).map((s) => s.student_name)
  console.log(`  · 명단 ${names.length}명: ${names.slice(0, 4).join(' ')}${names.length > 4 ? ' …' : ''}`)

  /**
   * 아이마다 사진을 붙인다.
   *
   * 사진이 없으면 이름만 지나가는 장면이 되어 「영상이 이렇게 나옵니다」를 보여 줄 수가 없다.
   * `detail/kids/이름.jpg` 가 있으면 그것을, 없으면 연습용 그림(SVG)을 굽는다.
   */
  const photoFiles = existsSync(KIDS)
    ? readdirSync(KIDS).filter((f) => /\.(jpe?g|png)$/i.test(f))
    : []
  const usingReal = photoFiles.length > 0
  console.log(usingReal ? `  · 예시 사진 ${photoFiles.length}장을 씁니다` : '  · 예시 사진이 없어 연습용 그림으로 대신합니다')

  const attach = async (studentName, dataUrl, label) => {
    const student = (roster.students ?? []).find((s) => s.student_name === studentName)
    if (!student) return false
    const made = await page.request.post(`${BASE}/api/academy/assets`, {
      data: { kind: 'photo', label, url: dataUrl },
    })
    const body = await made.json()
    await page.request.patch(`${BASE}/api/students/${student.id}`, { data: { photo_asset_id: body.asset.id } })
    return true
  }

  /** 파일을 데이터 주소로 — 브라우저를 거치지 않으므로 한글 이름도 안전하다 */
  const asDataUrl = (path) => {
    const ext = path.toLowerCase().endsWith('.png') ? 'png' : 'jpeg'
    return `data:image/${ext};base64,${readFileSync(path).toString('base64')}`
  }

  let attached = 0
  if (usingReal) {
    for (const file of photoFiles) {
      const name = file.replace(/\.[^.]+$/, '')
      if (await attach(name, asDataUrl(join(KIDS, file)), `${name} 연습`)) attached += 1
    }
  } else {
    for (const file of readdirSync(PHOTOS).filter((f) => f.endsWith('.svg'))) {
      const name = file.replace(/\.svg$/, '')
      if (!(roster.students ?? []).some((s) => s.student_name === name)) continue
      const svg = readFileSync(join(PHOTOS, file), 'utf8')
      const baked = await page.evaluate(
        (source) =>
          new Promise((resolve) => {
            const img = new Image()
            img.onload = () => {
              const canvas = document.createElement('canvas')
              canvas.width = 480
              canvas.height = 480
              canvas.getContext('2d').drawImage(img, 0, 0, 480, 480)
              resolve(canvas.toDataURL('image/jpeg', 0.9))
            }
            img.onerror = () => resolve(null)
            img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(source)))
          }),
        svg,
      )
      if (baked && (await attach(name, baked, `${name} 연습`))) attached += 1
    }
  }
  console.log(`  · 아이 사진 ${attached}명 분을 붙였습니다`)
  if (attached < 8) throw new Error(`사진이 ${attached}명 분밖에 안 붙었습니다 — 장면이 이름만 나옵니다.`)

  /** 앞 4초 흔들림 + 뒤 16초 본 화면을 흉내 낸 검사용 동영상 — 「자르는 칸」을 보여 주려면 필요하다 */
  const ffmpeg = spawnSync('which', ['ffmpeg'], { encoding: 'utf8' }).stdout.trim()
  // 파일 이름은 **버퍼로 따로 붙인다**(아래) — 여기서는 ASCII 로 둔다.
  // 한글 이름 파일을 그대로 올리면 이 환경에서 브라우저가 조용히 안 받는다(직접 확인).
  const clip = join(TMP, 'clip-src.webm')
  if (ffmpeg) {
    spawnSync(
      ffmpeg,
      [
        '-y', '-v', 'error',
        '-f', 'lavfi', '-i', 'color=c=0x6B5B4A:s=640x360:d=4',
        '-f', 'lavfi', '-i', 'color=c=0xC9A227:s=640x360:d=16',
        '-filter_complex', '[0:v][1:v]concat=n=2:v=1[v]', '-map', '[v]',
        '-c:v', 'libvpx', '-b:v', '400k', '-r', '15', clip,
      ],
      { encoding: 'utf8' },
    )
  }

  /**
   * 연습실 일상 사진 — 「이 무대까지 오는 동안」 묶음이 된다.
   *
   * 감동영상은 무대 사진만 이어 붙인 것이 아니다. 연습하던 날들이 앞에 깔려야
   * 「이만큼 고생했구나」가 전해진다. 그 장면이 실제로 만들어지는 것을 보여 준다.
   */
  const galleryFiles = existsSync(KIDS_EXTRA)
    ? readdirSync(KIDS_EXTRA).filter((f) => /\.(jpe?g|png)$/i.test(f)).sort()
    : []

  await page.goto(`${BASE}/events/${EVENT_ID}/video`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1800)

  // 처음 켤 때 뜨는 쪽지가 화면 오른쪽 아래를 가린다 — 찍기 전에 닫는다
  const tip = page.getByTestId('first-run-close')
  if (await tip.count()) {
    await tip.click()
    await page.waitForTimeout(400)
  }

  /*
   * 영상 템플릿을 **「꽉 찬 사진」으로 못박는다.**
   *
   * 감동영상은 아이 얼굴이 화면을 가득 채워야 하는 영상이다. 액자·반쪽 템플릿은
   * 사진을 작게 담으므로 「이렇게 나옵니다」를 보여 주는 자리에 맞지 않는다.
   * 기본값이 이미 그것이지만, 저장된 설정이 남아 있으면 다른 것이 열린다.
   */
  const picker = page.getByTestId('video-templates')
  if (await picker.getByTestId('video-template-toggle').count()) {
    await picker.getByTestId('video-template-toggle').click()
    await page.waitForTimeout(400)
    const full = picker.locator('button', { hasText: '꽉 찬 사진' }).first()
    if (await full.count()) {
      await full.click()
      await page.waitForTimeout(600)
    }
    await picker.getByTestId('video-template-toggle').click()
    await page.waitForTimeout(400)
  }

  if (galleryFiles.length > 0) {
    await page.locator('input[type="file"][accept="image/*"]').first().setInputFiles(
      galleryFiles.map((f) => ({
        name: f,
        mimeType: f.toLowerCase().endsWith('.png') ? 'image/png' : 'image/jpeg',
        buffer: readFileSync(join(KIDS_EXTRA, f)),
      })),
    )
    await page.waitForTimeout(2000)
    console.log(`  · 연습 사진 ${galleryFiles.length}장을 얹었습니다`)
  }

  const canvas = page.locator('canvas').first()
  const shoot = async (locator, file, quality = 72) => {
    await locator.screenshot({ path: join(OUT, file), type: 'jpeg', quality })
    console.log(`  ✓ ${file}  ${kb(file)}KB`)
  }

  /**
   * 아래쪽 칸을 찍을 때는 **미리보기 화면을 따라다니지 않게** 한다.
   *
   * 미리보기는 sticky 라 화면 위에 붙어 다닌다. 쓸 때는 그게 맞지만, 칸 하나를 찍으면
   * 그 위를 덮어 **찍힌 그림의 윗부분이 미리보기로 가려진다**(한 번 그렇게 찍혔다).
   * 붙어 다니는 것만 잠깐 풀어 둔다 — 칸의 내용은 그대로다.
   */
  const unstick = () => page.addStyleTag({ content: '.sticky{position:static!important}' })

  /* ① 화면 전체 — 「이 한 화면에서 다 됩니다」 */
  await page.screenshot({ path: join(OUT, 'vs-screen.jpg'), type: 'jpeg', quality: 70 })
  console.log(`  ✓ vs-screen.jpg  ${kb('vs-screen.jpg')}KB`)

  /* ② 미리보기 화면 — 실제로 뽑히는 그 그림 */
  const board = page.getByTestId('storyboard')
  const sceneButtons = board.locator('button[aria-label$="장면 고치기"]')
  const total = await sceneButtons.count()
  console.log(`  · 장면 ${total}개`)

  /**
   * 장면 하나를 골라 **자막이 다 떠오른 뒤** 화면을 찍는다.
   *
   * 장면 첫 순간은 자막이 아직 안 올라와 글자가 없다 — 그 그림으로는
   * 「이름과 곡이 이렇게 나옵니다」를 보여 줄 수 없다. 그래서 잠깐 틀었다 멈춘다.
   */
  const frameAt = async (index, file) => {
    await sceneButtons.nth(index).click()
    await page.waitForTimeout(400)
    await page.getByRole('button', { name: '미리보기' }).click()
    await page.waitForTimeout(1500)
    await canvas.screenshot({ path: join(OUT, file), type: 'jpeg', quality: 78 })
    await page.getByRole('button', { name: '멈추기' }).click().catch(() => undefined)
    await page.waitForTimeout(400)
    console.log(`  ✓ ${file}  ${kb(file)}KB`)
  }

  const labels = await sceneButtons.evaluateAll((nodes) => nodes.map((n) => n.getAttribute('aria-label') ?? ''))
  const find = (test, from = 0) => {
    for (let i = from; i < labels.length; i += 1) if (test(labels[i])) return i
    return -1
  }
  const titleAt = 0
  const kidAt = find((l) => /번째 무대/.test(l))
  const cheerAt = find((l) => l.startsWith('응원'))
  const endAt = find((l) => l.startsWith('마무리'))

  await frameAt(titleAt, 'vf-title.jpg')
  if (kidAt >= 0) await frameAt(kidAt, 'vf-kid.jpg')
  if (kidAt >= 0 && labels[kidAt + 2]) await frameAt(kidAt + 2, 'vf-kid2.jpg')
  const galleryAt = find((l) => l.startsWith('연습 사진'))
  if (galleryAt >= 0) await frameAt(galleryAt, 'vf-gallery.jpg')
  if (cheerAt >= 0) await frameAt(cheerAt, 'vf-cheer.jpg')
  if (endAt >= 0) await frameAt(endAt, 'vf-end.jpg')

  /* ③ 콘티 — 만들기 전에 전체가 그림으로 보인다 */
  await unstick()
  await page.waitForTimeout(300)
  await shoot(board, 'vs-board.jpg', 68)

  /* ④ 시간 띠 — 끌어서 옮기고 늘린다 */
  const strip = page.getByTestId('scene-timeline')
  await strip.locator('summary').click()
  await page.waitForTimeout(600)
  await unstick()
  await page.waitForTimeout(300)
  await shoot(strip, 'vs-timeline.jpg', 74)

  /* ⑤ 장면 고치기 — 전환·자막·작은 그림 */
  if (kidAt >= 0) {
    await sceneButtons.nth(kidAt).click()
    await page.waitForTimeout(500)
    await unstick()
    await page.waitForTimeout(300)
    await shoot(page.getByTestId('scene-editor'), 'vs-scene.jpg', 74)
  }

  /* ⑥ 동영상 자르기 — 휴대폰 영상 앞머리를 잘라 낸다 */
  if (!ffmpeg || !existsSync(clip)) {
    console.log('  · ffmpeg 이 없어 「자르는 칸」은 건너뜁니다')
  } else {
    // 이름은 화면에 그대로 나오므로 한글로 붙여 준다 — 원장님이 올리시는 파일과 같은 모양
    await page.locator('input[type="file"][accept="video/*"]').first().setInputFiles({
      name: '리허설 영상.webm',
      mimeType: 'video/webm',
      buffer: readFileSync(clip),
    })
    // 동영상은 길이를 재야 「쓸 자리」 칸이 열린다 — 사진보다 오래 걸린다
    const clipButton = board.locator('button[aria-label^="동영상"][aria-label$="장면 고치기"]').first()
    await clipButton.waitFor({ timeout: 20_000 })
    await clipButton.click()
    await page.waitForTimeout(900)
    const editor = page.getByTestId('scene-editor')
    const slider = editor.getByTestId('clip-start')
    // 조용히 건너뛰면 「자르는 칸」이 빠진 채로 상세페이지가 나간다 — 크게 실패시킨다
    await slider.waitFor({ timeout: 15_000 })
    await slider.fill('5')
    await page.waitForTimeout(500)
    await unstick()
    await page.waitForTimeout(300)
    await shoot(editor, 'vs-trim.jpg', 74)
  }

  await context.close()
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
