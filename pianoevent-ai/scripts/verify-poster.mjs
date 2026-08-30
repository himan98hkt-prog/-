// 그림 포스터의 글씨가 그림 위에서 실제로 읽히는가를 잰다.
//   node scripts/verify-poster.mjs          — 성격이 가장 다른 테마 4종 (평소)
//   node scripts/verify-poster.mjs --all    — 테마 108종 전수 (판매 직전에 한 번)
//
// 그림 23장 × 테마 108종이면 2484가지 조합이다. 눈으로는 못 본다.
// 그런데 하나라도 글씨가 묻히면 원장님은 그 한 장을 뽑아 벽에 붙이신다.
//
// 재는 방법 — 제목이 놓인 자리를 그대로 찍어서, 그 안의 **가장 흔한 밝기**(중앙값)를
// 바탕으로 보고 글씨 색과의 대비를 셈한다. 글씨는 자리의 일부만 덮으므로 중앙값은
// 바탕 쪽으로 쏠린다. 막·사진·선화가 뒤엉킨 실제 결과를 그대로 재는 셈이다.
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { chromium } from 'playwright'
import { killOnExit, requireFreePort, requireFreshBuild } from './lib/fresh-build.mjs'

const PORT = 3901

// 남이 물고 있는 문이면 **남의(낡은) 서버를 재게 된다**
await requireFreePort(PORT)
const BASE = `http://127.0.0.1:${PORT}`
const EVENT = 'demo-event'
/** 성격이 가장 다른 넷 — 어두운 갈라 · 밝은 미색 · 남색 격식 · 아이 */
const FOUR = ['gala-noir', 'gala-ivory', 'classic-navy', 'rainbow-play']
const MIN = 4.5

/**
 * 전수 검사.
 *
 * 그림 23장 × 테마 108종이면 2484가지다. 한 가지씩 새로 그려 재면 다섯 시간이 넘는다.
 * 그런데 **테마가 바꾸는 것은 색과 글꼴뿐**이다 — 그림도, 자리도, 글자 수도 그대로다.
 * 그래서 한 번 그려 놓고 색만 갈아 끼우며 잰다(10분대).
 *
 * 색만 갈아 끼운 것은 어림이다. 테마마다 다른 종이 장식(오선·금가루)까지는 못 따라간다.
 * 그래서 **문턱에 가까운 것은 전부 진짜로 다시 그려 확인한다.** 실패로 적히는 것은
 * 언제나 진짜로 그려 본 결과다.
 */
const ALL = process.argv.includes('--all') || process.env.POSTER_ALL === '1'
/** 어림으로 재서 이 밑이면 진짜로 다시 그려 본다 */
const SUSPECT = MIN + 0.75

/** 양식·테마 목록은 프로그램 자신에게 물어본다 (`/api/design/catalog`) */
let THEME_DATA = null
let THEMES = FOUR

const lum = ({ r, g, b }) => {
  const f = (c) => (c / 255 <= 0.03928 ? c / 255 / 12.92 : ((c / 255 + 0.055) / 1.055) ** 2.4)
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
}
const ratio = (a, b) => {
  const [x, y] = [a, b].sort((m, n) => n - m)
  return (x + 0.05) / (y + 0.05)
}

async function wait(ms = 90000) {
  const start = Date.now()
  while (Date.now() - start < ms) {
    try {
      if ((await fetch(`${BASE}/`, { redirect: 'manual' })).status < 500) return true
    } catch {
      /* 아직 안 떴다 */
    }
    await new Promise((r) => setTimeout(r, 400))
  }
  return false
}

requireFreshBuild()

const server = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '-p', String(PORT)], {
  stdio: 'ignore',
  detached: true,
  env: { ...process.env, NODE_ENV: 'production' },
})
killOnExit(server)
if (!(await wait())) {
  console.error('서버가 안 떴습니다')
  process.exit(1)
}

const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const browser = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})
const page = await (await browser.newContext({ viewport: { width: 900, height: 1300 } })).newPage()

