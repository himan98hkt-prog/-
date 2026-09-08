#!/usr/bin/env node
/**
 * **쉬움 재기.**
 *
 * "쉽게 만들었다" 는 말은 재어 보지 않으면 거짓말이 되기 쉽다. 실제로 이 프로그램은
 * 라운드를 거듭하며 기능이 붙는 동안 화면이 조용히 무거워졌다 — 재어 보니
 * 인쇄물 화면 하나에 눌러 볼 것이 102개, 길이가 6,000px 이었다. 여섯 화면을 내려야
 * 끝나는 화면을 두고 "이대로 뽑으셔도 됩니다" 라고 적어 둔 셈이다.
 *
 * 그래서 화면마다 **원장님이 실제로 마주하는 수**를 세어 문턱을 넘으면 실패로 만든다.
 *
 *   보이는 조작   접힌 것을 뺀, 지금 눌러 볼 수 있는 것의 수
 *   첫 판         스크롤하지 않고 보이는 자리의 조작 수 — 여기서 하나를 고르셔야 한다
 *   높이          한 화면을 다 보려면 몇 px 을 내려야 하는가
 *   작은 글씨     12px 아래로 나오는 글자 (연세를 생각하면 읽으라는 글씨가 아니다)
 *
 * 표 입력처럼 **본디 많을 수밖에 없는** 화면은 문턱을 따로 둔다.
 * 인쇄물 미리보기·콘티는 '축소한 그림' 이라 작은 글씨를 세지 않는다.
 *
 *   npm run build && node scripts/verify-simple.mjs
 */
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { chromium } from 'playwright'
import { requireFreePort, requireFreshBuild } from './lib/fresh-build.mjs'

const PORT = 3993

// 남이 물고 있는 문이면 **남의(낡은) 서버를 재게 된다**
await requireFreePort(PORT)
const BASE = `http://127.0.0.1:${PORT}`
const EVENT = 'demo-event'

/**
 * 화면마다 [주소, 보이는 조작 최대, 첫 판 최대, 높이 최대].
 * 지금 값보다 조금씩 여유를 둔 문턱이다 — 조금 느는 것까지 막자는 것이 아니라,
 * 또 두 배가 되는 것을 막자는 것이다.
 */
const SCREENS = [
  ['행사 목록', '/events', 22, 22, 1600],
  ['행사 화면 (차례 안내)', `/events/${EVENT}`, 20, 20, 1600],
  // 명단은 표다 — 아이 한 명이 칸 여러 개라 수가 많은 것이 당연하다. 첫 판만 본다
  ['① 학생 명단', `/events/${EVENT}?tab=roster`, 400, 22, 4000],
  ['② 순서표·대본', `/events/${EVENT}?tab=program`, 30, 26, 3200],
  ['③ 인쇄물 디자인', `/events/${EVENT}/design`, 55, 26, 2600],
  /**
   * 진행 준비 — 이 프로그램에서 **가장 무거운 화면**이다.
   * 체크리스트 스물몇 줄에 안내 문자·콘티가 붙어 있어, 「함께할 분들」을 넣기 전에도
   * 이미 눌러 볼 것이 61개·4,200px 였다(재어 봤다). 그래서 새로 붙인 여섯 갈래는
   * 접어 두었고, 접힌 채로는 +1개·+79px 만 든다.
   * 문턱은 지금 값에 여유를 조금 둔 것이다 — 또 두 배가 되는 것을 막자는 뜻이다.
   */
  ['④ 진행 준비', `/events/${EVENT}?tab=prep`, 66, 26, 4500],
  ['인쇄 화면', `/events/${EVENT}/design/print?template=poster-classic`, 14, 14, 1800],
  ['무대 화면', `/events/${EVENT}/stage`, 40, 20, 2400],
  ['감동영상', `/events/${EVENT}/video`, 50, 32, 2200],
  ['당일 진행', `/events/${EVENT}/live`, 42, 24, 2200],
  ['초대장', `/events/${EVENT}/invite`, 30, 26, 1600],
  ['학원 설정', '/settings', 34, 22, 3200],
]

