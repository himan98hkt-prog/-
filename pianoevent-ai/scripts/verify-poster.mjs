// 그림 포스터의 글씨가 그림 위에서 실제로 읽히는가를 잰다.
//   node scripts/verify-poster.mjs
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
const THEMES = ['gala-noir', 'gala-ivory', 'classic-navy', 'rainbow-play']
const MIN = 4.5

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

const templates = await (await page.request.get(`${BASE}/api/design/templates`)).json().catch(() => null)
const ids = templates?.templates?.filter((t) => t.startsWith('art-')) ?? null

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

const LIST = ids ?? [
  'art-stage-piano', 'art-oil-hall', 'art-keys', 'art-hands', 'art-gala', 'art-field',
  'art-watercolor', 'art-blossom', 'art-summer', 'art-autumn', 'art-christmas', 'art-confetti',
  'art-line-front', 'art-line-keys', 'art-line-arch', 'art-ill-line', 'art-ill-engraving',
  'art-ill-riso', 'art-ill-ink', 'art-ill-deco', 'art-real-stage', 'art-real-keys', 'art-real-hands',
]

for (const tpl of LIST) {
  for (const theme of THEMES) {
    await page.goto(`${BASE}/events/${EVENT}/design/print?template=${tpl}&theme=${theme}`, {
      waitUntil: 'networkidle',
    })
    await page.waitForTimeout(1400)
    const sheet = page.locator('.d-sheet').first()
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
      const r = ratio(lum(ink), lum(ground))
      checked += 1
      if (blank) failures.push(`${tpl} @ ${theme} · ${what} — 글씨와 바탕이 같은 색이다`)
      else if (r < MIN) failures.push(`${tpl} @ ${theme} · ${what} ${r.toFixed(2)}:1`)
    }
  }
}

await browser.close()
try {
  process.kill(-server.pid)
} catch {
  /* 이미 죽음 */
}

console.log(`\n그림 포스터 ${LIST.length}종 × 테마 ${THEMES.length}종 · ${checked}자리 검사`)
console.log(`${checked - failures.length}건 통과 · ${failures.length}건 실패`)
for (const line of failures) console.log(`  ✗ ${line}`)
process.exit(failures.length === 0 ? 0 : 1)