/**
 * 무엇을 잴지는 프로그램에게 물어본다.
 *
 * 예전에는 이 파일 안에 포스터 목록을 베껴 두었다. 그러면 그림을 새로 넣을 때마다
 * 한쪽만 늘어나 **새 포스터가 검사에서 조용히 빠진다.** 목록은 한 군데만 있어야 한다.
 */
const catalog = await (await page.request.get(`${BASE}/api/design/catalog`)).json().catch(() => null)
if (!catalog?.templates?.length || !catalog?.themes?.length) {
  console.error('양식·테마 목록을 읽지 못했습니다 — /api/design/catalog 가 응답하지 않습니다')
  process.exit(1)
}
const ids = catalog.templates.filter((t) => t.id.startsWith('art-')).map((t) => t.id)
if (ALL) {
  THEME_DATA = catalog.themes
  THEMES = THEME_DATA.map((t) => t.id)
}

const failures = []
let checked = 0

/**
 * 글씨 자리를 찍어 **바탕**의 밝기를 낸다.
 *
 * 처음에는 자리 전체의 중앙값을 바탕으로 봤는데, 그림이 섞인 자리에서는 그게 바탕이
 * 아니었다. 아치 기둥이나 건반이 자리의 절반을 덮으면 중앙값이 그쪽으로 끌려가
 * **멀쩡한 포스터를 실패로 찍었다.**
 *
 * 그래서 글씨 색에 가까운 픽셀을 먼저 빼고, 남은 것의 중앙값을 바탕으로 본다.
 * 뺐더니 남는 것이 거의 없으면(5% 미만) 그건 글씨와 바탕이 같은 색이라는 뜻이라
 * 그 자체가 실패다 — 정확히 「글씨가 안 보인다」는 상태다.
 */
async function groundOf(target, ink) {
  const shot = await target.screenshot()
  return page.evaluate(
    async ([bytes, ink]) => {
      const blob = new Blob([new Uint8Array(bytes)], { type: 'image/png' })
      const bmp = await createImageBitmap(blob)
      const cv = new OffscreenCanvas(bmp.width, bmp.height)
      const cx = cv.getContext('2d')
      cx.drawImage(bmp, 0, 0)
      const d = cx.getImageData(0, 0, bmp.width, bmp.height).data
      const all = []
      const bg = []
      for (let i = 0; i < d.length; i += 4) {
        const px = { r: d[i], g: d[i + 1], b: d[i + 2] }
        all.push(px)
        // 글씨 색에 가까운 픽셀(글자와 그 언저리)은 바탕이 아니다
        const near = Math.abs(px.r - ink.r) + Math.abs(px.g - ink.g) + Math.abs(px.b - ink.b) < 120
        if (!near) bg.push(px)
      }
      if (bg.length < all.length * 0.05) return { ground: ink, blank: true }
      bg.sort((a, b) => a.r + a.g + a.b - (b.r + b.g + b.b))
      return { ground: bg[Math.floor(bg.length / 2)], blank: false }
    },
    [Array.from(shot), ink],
  )
}

/** 한 장만 보고 싶을 때 — POSTER_ONLY=art-line-keys npm run verify:poster:all */
const ONLY = process.env.POSTER_ONLY
const LIST = ONLY ? ids.filter((id) => id === ONLY) : ids
if (LIST.length === 0) {
  console.error(`${ONLY} 라는 양식이 없습니다`)
  process.exit(1)
}

/** 한 장을 그려 놓고 제목·출연진 두 자리의 대비를 잰다 */
async function readSheet() {
  const sheet = page.locator('.d-sheet').first()
  const out = []
  for (const [what, target] of [
    ['제목', sheet.locator('h1').first()],
    ['출연진', sheet.locator('p').last()],
  ]) {
    const box = await target.boundingBox().catch(() => null)
    if (!box || box.width < 8) continue
    const ink = await target.evaluate((el) => {
      const c = getComputedStyle(el).color.match(/[\d.]+/g).map(Number)
      return { r: c[0], g: c[1], b: c[2] }
    })
    const { ground, blank } = await groundOf(target, ink)
    out.push({ what, blank, r: ratio(lum(ink), lum(ground)) })
  }
  return out
}

async function draw(tpl, theme) {
  await page.goto(`${BASE}/events/${EVENT}/design/print?template=${tpl}&theme=${theme}`, {
    waitUntil: 'networkidle',
  })
  await page.waitForTimeout(1400)
}

