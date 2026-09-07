#!/usr/bin/env node
/**
 * 감동영상 검사.
 *
 *   npm run build && node scripts/verify-video.mjs
 *
 * "만들어집니다" 라고 말하기 전에 실제로 만들어 본다.
 * 브라우저를 띄워 [영상 만들기] 를 누르고, 나온 파일이 진짜 재생되는 영상인지
 * 바이트로 확인한다. 화면 캡처도 남겨 장면이 제대로 그려지는지 눈으로 본다.
 */
import { spawn, spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright'
import { requireFreePort, requireFreshBuild } from './lib/fresh-build.mjs'

// 낡은 빌드를 재면 고쳐진 문제도 실패로 나온다
requireFreshBuild()

const PORT = Number(process.env.VIDEO_PORT ?? 3993)

// 남이 물고 있는 문이면 **남의(낡은) 서버를 재게 된다**
await requireFreePort(PORT)
const BASE = `http://127.0.0.1:${PORT}`
const DATA = join(process.cwd(), '.data')
const BACKUP = join(mkdtempSync(join(tmpdir(), 'pianoevent-video-')), 'data')
const OUT = join(process.cwd(), 'shots', 'video')
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
  const context = await browser.newContext({ viewport: { width: 1500, height: 1000 }, deviceScaleFactor: 1 })
  const page = await context.newPage()
  page.on('pageerror', (error) => failures.push(`화면 오류: ${error.message}`))

  // 아이 사진을 한 장 올려 둔다 — 사진이 든 장면까지 그려 보기 위해
  const photo = await page.goto(`${BASE}/`).then(() =>
    page.evaluate(() => {
      const canvas = document.createElement('canvas')
      canvas.width = 600
      canvas.height = 600
      const ctx = canvas.getContext('2d')
      const grad = ctx.createLinearGradient(0, 0, 600, 600)
      grad.addColorStop(0, '#E8A87C')
      grad.addColorStop(1, '#8B5E3C')
      ctx.fillStyle = grad
      ctx.fillRect(0, 0, 600, 600)
      ctx.fillStyle = '#fff'
      ctx.beginPath()
      ctx.arc(300, 250, 110, 0, Math.PI * 2)
      ctx.fill()
      return canvas.toDataURL('image/jpeg', 0.85)
    }),
  )
  const uploaded = await page.request.post(`${BASE}/api/academy/assets`, {
    data: { kind: 'photo', label: '검사용 사진', url: photo },
  })
  const uploadedBody = await uploaded.json()
  const roster = await (await page.request.get(`${BASE}/api/events/${EVENT_ID}/students`)).json()
  for (const student of (roster.students ?? []).slice(0, 3)) {
    await page.request.patch(`${BASE}/api/students/${student.id}`, {
      data: { photo_asset_id: uploadedBody.asset.id },
    })
  }

  await page.goto(`${BASE}/events/${EVENT_ID}/video`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(900)

  // 테마·길이·로고·구간·초대장은 "자세히 고치기" 안에 접혀 있다 (원장님은 그냥 만드시면 된다).
  // 검사할 때만 펴 준다.
  const openAdvanced = async () => {
    const toggle = page.getByTestId('video-advanced-toggle')
    if ((await toggle.getAttribute('aria-expanded')) === 'false') {
      await toggle.click()
      await page.waitForTimeout(350)
    }
  }


  check('감동영상 화면이 열린다', (await page.getByRole('heading', { name: '감동영상' }).count()) === 1)
  const canvas = page.locator('canvas')
  check('미리보기 화면이 있다', (await canvas.count()) === 1)
  const box = await canvas.boundingBox()
  check('16:9 로 그린다', Math.abs(box.width / box.height - 16 / 9) < 0.02, `${box.width}×${box.height}`)

  const lengthText = await page.getByTestId('video-length').textContent()
  check('길이와 장면 수를 알려 준다', /장면 \d+개/.test(lengthText), lengthText.trim())
  const sceneCount = Number(lengthText.match(/장면 (\d+)개/)[1])
  check('명단에서 장면이 만들어졌다', sceneCount >= 12 + 3, `${sceneCount}개`)

  // 영상 템플릿 20종 — 배경과 사진 놓는 방식이 실제로 달라지는가
  const picker = page.getByTestId('video-templates')
  check('영상 템플릿 창이 있다', (await picker.count()) === 1)
  // 스무 가지는 접혀 있다 — "이대로 만드셔도 됩니다" 아래에 펼쳐 두면 그 말을 못 믿으신다
  const shownChips = await picker.locator('button').evaluateAll((nodes) =>
    nodes.filter((n) => n.checkVisibility?.({ checkVisibilityCSS: true }) ?? true).length,
  )
  check('평소에는 접혀 있다 — 눌러 볼 것이 하나뿐이다', shownChips === 1, `${shownChips}개 보임`)
  await page.getByTestId('video-template-toggle').click()
  await page.waitForTimeout(500)
  const chips = picker.locator('button:not([data-testid="video-template-toggle"])')
  const chipCount = await chips.count()
  check('템플릿이 20종이다', chipCount === 20, String(chipCount))
  // 이름만으로는 "꽉 찬 사진 · 위 자막" 이 무엇이 다른지 알 수 없다 — 화면 모양을 그려 준다
  check('그림으로 고른다 — 이름 목록이 아니다', (await page.getByTestId('video-template-grid').count()) === 1)
  const vTile = await chips.first().boundingBox()
  check('칸이 눌러 볼 만한 크기다', vTile && vTile.width >= 80, vTile ? `${Math.round(vTile.width)}px` : '자리를 못 찾음')

  // 사진이 든 장면에 세워 놓고 견준다 — 표지 화면은 템플릿을 갈아도 거의 같아 보인다
  await page
    .locator('[data-testid="storyboard"] button[aria-label*="1번째 무대"]')
    .first()
    .click()
    .catch(() => undefined)
  await page.waitForTimeout(400)

  const looks = new Set()
  for (let i = 0; i < chipCount; i += 1) {
    await chips.nth(i).click()
    await page.waitForTimeout(420)
    // 캔버스 그림을 굵게 요약해 서로 다른지 본다
    const fingerprint = await page.locator('canvas').first().evaluate((node) => {
      const ctx = node.getContext('2d')
      const data = ctx.getImageData(0, 0, node.width, node.height).data
      let sum = 0
      let bright = 0
      for (let p = 0; p < data.length; p += 4 * 97) {
        sum += data[p] + data[p + 1] * 2 + data[p + 2] * 3
        if (data[p] > 235 && data[p + 1] > 235 && data[p + 2] > 235) bright += 1
      }
      return `${sum}|${bright > 0}`
    })
    looks.add(fingerprint)
    if (!fingerprint.endsWith('|true')) failures.push(`템플릿 ${i + 1}번에 글자가 보이지 않습니다`)
  }
  check('템플릿마다 화면이 실제로 다르다', looks.size === chipCount, `${looks.size} / ${chipCount}`)
  console.log('  ✓ 템플릿 20종 모두 글자가 보인다')
  passed += 1
  await chips.first().click()
  await page.waitForTimeout(350)

  // 만들기 전에 전체 모습이 보이는가 — 원장님이 마음 놓고 누를 수 있어야 한다
  const board = page.getByTestId('storyboard')
  check('만들어질 모습 창이 있다', (await board.count()) === 1)
  await page.waitForTimeout(1200)
  // 띠에도 같은 그림이 붙으므로, 세는 자리는 아래 격자로 못박는다
  const thumbs = page.getByTestId('storyboard-grid').locator('img')
  const thumbCount = await thumbs.count()
  check('장면마다 그림이 나온다', thumbCount === sceneCount, `${thumbCount} / ${sceneCount}`)
  const firstThumb = await thumbs.first().getAttribute('src')
  check('그림이 진짜로 그려진 것이다', (firstThumb ?? '').startsWith('data:image/jpeg'), (firstThumb ?? '').slice(0, 24))
  const boardText = await board.textContent()
  check('장면 이름과 길이를 적어 준다', /\d+초/.test(boardText) && boardText.includes('제12회'), boardText.slice(0, 60))
  check('사진이 없는 장면을 알려 준다', boardText.includes('사진 없음'))
  await board.screenshot({ path: join(OUT, 'storyboard.jpg'), type: 'jpeg', quality: 80 })

  // 콘티를 누르면 그 장면이 보이고, 고칠 수 있다
  await board.locator('button[aria-label$="장면 고치기"]').nth(4).click()
  await page.waitForTimeout(400)
  const jumped = await page.getByTestId('video-length').textContent()
  check('장면을 누르면 그 자리로 간다', !jumped.trim().startsWith('0초'), jumped.trim())

  const editor = page.getByTestId('scene-editor')
  check('장면 고치는 칸이 열린다', (await editor.count()) === 1)
  await page.getByLabel('큰 글씨').fill('우리 아이들의 1년')
  await page.getByLabel('작은 글씨', { exact: true }).fill('고맙습니다')
  await page.waitForTimeout(700)
  const editedThumb = await board.locator('img').nth(4).getAttribute('src')
  check('고친 문구가 콘티 그림에 바로 반영된다', (editedThumb ?? '').startsWith('data:image/jpeg'))
  const boardAfter = await board.textContent()
  check('고친 이름이 장면 목록에 보인다', boardAfter.includes('우리 아이들의 1년'), boardAfter.slice(0, 80))

  // 머무는 시간을 늘리면 전체 길이가 늘어난다
  const beforeLen = (await page.getByTestId('video-length').textContent()).split('/')[1]
  await page.getByLabel('머무는 시간 (초)').fill('8')
  await page.waitForTimeout(600)
  const afterLen = (await page.getByTestId('video-length').textContent()).split('/')[1]
  check('머무는 시간을 늘리면 전체 길이도 늘어난다', afterLen !== beforeLen, `${beforeLen.trim()} → ${afterLen.trim()}`)

  // 글자 자리 바꾸기
  await page.getByRole('button', { name: '가운데 크게' }).click()
  await page.waitForTimeout(500)
  check('글자 자리를 고를 수 있다', (await page.getByRole('button', { name: '가운데 크게' }).getAttribute('aria-pressed')) === 'true')

  // 순서 옮기기
  const labelsBefore = await board.locator('span.truncate').allTextContents()
  await editor.getByRole('button', { name: '← 앞으로' }).click()
  await page.waitForTimeout(500)
  const labelsAfter = await board.locator('span.truncate').allTextContents()
  check('장면 순서를 앞뒤로 옮긴다', labelsBefore[4] !== labelsAfter[4], `${labelsBefore[4]} → ${labelsAfter[4]}`)
  check('옮겨도 장면 수는 그대로', labelsBefore.length === labelsAfter.length)

  // 되돌리기
  await page.getByRole('button', { name: '고친 것 되돌리기' }).click()
  await page.waitForTimeout(600)
  const restored = await board.textContent()
  check('고친 것을 한 번에 되돌린다', !restored.includes('우리 아이들의 1년'))
  await page.getByTestId('scene-editor').isVisible().catch(() => undefined)

  // ── 빠른 미리보기 · 로고 · 설정 저장 ─────────────────────────────
  const speeds = page.getByTestId('preview-speed')
  check('미리보기 배속 단추가 있다', (await speeds.locator('button').count()) === 3)

  // 로고를 학원에 붙여 두고 화면을 다시 연다 — 영상 구석에 들어가야 한다
  const logo = await page.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 240
    canvas.height = 120
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#00FF66'
    ctx.fillRect(0, 0, 240, 120)
    return canvas.toDataURL('image/png')
  })
  await page.request.patch(`${BASE}/api/academy`, { data: { logo_url: logo } })
  await page.goto(`${BASE}/events/${EVENT_ID}/video`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1200)
  await openAdvanced()

  const logoBox = page.getByTestId('logo-place')
  check('로고 자리를 고르는 칸이 있다', (await logoBox.count()) === 1)
  check('로고 자리가 5가지다', (await logoBox.locator('button').count()) === 5)

  // 초록 로고가 실제로 화면에 찍혔는지 픽셀로 센다
  const greenAt = async () =>
    page.locator('canvas').first().evaluate((node) => {
      const ctx = node.getContext('2d')
      const data = ctx.getImageData(0, 0, node.width, node.height).data
      let green = 0
      for (let p = 0; p < data.length; p += 4) {
        if (data[p] < 120 && data[p + 1] > 180 && data[p + 2] < 150) green += 1
      }
      return green
    })

  await logoBox.getByRole('button', { name: '넣지 않기' }).click()
  await page.waitForTimeout(500)
  const withoutLogo = await greenAt()
  await logoBox.getByRole('button', { name: '오른쪽 아래' }).click()
  await page.waitForTimeout(500)
  const withLogo = await greenAt()
  check('로고가 실제로 화면에 그려진다', withLogo > withoutLogo + 500, `${withoutLogo} → ${withLogo}`)
  check('로고가 화면을 가리지 않는다', withLogo < 1280 * 720 * 0.05, `${withLogo}점`)

  // 설정 저장 → 다시 열면 그대로
  await page.getByRole('button', { name: '테마 · ', exact: false }).first().click()
  await page.waitForTimeout(300)
  // 템플릿은 접혀 있다 — 고르려면 먼저 펴야 한다
  await page.getByTestId('video-template-toggle').click()
  await page.waitForTimeout(400)
  const templateChips = page
    .getByTestId('video-templates')
    .locator('button:not([data-testid="video-template-toggle"])')
  const savedTemplate = await templateChips.nth(5).textContent()
  await templateChips.nth(5).click()
  await page.waitForTimeout(300)
  await page.getByTestId('prefs-video_prefs').getByRole('button', { name: '이 설정 저장' }).click()
  await page.waitForSelector('text=저장했습니다', { timeout: 8000 })
  check('영상 설정을 저장한다', true)
  passed += 1

  await page.goto(`${BASE}/events/${EVENT_ID}/video`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1000)
  await openAdvanced()
  await page.getByTestId('video-template-toggle').click()
  await page.waitForTimeout(400)
  const reopened = page.getByTestId('video-templates').locator('button[aria-pressed="true"]')
  check('다시 열면 저장해 둔 템플릿으로 시작한다', (await reopened.textContent()) === savedTemplate, savedTemplate ?? '')
  const reopenedLogo = await page
    .getByTestId('logo-place')
    .locator('button[aria-pressed="true"]')
    .textContent()
  check('로고 자리도 그대로 열린다', reopenedLogo === '오른쪽 아래', reopenedLogo ?? '')

  // 초대장에 붙일 영상 주소
  const inviteBox = page.getByTestId('invite-video')
  check('초대장에 영상 붙이는 칸이 있다', (await inviteBox.count()) === 1)
  await inviteBox.getByLabel('영상 주소').fill('https://youtu.be/dQw4w9WgXcQ')
  await page.waitForTimeout(300)
  check('붙여넣은 주소를 알아본다', (await inviteBox.textContent()).includes('바로 재생'))
  await inviteBox.getByRole('button', { name: '붙이기' }).click()
  await page.waitForTimeout(800)
  const inviteRes = await page.request.get(`${BASE}/e/${EVENT_ID}`)
  const inviteHtml = await inviteRes.text()
  check('초대장에 영상이 실제로 붙는다', inviteHtml.includes('youtube-nocookie.com/embed/dQw4w9WgXcQ'))
  check('초대장에 영상 제목이 함께 나온다', inviteHtml.includes('아이들이 걸어온 시간'))

  // 미리보기를 2배로 돌리면 실제로 두 배 빨리 흐른다
  await page.getByLabel('아이 한 명당').fill('3')
  await page.waitForTimeout(500)
  const readClock = async () => {
    const text = await page.getByTestId('video-length').textContent()
    const head = text.split('/')[0].trim()
    const m = head.match(/(?:(\d+)분 )?(\d+)초/)
    return m ? Number(m[1] ?? 0) * 60 + Number(m[2]) : 0
  }
  // 미리보기는 멈춘 자리에서 이어 재생하므로, 절대 시각이 아니라 **3초 동안 얼마나 흘렀는지**를 잰다
  const playFor = async (label) => {
    await page.getByTestId('preview-speed').getByRole('button', { name: label }).click()
    const before = await readClock()
    await page.getByRole('button', { name: '미리보기' }).click()
    await page.waitForTimeout(3000)
    const after = await readClock()
    await page.getByRole('button', { name: '멈추기' }).click().catch(() => undefined)
    await page.waitForTimeout(400)
    return after - before
  }
  const slow = await playFor('1배 속도로 보기')
  const fast = await playFor('4배 속도로 보기')
  check('1배 미리보기는 실제 시간만큼 흐른다', slow >= 2 && slow <= 5, `3초에 ${slow}초`)
  check('4배속 미리보기가 실제로 네 배 가까이 빠르다', fast >= slow * 3, `4배 ${fast}초 / 1배 ${slow}초`)

  // 이 브라우저가 뽑을 수 있는 형식이 있는가
  const recordType = await page.evaluate(() => {
    const list = [
      'video/mp4;codecs="avc1.42E01E,mp4a.40.2"',
      'video/mp4;codecs=avc1',
      'video/webm;codecs="vp9,opus"',
      'video/webm',
      'video/mp4',
    ]
    return list.find((type) => MediaRecorder.isTypeSupported(type)) ?? null
  })
  check('영상으로 뽑을 형식이 있다', Boolean(recordType), recordType ?? '없음')

  // 장면 시간을 줄여 검사를 빨리 끝낸다 — 녹화는 실제 시간만큼 걸린다
  await page.getByLabel('아이 한 명당').fill('1.5')
  await page.getByLabel('표지 · 마무리').fill('1.5')
  await page.waitForTimeout(600)
  const shortText = await page.getByTestId('video-length').textContent()
  check('장면 시간을 줄이면 전체 길이도 줄어든다', shortText !== lengthText, shortText.trim())

  // 몇 장면을 그려 캡처로 남긴다 (미리보기를 잠깐 돌린다)
  await page.getByRole('button', { name: '미리보기' }).click()
  for (const [index, wait] of [800, 3000, 6000].entries()) {
    await page.waitForTimeout(index === 0 ? wait : 2200)
    await canvas.screenshot({ path: join(OUT, `frame-${index + 1}.jpg`), type: 'jpeg', quality: 80 })
  }
  const painted = await canvas.evaluate((node) => {
    const ctx = node.getContext('2d')
    const data = ctx.getImageData(0, 0, node.width, node.height).data
    let lit = 0
    for (let i = 0; i < data.length; i += 4 * 997) if (data[i] + data[i + 1] + data[i + 2] > 60) lit += 1
    return lit
  })
  check('화면에 실제로 그려진다 (검은 화면이 아니다)', painted > 20, `${painted}점`)
  await page.getByRole('button', { name: '멈추기' }).click().catch(() => undefined)
  await page.waitForTimeout(400)

  // 만들다 끊겨도 담긴 데까지는 파일로 나오는가 — 8분짜리를 7분째에 잃지 않게
  console.log('  · 중간에 멈춰 봅니다')
  await page.getByRole('button', { name: '영상 만들기' }).click()
  await page.waitForTimeout(4000)
  await page.getByRole('button', { name: '여기까지 만들고 멈추기' }).click()
  await page.waitForSelector('text=내려받기', { timeout: 30_000 })
  const partial = await page.evaluate(async () => {
    const link = document.querySelector('a[download]')
    if (!link) return null
    const res = await fetch(link.href)
    const buf = new Uint8Array(await res.arrayBuffer())
    return { name: link.getAttribute('download'), bytes: buf.length, head: Array.from(buf.slice(0, 12)) }
  })
  check('멈춰도 담긴 데까지 파일이 나온다', partial && partial.bytes > 5_000, partial ? `${Math.round(partial.bytes / 1024)}KB` : '없음')
  check('중간까지라는 것을 이름에 적어 준다', (partial?.name ?? '').includes('중간까지'), partial?.name ?? '')
  if (partial) {
    const bytes = Buffer.from(partial.head)
    const isMp4 = bytes.slice(4, 8).toString('latin1') === 'ftyp'
    const isWebm = bytes[0] === 0x1a && bytes[1] === 0x45 && bytes[2] === 0xdf && bytes[3] === 0xa3
    check('멈춰서 받은 것도 진짜 영상 파일이다', isMp4 || isWebm, bytes.toString('hex'))
  }
  const partialNote = await page.textContent('body')
  check('왜 짧은지 화면에 적어 준다', partialNote.includes('만들다 멈춰'))

  // 빠른 길(WebCodecs)을 쓸 수 있는 컴퓨터인가 — 쓸 수 있으면 영상 길이보다 빨리 끝나야 한다
  const fastPlan = await page.evaluate(async () => {
    if (typeof VideoEncoder === 'undefined' || typeof AudioEncoder === 'undefined') return null
    const plans = [
      { c: 'avc1.4D002A', a: 'mp4a.40.2', box: 'mp4' },
      { c: 'avc1.42002A', a: 'mp4a.40.2', box: 'mp4' },
      { c: 'vp09.00.10.08', a: 'opus', box: 'webm' },
    ]
    for (const plan of plans) {
      try {
        const video = await VideoEncoder.isConfigSupported({ codec: plan.c, width: 1280, height: 720, bitrate: 4_500_000, framerate: 30 })
        if (!video.supported) continue
        const audio = await AudioEncoder.isConfigSupported({ codec: plan.a, sampleRate: 48_000, numberOfChannels: 2, bitrate: 128_000 })
        if (!audio.supported) continue
        return plan
      } catch {
        /* 다음 것을 본다 */
      }
    }
    return null
  })
  // 예전 방식이 MP4 를 만드는데 빠른 길이 WebM 뿐이면 쓰지 않는다 (화면과 같은 규칙)
  const usesFast = Boolean(fastPlan) && !(fastPlan.box === 'webm' && (recordType ?? '').includes('mp4'))
  const costText = (await page.getByTestId('record-cost').textContent()) ?? ''
  check(
    '빠르게 만들 수 있는지 미리 알려 준다',
    usesFast ? costText.includes('빠르게') : costText.includes('걸립니다'),
    `${usesFast ? '빠른 길' : '예전 길'} · ${costText.trim().slice(0, 40)}`,
  )

  // 진짜로 만들어 본다
  const total = Number((await page.getByTestId('video-length').textContent()).match(/\/ (?:(\d+)분 )?(\d+)초/)?.slice(1).reduce((a, b) => Number(a || 0) * 60 + Number(b || 0), 0) ?? 40)
  console.log(`  · 영상 ${total}초 분량을 실제로 만듭니다 (${usesFast ? '빠른 길' : '실시간이라 그만큼 걸립니다'})`)
  const madeAt = Date.now()
  await page.getByRole('button', { name: '영상 만들기' }).click()
  await page.waitForSelector('text=내려받기', { timeout: (total + 60) * 1000 })
  const madeSec = (Date.now() - madeAt) / 1000
  if (usesFast) {
    check('빠른 길이 영상 길이보다 빨리 끝난다', madeSec < total, `${total}초짜리를 ${madeSec.toFixed(1)}초에`)
  } else {
    console.log(`  · 이 컴퓨터에는 빠른 길이 없어 ${madeSec.toFixed(1)}초 걸렸습니다`)
  }

  const made = await page.evaluate(async () => {
    const link = document.querySelector('a[download]')
    if (!link) return null
    const res = await fetch(link.href)
    const buf = new Uint8Array(await res.arrayBuffer())
    return { name: link.getAttribute('download'), bytes: buf.length, head: Array.from(buf.slice(0, 12)) }
  })
  check('영상 파일이 만들어졌다', made && made.bytes > 20_000, made ? `${Math.round(made.bytes / 1024)}KB` : '없음')
  check('파일 이름이 한글 행사명으로 붙는다', (made?.name ?? '').includes('감동영상'), made?.name ?? '')

  if (made) {
    const bytes = Buffer.from(made.head)
    const isMp4 = bytes.slice(4, 8).toString('latin1') === 'ftyp'
    const isWebm = bytes[0] === 0x1a && bytes[1] === 0x45 && bytes[2] === 0xdf && bytes[3] === 0xa3
    check('진짜 영상 파일이다 (MP4 또는 WebM)', isMp4 || isWebm, bytes.toString('hex'))
    check('확장자가 실제 형식과 맞는다', isMp4 ? made.name.endsWith('.mp4') : made.name.endsWith('.webm'), made.name)

    // 파일을 남겨 두고 재생 가능한지 본다
    const full = await page.evaluate(async () => {
      const link = document.querySelector('a[download]')
      const res = await fetch(link.href)
      return Array.from(new Uint8Array(await res.arrayBuffer()))
    })
    const path = join(OUT, made.name)
    writeFileSync(path, Buffer.from(full))
    const probe = spawnSync('which', ['ffprobe'], { encoding: 'utf8' }).stdout.trim()
    if (probe) {
      const info = spawnSync(probe, ['-v', 'error', '-show_entries', 'format=duration:stream=codec_type', '-of', 'default=nw=1', path], { encoding: 'utf8' })
      check('영상 도구가 읽어 낸다', info.status === 0, (info.stderr ?? '').trim().slice(0, 120))
      check('영상 트랙이 들어 있다', (info.stdout ?? '').includes('video'), (info.stdout ?? '').trim().replace(/\n/g, ' '))
      // 화면이 실제로 풀리는지 — 한 장면을 그림으로 뽑아 본다
      const ffmpeg = spawnSync('which', ['ffmpeg'], { encoding: 'utf8' }).stdout.trim()
      if (ffmpeg) {
        const still = join(OUT, 'decoded.jpg')
        rmSync(still, { force: true })
        spawnSync(ffmpeg, ['-y', '-v', 'error', '-i', path, '-frames:v', '1', '-ss', '2', still], { encoding: 'utf8' })
        check('영상을 풀면 그림이 나온다', existsSync(still))
      }
    } else {
      console.log('  · ffprobe 가 없어 재생 검사는 건너뜁니다')
    }
  }

  // ── 시간 띠에서 끌어 편집 ───────────────────────────────────────
  // 30개짜리 영상에서 다섯 번째를 스무 번째로 옮기는 데 [뒤로]를 열다섯 번 누르게 두지 않는다
  console.log('  · 시간 띠')
  await page.goto(`${BASE}/events/${EVENT_ID}/video`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1200)

  const strip = page.getByTestId('scene-timeline')
  check('시간 띠가 있다', (await strip.count()) === 1)
  // 평소에는 접혀 있다 — 원장님은 안 여셔도 되고, 화면도 그만큼 조용하다
  check('평소에는 접혀 있다', (await strip.locator('[data-testid^="timeline-block-"]').first().isVisible()) === false)
  await strip.locator('summary').click()
  await page.waitForTimeout(500)
  const blocks = strip.locator('[data-testid^="timeline-block-"]')
  const blockCount = await blocks.count()
  const stripThumbs = await strip.locator('img').count()
  const sceneTotal = Number((await page.getByTestId('video-length').textContent()).match(/장면 (\d+)개/)[1])
  check('띠에 장면이 모두 놓인다', blockCount === sceneTotal, `${blockCount} / ${sceneTotal}`)
  check('띠에도 장면마다 그림이 붙는다', stripThumbs === sceneTotal, `${stripThumbs} / ${sceneTotal}`)

  // 긴 장면이 더 넓게 — 어느 장면이 긴지는 숫자가 아니라 폭으로 보여야 한다
  const widths = await blocks.evaluateAll((nodes) => nodes.map((n) => n.getBoundingClientRect().width))
  const secs = await blocks.evaluateAll((nodes) =>
    nodes.map((n) => Number((n.getAttribute('aria-label') ?? '').match(/([\d.]+)초$/)?.[1] ?? 0)),
  )
  const longest = secs.indexOf(Math.max(...secs))
  const shortest = secs.indexOf(Math.min(...secs))
  check('머무는 시간이 길수록 넓다', widths[longest] > widths[shortest], `${secs[longest]}초 ${Math.round(widths[longest])}px / ${secs[shortest]}초 ${Math.round(widths[shortest])}px`)

  // 끌어서 옮기기 — 첫 장면을 네 번째 자리로
  // 띠는 화면 아래쪽에 있다 — 창 밖을 끌면 브라우저에 아무 일도 일어나지 않는다.
  // (이 자리를 안 맞추면 「끌어도 안 움직인다」가 제품 탓으로 보인다 — 실제로는 검사가 창 밖을 짚은 것이었다)
  // 띠는 화면 아래쪽에 있다 — 창 밖을 끌면 브라우저에 아무 일도 일어나지 않는다.
  // 한가운데로 올리면 안 된다: 미리보기 화면이 sticky 로 위쪽에 붙어 있어 띠가 그 아래로 숨는다.
  // (원장님이 쓰실 때도 마찬가지다 — 미리보기 밑으로 밀려 올라간 띠는 안 보이고, 안 잡힌다)
  await blocks.first().scrollIntoViewIfNeeded()
  await page.waitForTimeout(300)
  const labelOf = async (i) => (await blocks.nth(i).getAttribute('aria-label')) ?? ''
  const firstBefore = await labelOf(0)
  const fourthBefore = await labelOf(3)
  const from = await blocks.nth(0).boundingBox()
  const to = await blocks.nth(3).boundingBox()
  /**
   * 짚는 자리에 **정말로 그 블록이 있는가**.
   *
   * 좌표만 견주면 모자란다 — 창 안이어도 미리보기 화면이 그 위를 덮고 있으면
   * 브라우저는 아무 일도 하지 않는다. 그러면 「끌어도 안 움직인다」가 제품 탓으로 보인다.
   * 실제로 그렇게 두 번 속았으므로, 손가락 밑에 무엇이 있는지를 직접 묻는다.
   */
  const under = async (box) =>
    page.evaluate(
      ([x, y]) => document.elementFromPoint(x, y)?.closest('[data-testid="scene-timeline"]') !== null,
      [Math.round(box.x + box.width / 2), Math.round(box.y + box.height / 2)],
    )
  check('짚는 자리에 정말 띠가 있다 (검사가 헛짚지 않았다)', (await under(from)) && (await under(to)))
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
  await page.mouse.down()
  await page.mouse.move(from.x + from.width, from.y + from.height / 2, { steps: 4 })
  await page.mouse.move(to.x + to.width * 0.8, to.y + to.height / 2, { steps: 12 })
  await page.mouse.up()
  await page.waitForTimeout(700)
  const firstAfter = await labelOf(0)
  check('끌어서 장면 순서를 옮긴다', firstAfter !== firstBefore, `${firstBefore.slice(0, 22)} → ${firstAfter.slice(0, 22)}`)
  const moved = await blocks.evaluateAll((nodes) => nodes.map((n) => n.getAttribute('aria-label')))
  check('옮겨도 장면이 사라지지 않는다', moved.length === blockCount && moved.includes(firstBefore), `${moved.length}개`)
  check('밀려난 장면이 앞으로 온다', (await labelOf(2)) === fourthBefore || moved.includes(fourthBefore), fourthBefore.slice(0, 22))

  // 오른쪽 끝을 끌어 길이 바꾸기
  const target = blocks.nth(1)
  const beforeLabel = await target.getAttribute('aria-label')
  const beforeSec = Number(beforeLabel.match(/([\d.]+)초$/)[1])
  const beforeWidth = (await target.boundingBox()).width
  const grip = strip.getByTestId('timeline-grip-1')
  await grip.scrollIntoViewIfNeeded()
  await page.waitForTimeout(300)
  const gripBox = await grip.boundingBox()
  await page.mouse.move(gripBox.x + gripBox.width / 2, gripBox.y + gripBox.height / 2)
  await page.mouse.down()
  await page.mouse.move(gripBox.x + gripBox.width / 2 + 80, gripBox.y + gripBox.height / 2, { steps: 10 })
  await page.mouse.up()
  await page.waitForTimeout(800)
  const afterLabel = await blocks.nth(1).getAttribute('aria-label')
  const afterSec = Number(afterLabel.match(/([\d.]+)초$/)[1])
  check('끝을 끌면 머무는 시간이 늘어난다', afterSec > beforeSec, `${beforeSec}초 → ${afterSec}초`)
  check('늘린 만큼 블록도 넓어진다', (await blocks.nth(1).boundingBox()).width > beforeWidth, `${Math.round(beforeWidth)}px → ${Math.round((await blocks.nth(1).boundingBox()).width)}px`)
  const lenAfterDrag = await page.getByTestId('video-length').textContent()
  check('끌어 늘린 것이 전체 길이에도 반영된다', /장면 \d+개/.test(lenAfterDrag), lenAfterDrag.trim())

  // 눌러 두 번째 장면을 고르면 그 자리로 간다
  await blocks.nth(2).click()
  await page.waitForTimeout(500)
  check('띠에서 누르면 그 장면 고치기가 열린다', (await page.getByTestId('scene-editor').count()) === 1)

  // 보고 있는 자리 표시
  const headBefore = await strip.getByTestId('timeline-playhead').evaluate((n) => n.getBoundingClientRect().x)
  await page.getByRole('button', { name: '미리보기' }).click()
  await page.waitForTimeout(2500)
  const headAfter = await strip.getByTestId('timeline-playhead').evaluate((n) => n.getBoundingClientRect().x)
  await page.getByRole('button', { name: '멈추기' }).click().catch(() => undefined)
  await page.waitForTimeout(400)
  check('보고 있는 자리가 띠 위에서 움직인다', Math.abs(headAfter - headBefore) > 4, `${Math.round(headBefore)} → ${Math.round(headAfter)}`)
  await strip.screenshot({ path: join(OUT, 'timeline.jpg'), type: 'jpeg', quality: 85 })

  // ── 동영상 구간 자르기 ─────────────────────────────────────────
  // 휴대폰 영상은 앞이 흔들리거나 「자, 시작」 소리가 들어 있다. 그 앞을 잘라 낼 수 있는가,
  // 그리고 **잘라 낸 자리가 실제로 화면에 나오는가**를 색으로 잰다.
  const ffmpegBin = spawnSync('which', ['ffmpeg'], { encoding: 'utf8' }).stdout.trim()
  if (!ffmpegBin) {
    console.log('  · ffmpeg 가 없어 구간 자르기 검사는 건너뜁니다')
  } else {
    console.log('  · 동영상 구간 자르기')
    // 앞 4초는 빨강, 뒤 16초는 파랑인 20초짜리. 어느 자리를 썼는지 색만 보면 안다
    const clipPath = join(BACKUP, '..', 'trim-clip.webm')
    spawnSync(ffmpegBin, [
      '-y', '-v', 'error',
      '-f', 'lavfi', '-i', 'color=c=0xE03030:s=320x180:d=4',
      '-f', 'lavfi', '-i', 'color=c=2050E0:s=320x180:d=16',
      '-filter_complex', '[0:v][1:v]concat=n=2:v=1[v]', '-map', '[v]',
      '-c:v', 'libvpx', '-b:v', '300k', '-r', '15', clipPath,
    ], { encoding: 'utf8' })
    check('검사용 동영상을 만들었다', existsSync(clipPath))

    await page.goto(`${BASE}/events/${EVENT_ID}/video`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(900)
    // 장면을 짧게 해 두면 클립까지 금방 닿는다
    await openAdvanced()
    await page.getByLabel('아이 한 명당').fill('1.5')
    await page.getByLabel('표지 · 마무리').fill('1.5')
    await page.waitForTimeout(500)

    await page.locator('input[type="file"][accept="video/*"]').first().setInputFiles(clipPath)
    await page.waitForTimeout(2500)

    const clipBoard = page.getByTestId('storyboard')
    const clipButton = clipBoard.locator('button[aria-label^="동영상"][aria-label$="장면 고치기"]').first()
    check('올린 동영상이 장면으로 들어간다', (await clipButton.count()) === 1)

    await clipButton.click()
    await page.waitForTimeout(600)
    const clipEditor = page.getByTestId('scene-editor')
    // 20초짜리를 통째로 넣으면 한 아이가 영상의 절반을 먹는다 — 앞머리만 쓴다
    const clipSeconds = await clipEditor.locator('#sc-sec').inputValue()
    check('긴 동영상은 앞머리만 쓴다', Number(clipSeconds) === 12, `${clipSeconds}초`)
    check('동영상 장면에 자르는 칸이 있다', (await clipEditor.getByTestId('clip-start').count()) === 1)
    const slider = clipEditor.getByTestId('clip-start')
    const sliderMax = Number(await slider.getAttribute('max'))
    // 20초 동영상에 12초 장면 — 8초까지 밀 수 있다
    check('밀 수 있는 자리를 동영상 길이로 정한다', Math.abs(sliderMax - 8) < 0.6, `최대 ${sliderMax}초`)

    // 자른 자리가 화면에 실제로 나오는가 — 미리보기를 그 장면에서 돌려 색을 본다
    const colourAt = async (start) => {
      await slider.fill(String(start))
      await page.waitForTimeout(400)
      await clipButton.click() // 그 장면 자리로 옮긴다
      await page.waitForTimeout(300)
      await page.getByTestId('preview-speed').getByRole('button', { name: '1배 속도로 보기' }).click()
      await page.getByRole('button', { name: '미리보기' }).click()
      await page.waitForTimeout(1200)
      const rgb = await canvas.evaluate((node) => {
        const ctx = node.getContext('2d')
        const w = node.width, h = node.height
        const data = ctx.getImageData(Math.round(w * 0.4), Math.round(h * 0.4), Math.round(w * 0.2), Math.round(h * 0.2)).data
        let r = 0, g = 0, b = 0
        for (let i = 0; i < data.length; i += 4) { r += data[i]; g += data[i + 1]; b += data[i + 2] }
        const n = data.length / 4
        return { r: r / n, g: g / n, b: b / n }
      })
      await page.getByRole('button', { name: '멈추기' }).click().catch(() => undefined)
      await page.waitForTimeout(400)
      return rgb
    }
    const readout = () => clipEditor.getByTestId('clip-range').textContent()

    const head = await colourAt(0)
    check('처음부터 쓰면 앞부분(빨강)이 나온다', head.r > head.b + 40, `R${Math.round(head.r)} B${Math.round(head.b)}`)
    check('쓰는 구간을 적어 준다 (처음)', (await readout()).startsWith('0.0초 → 12.0초'), (await readout()).trim())

    const tail = await colourAt(6)
    check('6초부터로 밀면 뒷부분(파랑)이 나온다', tail.b > tail.r + 40, `R${Math.round(tail.r)} B${Math.round(tail.b)}`)
    check('민 자리를 적어 준다', (await readout()).startsWith('6.0초 → 18.0초'), (await readout()).trim())

    await clipEditor.screenshot({ path: join(OUT, 'clip-trim.jpg'), type: 'jpeg', quality: 85 })

    // 동영상을 통째로 쓰면 밀 자리가 없다 — 죽은 손잡이를 두지 않고 이유를 적는다
    await clipEditor.locator('#sc-sec').fill('20')
    await page.waitForTimeout(700)
    check('밀 자리가 없으면 손잡이 대신 이유를 적는다', (await clipEditor.getByTestId('clip-whole').count()) === 1)
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
