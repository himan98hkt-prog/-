import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { chromium } from 'playwright'

const FILE = 'file://' + resolve('web/download/recital-manager-detail.html')
const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const b = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})
const widths = [320, 360, 390, 430, 480, 540, 600, 660, 704, 768, 840, 900, 960, 1010, 1056]
const out = []
for (const w of widths) {
  const ctx = await b.newContext({ viewport: { width: w, height: 900 }, deviceScaleFactor: 1 })
  const p = await ctx.newPage()
  await p.goto(FILE, { waitUntil: 'load' })
  await p.evaluate(async () => {
    const step = window.innerHeight * 0.8
    for (let y = 0; y < document.body.scrollHeight; y += step) {
      window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 40))
    }
    window.scrollTo(0, 0)
  })
  await p.waitForTimeout(1500)
  const h = await p.evaluate(() => document.documentElement.scrollHeight)
  out.push([w, h])
  console.log(`${w}\t${h}`)
  await ctx.close()
}
await b.close()
console.log('JSON ' + JSON.stringify(out))
