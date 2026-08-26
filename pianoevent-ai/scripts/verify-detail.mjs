import { existsSync } from 'node:fs'
import { chromium } from 'playwright'

const FILE = 'file:///home/user/-/pianoevent-ai/detail/piano-event-detail.html'
const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const browser = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})

for (const [name, width, height, mobile] of [
  ['mobile', 390, 844, true],
  ['tablet', 768, 1024, true],
  ['desktop', 1280, 900, false],
]) {
  const ctx = await browser.newContext({
    viewport: { width, height },
    deviceScaleFactor: 1,
    isMobile: mobile,
    locale: 'ko-KR',
  })
  const page = await ctx.newPage()
  await page.goto(FILE, { waitUntil: 'networkidle' })
  // reveal 애니메이션이 끝까지 돌도록 스크롤을 흉내 낸다
  await page.evaluate(async () => {
    const step = window.innerHeight * 0.6
    for (let y = 0; y < document.body.scrollHeight; y += step) {
      window.scrollTo(0, y)
      await new Promise((r) => setTimeout(r, 90))
    }
    window.scrollTo(0, 0)
    await new Promise((r) => setTimeout(r, 400))
  })
  await page.waitForTimeout(3500) // reveal 안전장치까지 확인
  await page.screenshot({ path: `/home/user/-/pianoevent-ai/promo/detail-${name}.jpg`, type: 'jpeg', quality: 70, fullPage: true })

  // 가로 스크롤(넘침) 검사 + 주요 요소 확인
  const report = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    hidden: Array.from(document.querySelectorAll('.reveal')).filter((el) => getComputedStyle(el).opacity === '0').length,
    cta: document.querySelector('.cta-btn')?.getAttribute('href'),
    minFont: Math.min(...Array.from(document.querySelectorAll('p,span,li')).map((el) => parseFloat(getComputedStyle(el).fontSize)).filter(Boolean)),
    height: document.body.scrollHeight,
  }))
  console.log(`${name.padEnd(8)} 가로넘침 ${report.overflow}px · 미표시 ${report.hidden}개 · 최소글씨 ${report.minFont}px · 높이 ${report.height}px`)
  console.log(`         CTA ${report.cta}`)
  await ctx.close()
}
await browser.close()