async function waitForServer(ms = 90000) {
  const start = Date.now()
  while (Date.now() - start < ms) {
    try { if ((await fetch(`${BASE}/`, { redirect: 'manual' })).status < 500) return true } catch {}
    await new Promise((r) => setTimeout(r, 400))
  }
  return false
}

requireFreshBuild()

const server = spawn(process.execPath,
  ['node_modules/next/dist/bin/next', 'start', '-p', String(PORT)],
  { stdio: ['ignore', 'ignore', 'ignore'], detached: true, env: { ...process.env, NODE_ENV: 'production' } })

if (!(await waitForServer())) { console.error('서버 안 뜸'); process.exit(1) }

const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const browser = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 } })
const page = await ctx.newPage()
// 처음 안내를 닫아 둔 상태로 (안내는 따로 본다)
await page.goto(`${BASE}/events`, { waitUntil: 'networkidle' })
await page.evaluate(() => { try { localStorage.setItem('pianoevent.tour.v1', 'done') } catch {} })

const rows = []
const failures = []
// 어떤 조작거리가 있는지 이름까지 뽑아 본다 (사람이 볼 때만)
const DETAIL = process.argv[2] ?? null
for (const [name, path, maxControls, maxFold, maxHeight] of SCREENS) {
  if (DETAIL && !name.includes(DETAIL)) continue
  await page.goto(BASE + path, { waitUntil: 'networkidle' })
  await page.waitForTimeout(2200)
  const m = await page.evaluate(() => {
    // 접힌 <details> 안은 화면에 없다 — checkVisibility 가 content-visibility 까지 본다
    const vis = (el) => {
      if (typeof el.checkVisibility === 'function' &&
          !el.checkVisibility({ checkVisibilityCSS: true, contentVisibilityAuto: true, opacityProperty: true, visibilityProperty: true })) return false
      if (el.closest('details:not([open])')) return false
      const r = el.getBoundingClientRect()
      return r.width > 0 && r.height > 0
    }
    const all = [...document.querySelectorAll('button, a[href], input, select, textarea, summary, [role="button"]')]
      .filter((el) => !el.closest('[data-testid="first-run"]'))
    const shown = all.filter(vis)
    // 접혀 있어 지금은 안 보이는 것
    const hidden = all.length - shown.length
    const words = (document.body.innerText || '').replace(/\s+/g, ' ').trim()
    return {
      controls: shown.length,
      folded: hidden,
      chars: words.length,
      // 화면 첫 판(스크롤 없이 보이는 곳)에 있는 조작거리
      aboveFold: shown.filter((el) => el.getBoundingClientRect().top < window.innerHeight).length,
      height: document.documentElement.scrollHeight,
      // 글자가 실제로 몇 px 로 나오는가 — 원장님 연세를 생각하면 12px 아래는 못 읽으신다
      tiny: (() => {
        let n = 0
        for (const el of document.querySelectorAll('body *')) {
          if (!el.childNodes.length) continue
          const hasText = [...el.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim().length > 1)
          if (!hasText) continue
          // 인쇄물 미리보기·콘티는 '축소한 그림' 이라 작은 게 당연하다 — 화면 글씨만 센다
          if (el.closest('.d-sheet, [data-testid="design-preview"], [data-testid="storyboard"], canvas, svg')) continue
          const r = el.getBoundingClientRect()
          if (r.width === 0 || r.height === 0) continue
          if (parseFloat(getComputedStyle(el).fontSize) < 12) n += 1
        }
        return n
      })(),
      // 누르는 자리가 손가락에 맞는가 (44px 권장)
      small: [...document.querySelectorAll('button, a[href], input[type=checkbox], input[type=radio], summary')]
        .filter((el) => { const r = el.getBoundingClientRect(); return r.height > 0 && r.height < 32 }).length,
    }
  })
  rows.push({ name, ...m })
  if (m.controls > maxControls) failures.push(`${name} — 눌러 볼 것이 ${m.controls}개입니다 (${maxControls}개까지). 고르는 자리를 접어 주세요`)
  if (m.aboveFold > maxFold) failures.push(`${name} — 첫 판에 ${m.aboveFold}개가 보입니다 (${maxFold}개까지). 지금 하실 것 하나가 묻힙니다`)
  if (m.height > maxHeight) failures.push(`${name} — 화면이 ${m.height}px 입니다 (${maxHeight}px 까지). 끝까지 못 내려가십니다`)
  if (m.tiny > 0) failures.push(`${name} — 12px 아래 글씨가 ${m.tiny}곳 있습니다. [글씨 크게] 를 눌러도 안 커집니다`)
  if (DETAIL) {
    const labels = await page.evaluate(() => {
      const vis = (el) => { if (el.closest('details:not([open])')) return false; if (typeof el.checkVisibility === 'function' && !el.checkVisibility({checkVisibilityCSS:true,contentVisibilityAuto:true,opacityProperty:true,visibilityProperty:true})) return false; const r = el.getBoundingClientRect(); return r.width>0&&r.height>0 }
      const zone = (el) => {
        if (el.closest('nav') || el.closest('header')) return '머리띠'
        const s = el.closest('[data-testid], section, .rounded-lg, [class*="Card"]')
        const t = s?.getAttribute('data-testid')
        if (t) return t
        const card = el.closest('div')
        const head = el.closest('section, div')?.querySelector('h2,h3,p,legend,label')
        return (head?.textContent ?? '(그밖)').trim().replace(/\s+/g,' ').slice(0, 22)
      }
      const out = {}
      for (const el of document.querySelectorAll('button, a[href], input, select, textarea, summary, [role="button"]')) {
        if (!vis(el)) continue
        const k = zone(el)
        out[k] = (out[k] ?? 0) + 1
      }
      return out
    })
    console.log('\n[' + name + ']')
    for (const [k, v] of Object.entries(labels).sort((a,b)=>b[1]-a[1])) console.log('  ' + String(v).padStart(3) + '  ' + k)
  }
}

