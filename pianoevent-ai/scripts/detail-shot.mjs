import { chromium } from 'playwright'
import { existsSync } from 'node:fs'
const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const b = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})
const URL = 'file:///home/user/-/pianoevent-ai/detail/piano-event-detail.html'
const shots = [
  ['detail-features', 1100, '.feat-grid'],
  ['detail-chain', 1100, '.chain'],
  ['detail-numbers', 1100, '.numbers'],
  ['detail-scope', 1000, '.scope-grid'],
  ['detail-flow', 1000, '.flow'],
  ['detail-compare', 1000, '.cmp-wrap'],
  ['detail-hero-btn', 1000, '.hero .btn-row'],
  ['detail-scope-mobile', 390, '.scope-grid'],
]
for (const [name, w, sel] of shots) {
  const p = await b.newPage({ viewport: { width: w, height: 900 } })
  await p.goto(URL, { waitUntil: 'load' })
  await p.waitForTimeout(600)
  await p.evaluate(() => document.querySelectorAll('.reveal').forEach((el) => el.classList.add('in')))
  await p.waitForTimeout(300)
  const el = p.locator(sel).first()
  await el.scrollIntoViewIfNeeded()
  await p.waitForTimeout(300)
  await el.screenshot({ path: `screenshots/${name}.png` })
  await p.close()
  console.log(name)
}
await b.close()
