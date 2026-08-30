/**
 * 첫 화면(켜지는 동안 뜨는 창)을 브라우저로 띄워 사진을 찍는다.
 *
 *   node scripts/splash-shot.mjs
 *
 * 설치본을 뽑아 깔아 보지 않고도 첫 화면을 눈으로 확인할 수 있다.
 */
import { existsSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { chromium } from 'playwright'
const require = createRequire(import.meta.url)
const { splashHtml } = require('../desktop/splash.js')
const img = `data:image/jpeg;base64,${readFileSync('public/art/app/splash.jpg').toString('base64')}`
const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const browser = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})
const page = await (await browser.newContext({ viewport: { width: 560, height: 340 }, deviceScaleFactor: 2 })).newPage()
await page.setContent(splashHtml(img))
await page.waitForTimeout(600)
await page.screenshot({ path: 'shots/splash.png' })
await browser.close()
console.log('ok')