console.log('화면'.padEnd(24), '보이는 조작', '첫 판', '접힘', '글자수', '높이px', '작은글씨', '작은단추')
for (const r of rows) {
  console.log(
    r.name.padEnd(22),
    String(r.controls).padStart(8),
    String(r.aboveFold).padStart(6),
    String(r.folded).padStart(5),
    String(r.chars).padStart(7),
    String(r.height).padStart(7),
    String(r.tiny).padStart(7),
    String(r.small).padStart(7),
  )
}

// 글씨 크기 단추가 **가장 작은 글씨까지** 키우는가.
// 예전에는 text-[10px] 처럼 px 로 박아 둔 곳이 있어, 정작 안 보이는 글씨는 그대로였다.
if (!DETAIL) {
  await page.goto(BASE + '/settings', { waitUntil: 'networkidle' })
  await page.waitForTimeout(1200)
  const smallest = () =>
    page.evaluate(() => {
      let min = Infinity
      for (const el of document.querySelectorAll('body *')) {
        if (el.closest('.d-sheet, canvas, svg')) continue
        if (![...el.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim().length > 1)) continue
        const r = el.getBoundingClientRect()
        if (!r.width || !r.height) continue
        min = Math.min(min, parseFloat(getComputedStyle(el).fontSize))
      }
      return min
    })
  const before = await smallest()
  for (let i = 0; i < 2; i += 1) {
    await page.getByTestId('text-size').click().catch(() => {})
    await page.waitForTimeout(400)
  }
  const after = await smallest()
  console.log(`\n글씨 크게 — 가장 작은 글씨 ${before}px → ${after}px`)
  if (before < 12) failures.push(`가장 작은 글씨가 ${before}px 입니다 (12px 이상이어야 합니다)`)
  if (after <= before) failures.push(`[글씨 크게] 를 눌러도 가장 작은 글씨가 그대로입니다 (${before}px → ${after}px)`)
}

await browser.close()
try { process.kill(-server.pid) } catch {}

if (DETAIL) process.exit(0)
console.log(`\n${SCREENS.length}개 화면 검사 · ${failures.length}건 실패`)
for (const line of failures) console.log(`  ✗ ${line}`)
process.exit(failures.length === 0 ? 0 : 1)
