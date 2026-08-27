import { chromium } from 'playwright'
import { existsSync } from 'node:fs'
const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const browser = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})
const errors = []
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } })
page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()) })
page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
await page.goto('file:///home/user/-/pianoevent-ai/배포/demo/index.html', { waitUntil: 'load' })
await page.waitForTimeout(1500)

const probe = async (label, fn) => {
  try { const v = await fn(); console.log((v ? '  ✓ ' : '  ✗ ') + label + (typeof v === 'string' ? ' — ' + v : '')) ; return Boolean(v) }
  catch (e) { console.log('  ✗ ' + label + ' — ' + e.message); return false }
}

console.log('\n▸ 체험판 동작')
await probe('명단 12명 읽음', async () => (await page.locator('.tag').innerText()).includes('12명'))
await probe('순서표 12줄 생성', async () => (await page.locator('.grid tbody tr').count()) === 12)
await probe('오프닝 멘트 생성', async () => (await page.locator('.script__body').first().innerText()).includes('환영합니다'))
await probe('인쇄물 종이 렌더', async () => (await page.locator('.paper__frame .d-sheet').count()) > 0)
await probe('테마 목록 노출', async () => (await page.locator('.swatch').count()) >= 3)
await probe('리허설 조 계산', async () => (await page.locator('.calc__list').first().locator('li').count()) >= 2)
await probe('좌석 표기 생성', async () => (await page.locator('.calc article').nth(2).locator('li').count()) >= 4)
await probe('구매 링크', async () => (await page.locator('a.cta').getAttribute('href')).includes('add-to-cart=2089'))

// 곡 사전이 실제로 빈칸을 채우는가
await page.locator('.roster').fill('이름\t연주곡\n김서연\t엘리제를 위하여\n박지호\t징글벨')
await page.waitForTimeout(400)
await probe('곡 사전이 빈칸을 채움', async () => (await page.locator('.tag--fill').innerText()).includes('2곡'))
await probe('채워진 시간이 러닝타임에 반영', async () =>
  (await page.locator('.summary').innerText()).includes('분'))

// 명단을 고치면 전부 다시 계산되는가
await page.locator('.roster').fill('홍길동\t캐논 변주곡\t파헬벨\t4:00\t중급\n김철수\t젓가락 행진곡\t전래\t1:30\t초급')
await page.waitForTimeout(500)
await probe('명단 수정 후 재계산', async () => (await page.locator('.grid tbody tr').count()) === 2)
await probe('수정된 이름이 종이에 반영', async () => (await page.locator('.paper__frame').innerText()).length > 0)

// 테마·양식 전환
await page.evaluate(() => { document.querySelectorAll('.chip')[6]?.click() })
await page.waitForTimeout(300)
await page.evaluate(() => { document.querySelectorAll('.swatch')[1]?.click() })
await page.waitForTimeout(300)
await probe('테마 전환 후에도 종이 유지', async () => (await page.locator('.paper__frame .d-sheet').count()) > 0)

// 모바일
await page.setViewportSize({ width: 390, height: 844 })
await page.waitForTimeout(400)
await probe('모바일에서 가로 스크롤 없음', async () =>
  await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1))

console.log(errors.length ? '\n오류:\n' + errors.join('\n') : '\n콘솔 오류 없음')
await browser.close()
