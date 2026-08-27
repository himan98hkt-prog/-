/**
 * 캐러셀 슬라이드를 1080×1080 PNG 로 뽑는다.
 *   python3 scripts/build-carousel.py && node scripts/carousel-shot.mjs
 * 결과: carousel/01.png … 14.png — 쇼핑몰 상품 갤러리에 그대로 올린다.
 */
import { chromium } from 'playwright'
import { existsSync, mkdirSync } from 'node:fs'
const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const browser = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})

mkdirSync('carousel', { recursive: true })
const page = await browser.newPage({ viewport: { width: 1200, height: 1200 }, deviceScaleFactor: 1 })
await page.goto('file:///home/user/-/pianoevent-ai/promo/carousel.html', { waitUntil: 'load' })
// 웹폰트가 없으면 시스템 글꼴로 떨어지므로, 있으면 다 받을 때까지 기다린다
await page.evaluate(() => document.fonts.ready).catch(() => {})
await page.waitForTimeout(1500)

const count = await page.locator('.slide').count()
const problems = []
for (let i = 0; i < count; i += 1) {
  const el = page.locator('.slide').nth(i)
  const n = String(i + 1).padStart(2, '0')
  await el.screenshot({ path: `carousel/${n}.png` })
  // 내용이 종이 밖으로 넘치지 않았는지 확인한다
  // 슬라이드는 높이가 1080 으로 고정이다. 넘친 내용은 잘려서 사라지므로 슬라이드 자체를 잰다.
  const overflow = await el.evaluate((node) => {
    let worst = Math.max(0, node.scrollHeight - node.clientHeight)
    // 잘려 나가는 경계는 슬라이드 바닥이 아니라 아래쪽 고정 줄(로고·쪽번호)이다.
    // 거기까지만 내용이 와야 글자가 겹치지 않는다.
    const foot = node.querySelector('.foot')
    const limit = foot ? foot.getBoundingClientRect().top - 8 : node.getBoundingClientRect().bottom
    for (const child of node.querySelectorAll('.body *')) {
      const over = child.getBoundingClientRect().bottom - limit
      if (over > worst) worst = Math.round(over)
    }
    return worst
  })
  if (overflow > 2) problems.push(`${n}: 내용이 ${overflow}px 넘칩니다`)
  console.log(`  ${n}.png${overflow > 2 ? `  ⚠ 넘침 ${overflow}px` : ''}`)
}
await browser.close()
console.log(`\n${count}장 생성`)
if (problems.length) {
  console.log('\n확인 필요:\n' + problems.join('\n'))
  process.exit(1)
}
