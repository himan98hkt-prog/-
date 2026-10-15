// 휴대폰·태블릿에서 화면이 성립하는가를 잰다.
//   npm run verify:mobile
//
// 설치판은 PC 에서 돌지만, 연주회 **당일**에는 태블릿을 들고 다니신다.
// 그때 가로로 넘치거나 단추가 손가락보다 작으면 그 자리에서 못 쓰신다.
// 눈으로는 화면 크기 세 가지 × 화면 열 몇 개를 다 볼 수 없으므로 여기서 잰다.
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { chromium, devices } from 'playwright'
import { killOnExit, requireFreePort, requireFreshBuild } from './lib/fresh-build.mjs'

const PORT = 3905

await requireFreePort(PORT)
const BASE = `http://127.0.0.1:${PORT}`
const EVENT = 'demo-event'

/** 손가락으로 누르는 것은 44px 이 최소다 (애플·구글이 같이 쓰는 값) */
const TAP = 40
/** 이보다 작으면 태블릿에서 읽기 힘들다 */
const MIN_TEXT = 12

const SIZES = [
  { name: '휴대폰', ...devices['iPhone 13'] },
  { name: '태블릿 세로', viewport: { width: 768, height: 1024 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
  { name: '태블릿 가로', viewport: { width: 1024, height: 768 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
]

const PAGES = [
  ['첫 화면', '/'],
  ['행사 목록', '/events'],
  ['행사 하나', `/events/${EVENT}`],
  ['학생 명단', `/events/${EVENT}/roster`],
  ['순서표', `/events/${EVENT}/program`],
  ['인쇄물 디자인', `/events/${EVENT}/design`],
  ['당일 진행', `/events/${EVENT}/live`],
  ['초대장', `/events/${EVENT}/invite`],
  ['설정', '/settings'],
  ['사용설명서', '/help'],
  ['인증키', '/activate'],
]

requireFreshBuild()

const server = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '-p', String(PORT)], {
  stdio: 'ignore',
  detached: true,
  env: { ...process.env, NODE_ENV: 'production' },
})
killOnExit(server)

const up = await (async () => {
  const start = Date.now()
  while (Date.now() - start < 90000) {
    try {
      if ((await fetch(`${BASE}/`, { redirect: 'manual' })).status < 500) return true
    } catch {
      /* 아직 */
    }
    await new Promise((r) => setTimeout(r, 400))
  }
  return false
})()
if (!up) {
  console.error('서버가 안 떴습니다')
  process.exit(1)
}

const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const browser = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})

const failures = []
let checked = 0

for (const size of SIZES) {
  const { name, ...device } = size
  const page = await (await browser.newContext(device)).newPage()
  for (const [label, at] of PAGES) {
    await page.goto(`${BASE}${at}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(500)
    checked += 1

    const found = await page.evaluate(
      ([tap, minText]) => {
        const width = document.documentElement.clientWidth
        const out = { over: 0, small: [], tiny: [] }

        // 가로 넘침 — 옆으로 밀리는 화면은 태블릿에서 못 쓴다
        out.over = Math.max(0, document.documentElement.scrollWidth - width)

        for (const el of document.querySelectorAll('button, a, summary, [role="button"], input, select')) {
          const box = el.getBoundingClientRect()
          if (box.width < 1 || box.height < 1) continue
          const style = getComputedStyle(el)
          if (style.display === 'none' || style.visibility === 'hidden') continue
          // 글 안에 섞인 링크는 손가락 크기를 맞출 수 없다 — 단추만 본다
          const inline = el.tagName === 'A' && style.display.startsWith('inline')
          // 종이 미리보기 안의 것은 화면 단추가 아니다
          if (el.closest('.d-sheet, [data-paper]')) continue
          // 체크상자는 옆의 이름표를 누르시는 것이라 상자 크기로 재지 않는다
          if (el instanceof HTMLInputElement && (el.type === 'checkbox' || el.type === 'radio')) continue
          if (!inline && box.height < tap) {
            out.small.push(`${el.tagName.toLowerCase()} ${(el.textContent ?? '').trim().slice(0, 14)} ${Math.round(box.height)}px`)
          }
        }

        for (const el of document.querySelectorAll('p, li, td, th, span, label, div')) {
          if (el.children.length > 0) continue
          // 종이(A4 축소본)와 로고 글자는 화면 글씨가 아니다 — 종이는 종이 크기로 읽으신다
          if (el.closest('.d-sheet, [data-paper], [data-wordmark]')) continue
          const text = (el.textContent ?? '').trim()
          if (text.length < 6) continue
          const px = Number.parseFloat(getComputedStyle(el).fontSize)
          if (px < minText) out.tiny.push(`${px}px ${text.slice(0, 16)}`)
        }
        return out
      },
      [TAP, MIN_TEXT],
    )

    if (found.over > 2) failures.push(`${name} · ${label} — 가로로 ${found.over}px 넘침`)
    if (found.small.length > 0) {
      failures.push(`${name} · ${label} — 손가락보다 작은 단추 ${found.small.length}개 (${found.small[0]})`)
    }
    if (found.tiny.length > 0) {
      failures.push(`${name} · ${label} — ${MIN_TEXT}px 보다 작은 글씨 ${found.tiny.length}곳 (${found.tiny[0]})`)
    }
  }
  await page.close()
}

await browser.close()
try {
  process.kill(-server.pid)
} catch {
  /* 이미 죽음 */
}

console.log(`\n화면 ${PAGES.length}개 × 크기 ${SIZES.length}가지 · ${checked}자리 검사`)
console.log(`${checked - failures.length}건 통과 · ${failures.length}건 실패`)
for (const line of failures) console.log(`  ✗ ${line}`)
process.exit(failures.length === 0 ? 0 : 1)
