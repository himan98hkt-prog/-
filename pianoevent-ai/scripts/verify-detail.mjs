import { existsSync } from 'node:fs'
import { chromium } from 'playwright'

const FILE = 'file:///home/user/-/pianoevent-ai/detail/piano-event-detail.html'
const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const browser = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})
const failures = []

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

  // 그림이 카드 밖으로 나가거나, 카드에 눌려 잘리지 않는지 — 원장님이 보시는 그 화면 그대로
  const clipped = await page.evaluate(() =>
    Array.from(document.querySelectorAll('img'))
      .map((img) => {
        const rect = img.getBoundingClientRect()
        if (rect.width === 0) return null
        // 실제 비율대로 그려졌는가 (억지로 눌리면 내용이 찌그러진다)
        const drawn = rect.height / rect.width
        const natural = img.naturalHeight / img.naturalWidth
        const squashed = natural > 0 && Math.abs(drawn - natural) / natural > 0.02
        // 잘라 내는 조상이 있는가
        let cut = 0
        for (let node = img.parentElement; node; node = node.parentElement) {
          const style = getComputedStyle(node)
          if (style.overflow === 'hidden' || style.overflowY === 'hidden') {
            const box = node.getBoundingClientRect()
            cut = Math.max(cut, Math.round(rect.bottom - box.bottom), Math.round(box.top - rect.top))
          }
        }
        return squashed || cut > 1 ? { alt: img.alt.slice(0, 28), squashed, cut } : null
      })
      .filter(Boolean),
  )
  if (clipped.length > 0) {
    failures.push(`${name}: 그림 ${clipped.length}장이 잘리거나 찌그러짐 — ${JSON.stringify(clipped)}`)
    console.log(`         ✗ 그림 잘림 ${JSON.stringify(clipped)}`)
  } else {
    console.log('         ✓ 그림 전부 온전히 표시됨')
  }
  if (report.overflow > 1) failures.push(`${name}: 가로로 ${report.overflow}px 넘침`)
  await ctx.close()
}
await browser.close()

if (failures.length > 0) {
  console.error(`\n${failures.length}건 실패`)
  for (const failure of failures) console.error(`  ✗ ${failure}`)
  process.exitCode = 1
} else {
  console.log('\n상세페이지 검사 통과')
}
