import { chromium } from 'playwright'
import { existsSync } from 'node:fs'
const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const b = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})
const URL = 'file:///home/user/-/pianoevent-ai/배포/demo/index.html'

for (const [name, w, dark] of [['demo-full', 1400, false], ['demo-mobile', 390, false], ['demo-dark', 1400, true]]) {
  const p = await b.newPage({ viewport: { width: w, height: 1200 }, colorScheme: dark ? 'dark' : 'light' })
  await p.goto(URL, { waitUntil: 'load' })
  await p.waitForTimeout(1200)
  await p.screenshot({ path: `screenshots/${name}.png`, fullPage: true })
  await p.close()
}
// 인쇄물 구간만 따로 — 종이가 잘리지 않는지 본다
for (const [name, w] of [['demo-paper-desktop', 1400], ['demo-paper-mobile', 390]]) {
  const p = await b.newPage({ viewport: { width: w, height: 1000 } })
  await p.goto(URL, { waitUntil: 'load' })
  await p.waitForTimeout(1000)
  await p.locator('.proscenium').screenshot({ path: `screenshots/${name}.png` })
  await p.close()
}
console.log('캡처 완료')
await b.close()
