import { existsSync } from 'node:fs'
import { chromium } from 'playwright'
const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const browser = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})
for (const [name, width, height, mobile] of [['mobile', 390, 844, true], ['desktop', 1280, 900, false]]) {
  const ctx = await browser.newContext({ viewport: { width, height }, isMobile: mobile, locale: 'ko-KR' })
  const page = await ctx.newPage()
  await page.goto('file:///home/user/-/pianoevent-ai/%EB%B0%B0%ED%8F%AC/%ED%94%BC%EC%95%84%EB%85%B8%EC%9D%B4%EB%B2%A4%ED%8A%B8-%EB%AF%B8%EB%A6%AC%EB%B3%B4%EA%B8%B0.html', { waitUntil: 'networkidle' })
  const r = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    imgs: document.images.length,
    broken: Array.from(document.images).filter((i) => !i.complete || i.naturalWidth === 0).length,
    h: document.body.scrollHeight,
  }))
  console.log(`${name.padEnd(8)} 가로넘침 ${r.overflow}px · 이미지 ${r.imgs}장(깨짐 ${r.broken}) · 높이 ${r.h}px`)
  await page.screenshot({ path: `promo/preview-check-${name}.jpg`, type: 'jpeg', quality: 60, fullPage: name === 'mobile' })
  await ctx.close()
}
await browser.close()