/** 그려 놓은 종이에 다른 테마의 색·글꼴만 갈아 끼운다 */
async function repaint(theme) {
  await page.evaluate((t) => {
    const sheet = document.querySelector('.d-sheet')
    if (!sheet) return
    const vars = {
      '--d-paper': t.palette.paper,
      '--d-paper-alt': t.palette.paperAlt,
      '--d-ink': t.palette.ink,
      '--d-muted': t.palette.muted,
      '--d-accent': t.palette.accent,
      '--d-accent-soft': t.palette.accentSoft,
      '--d-line': t.palette.line,
      '--d-band': t.palette.band,
      '--d-band-ink': t.palette.bandInk,
      '--d-display': t.fonts.display,
      '--d-body': t.fonts.body,
    }
    for (const [k, v] of Object.entries(vars)) sheet.style.setProperty(k, v)
  }, theme)
  // 색이 바뀌면 다시 그려질 틈을 준다
  await page.waitForTimeout(60)

  /*
   * 색이 진짜로 갈렸는지 확인한다.
   *
   * 갈아 끼우기가 조용히 안 먹으면 **4968자리가 전부 같은 테마**를 잰 것이 되고,
   * 검사는 「0건 실패」라고 말한다. 아무것도 안 재고 통과했다고 말하는 것이
   * 실패를 못 잡는 것보다 나쁘다.
   */
  const applied = await page.evaluate(
    () => getComputedStyle(document.querySelector('.d-sheet')).getPropertyValue('--d-ink').trim(),
  )
  if (applied.toLowerCase() !== theme.palette.ink.toLowerCase()) {
    console.error(`\n색을 갈아 끼우지 못했습니다 — ${theme.id} 의 먹빛이 ${applied} 로 남아 있습니다`)
    process.exit(1)
  }
}

function note(tpl, theme, m) {
  if (m.blank) failures.push(`${tpl} @ ${theme} · ${m.what} — 글씨와 바탕이 같은 색이다`)
  else if (m.r < MIN) failures.push(`${tpl} @ ${theme} · ${m.what} ${m.r.toFixed(2)}:1`)
}

if (!ALL) {
  for (const tpl of LIST) {
    for (const theme of THEMES) {
      await draw(tpl, theme)
      for (const m of await readSheet()) {
        checked += 1
        note(tpl, theme, m)
      }
    }
  }
} else {
  /** 어림으로 재서 문턱에 가까웠던 조합 — 진짜로 다시 그려 확인한다 */
  const suspect = new Map()
  let done = 0
  for (const tpl of LIST) {
    // 밝은 종이 하나로 그려 놓고 색만 갈아 끼운다
    await draw(tpl, 'gala-ivory')
    for (const theme of THEME_DATA) {
      await repaint(theme)
      for (const m of await readSheet()) {
        checked += 1
        if (m.blank || m.r < SUSPECT) suspect.set(`${tpl}|${theme.id}`, { tpl, theme: theme.id })
      }
    }
    done += 1
    // 한 줄씩 새로 찍는다 — 파이프로 흘려 보낼 때 \r 는 아무것도 안 보인다
    console.log(`  ${done}/${LIST.length}장 · ${tpl} · ${checked}자리 · 확인할 것 ${suspect.size}가지`)
  }

  for (const { tpl, theme } of suspect.values()) {
    await draw(tpl, theme)
    for (const m of await readSheet()) note(tpl, theme, m)
  }
  console.log(`어림으로 ${checked}자리를 재고, 문턱에 가까운 ${suspect.size}가지를 다시 그려 확인했습니다.`)
}

await browser.close()
try {
  process.kill(-server.pid)
} catch {
  /* 이미 죽음 */
}

console.log(`\n그림 포스터 ${LIST.length}종 × 테마 ${THEMES.length}종 · ${checked}자리 검사`)
console.log(ALL ? `${failures.length}건 실패` : `${checked - failures.length}건 통과 · ${failures.length}건 실패`)
for (const line of failures) console.log(`  ✗ ${line}`)
process.exit(failures.length === 0 ? 0 : 1)
