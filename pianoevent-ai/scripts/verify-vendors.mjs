#!/usr/bin/env node
/**
 * **함께할 분들이 진짜로 저장되고, 내년에 돌아오는가.**
 *
 *   npm run build && node scripts/verify-vendors.mjs
 *
 * 단위 검사는 lib/vendors.ts 의 셈만 본다. 그런데 원장님이 겪으시는 실패는
 * 셈이 아니라 **「적었는데 다시 여니 없어졌다」** 다. 그래서 진짜 서버를 띄우고
 * 진짜 화면에서 적어 본 뒤, 창을 새로 열어 그대로 있는지 본다.
 *
 * 또 하나 — 이 기능의 값은 「내년에 그대로」에 있다. 다른 행사에서 수첩이
 * 돌아오지 않으면 그냥 메모장이다. 그것도 함께 잰다.
 */
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { chromium } from 'playwright'
import { killOnExit, requireFreePort, requireFreshBuild } from './lib/fresh-build.mjs'

const PORT = 3906
await requireFreshBuild()
await requireFreePort(PORT)

const BASE = `http://127.0.0.1:${PORT}`
// npx 를 죽여도 그 밑의 next-server 는 남는다. 남으면 **다음 검사가 낡은 서버를 잰다**
const server = spawn('npx', ['next', 'start', '-p', String(PORT)], { stdio: 'ignore', detached: true })
const stop = killOnExit(server)

for (let i = 0; i < 180; i += 1) {
  try { if ((await fetch(`${BASE}/`, { redirect: 'manual' })).status < 500) break } catch {}
  await new Promise((r) => setTimeout(r, 500))
}

const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const browser = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})
const failures = []
const say = (ok, line) => { if (!ok) failures.push(line); console.log(`${ok ? '✓' : '✗'} ${line}`) }

/** 화면을 거치지 않고 자료만 확인한다 — 화면이 거짓말을 해도 잡히게 */
async function bookings(eventId) {
  const res = await fetch(`${BASE}/api/events`)
  const json = await res.json()
  const found = (json?.events ?? []).find((e) => e.id === eventId)
  return found?.vendor_bookings ?? null
}

/**
 * 앞선 실행이 남긴 것을 먼저 치운다.
 *
 * 처음 돌렸을 때는 통과하고 두 번째부터 실패하는 검사는, 있으나 마나 한 검사다.
 * (실제로 그렇게 만들었다가 두 번째 실행에서 「적기」 단추를 못 찾고 멈췄다.)
 */
for (const category of ['hall', 'accompanist', 'mc', 'dress', 'photo', 'tuner']) {
  await fetch(`${BASE}/api/events/demo-event/vendors`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ category, name: '' }),
  })
}
const before = await (await fetch(`${BASE}/api/events`)).json()
for (const e of before?.events ?? []) {
  if (e.title === '제13회 정기 연주회') await fetch(`${BASE}/api/events/${e.id}`, { method: 'DELETE' })
}

const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: 'ko-KR' })
const page = await ctx.newPage()

// ── 적기 ───────────────────────────────────────────────────────────
await page.goto(`${BASE}/events/demo-event?tab=prep`, { waitUntil: 'networkidle' })
// 접혀 있는 것이 기본이다 — 접힌 줄에 빠진 갈래가 그대로 보이는지부터 본다
const shut = page.getByTestId('vendor-details')
say(!(await shut.evaluate((el) => el.open)), '처음에는 접혀 있다 — 화면이 무거워지지 않는다')
say(
  await page.getByText('아직 안 정하신 것', { exact: false }).isVisible(),
  '접힌 채로도 무엇이 비었는지 보인다',
)
await shut.locator('summary').click()
await page.waitForTimeout(300)
await page.getByLabel('우리 학원 지역').fill('일산동구')

await page.getByRole('button', { name: '연주홀 · 대관 적기' }).click()
await page.getByLabel('이름 · 상호').fill('하모니홀')
await page.getByLabel('연락처').fill('031-000-1234')
await page.getByLabel('금액').fill('300000')
await page.getByLabel('메모').fill('주차 10대 · 리허설 2시간 포함')
await page.getByRole('button', { name: '저장', exact: true }).click()
await page.waitForTimeout(1200)

say(await page.getByText('하모니홀').first().isVisible(), '적으면 화면에 바로 보인다')
say(await page.getByText('300,000원').first().isVisible(), '금액이 원 단위로 보인다')

// ── 창을 새로 열어도 남아 있는가 ────────────────────────────────────
const fresh = await ctx.newPage()
await fresh.goto(`${BASE}/events/demo-event?tab=prep`, { waitUntil: 'networkidle' })
await fresh.getByTestId('vendor-details').locator('summary').click()
await fresh.waitForTimeout(600)
say(await fresh.getByText('하모니홀').first().isVisible(), '창을 새로 열어도 그대로 있다')
say((await fresh.getByLabel('우리 학원 지역').inputValue()) === '일산동구', '지역이 학원에 남는다')

const saved = await bookings('demo-event')
say(saved?.hall?.name === '하모니홀' && saved?.hall?.fee === 300000, '자료에 실제로 저장된다')

// ── 전화 · 문자 바로 걸기 ──────────────────────────────────────────
const tel = await fresh.locator('a[href^="tel:"]').first().getAttribute('href')
say(tel === 'tel:0310001234', `전화 링크에 숫자만 남는다 (${tel})`)

// ── 지도 검색 — 지역이 붙는가, 학원 자료가 새지 않는가 ──────────────
//
// 갈래마다 다르게 굴어야 한다. 사진사는 지도에서 찾아지니 길을 셋 다 주고,
// 반주자는 개인이라 지도에 안 나오니 다른 길을 안내한다. 둘을 따로 잰다.
const openFind = async (id) => {
  const card = fresh.getByTestId(`vendor-${id}`)
  await card.getByRole('button', { name: '찾아보기' }).click()
  await fresh.waitForTimeout(300)
  return card
}

const photoCard = await openFind('photo')
const FIND_LINKS = 'a[href*="map.naver"], a[href*="map.kakao"], a[href*="search.naver"]'
const links = await photoCard
  .locator(FIND_LINKS)
  .evaluateAll((els) => els.map((el) => el.getAttribute('href')))
say(links.length === 3, `찾아지는 갈래는 길을 셋 준다 (${links.length}개)`)
say(
  links[0]?.includes('search.naver'),
  '가장 튼튼한 길(네이버 검색)이 첫 단추다',
)
say(
  links.every((u) => !u.includes('${') && !u.includes('undefined')),
  '주소에 채워지지 않은 자리가 남지 않는다',
)
say(links.every((u) => u.includes(encodeURIComponent('일산동구'))), '검색어에 학원 지역이 붙는다')
say(
  links.every((u) => !/김서연|박지호|demo-event|하모니 피아노학원/.test(decodeURIComponent(u))),
  '검색 주소에 아이 이름·학원 자료가 들어가지 않는다',
)

const mcCard = await openFind('accompanist')
const mcLinks = await mcCard
  .locator(FIND_LINKS)
  .evaluateAll((els) => els.map((el) => el.getAttribute('href')))
say(mcLinks.length === 1, `지도에 안 나오는 갈래는 길을 하나만 준다 (${mcLinks.length}개)`)
// 개수만 세면 순서를 바꿨을 때 엉뚱한 단추가 된 것을 못 잡는다 — 실제로 그랬다
say(
  mcLinks[0]?.includes('search.naver'),
  `그 하나는 가장 튼튼한 길이다 (${(mcLinks[0] ?? '').split('?')[0]})`,
)
say(
  await mcCard.getByText('음대 학과 사무실', { exact: false }).count() > 0,
  '지도에 안 나오는 갈래에는 다른 길을 알려 준다',
)

// ── 내년에 돌아오는가 (다른 행사에서 수첩이 뜨는가) ─────────────────
const created = await (
  await fetch(`${BASE}/api/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: '제13회 정기 연주회', event_at: '2027-09-18T15:00', venue: '구민회관 소공연장' }),
  })
).json()
const nextId = created?.event?.id
if (!nextId) {
  say(false, '내년 행사를 만들지 못했습니다')
} else {
  const next = await ctx.newPage()
  await next.goto(`${BASE}/events/${nextId}?tab=prep`, { waitUntil: 'networkidle' })
  await next.getByTestId('vendor-details').locator('summary').click()
  await next.waitForTimeout(600)
  const again = next.getByRole('button', { name: /하모니홀/ }).first()
  say(await again.count() > 0, '새 연주회에서 「지난번 그대로」가 뜬다')
  await again.click()
  await next.waitForTimeout(1200)
  const copied = await bookings(nextId)
  say(
    copied?.hall?.name === '하모니홀' && copied?.hall?.phone === '031-000-1234' && copied?.hall?.fee === 300000,
    '한 번 눌러 이름·연락처·금액이 그대로 들어온다',
  )
  await fetch(`${BASE}/api/events/${nextId}`, { method: 'DELETE' })
}

// ── 적어 두신 금액이 예산으로 흘러가는가 ────────────────────────────
//
// 이 기능의 값은 「한 번만 적으면 비용 예측까지 된다」에 있다.
// 두 화면이 따로 놀면 원장님은 같은 금액을 두 번 적으셔야 한다.
const plan = await ctx.newPage()
await plan.goto(`${BASE}/events/demo-event?tab=plan`, { waitUntil: 'networkidle' })
await plan.waitForTimeout(800)
say(
  await plan.getByText('하모니홀 · 적어 두신 금액', { exact: false }).count() > 0,
  '예산표에 「적어 두신 금액」 표시가 붙는다',
)
const venueLine = await plan
  .locator('label', { hasText: '대관료' })
  .first()
  .innerText()
say(venueLine.includes('300,000'), `예산의 대관료가 적어 두신 300,000원이 된다 (${venueLine.split('\n').pop()})`)

// ── 재능마켓 길 — 공급이 있는 갈래에만 ──────────────────────────────
const mcCard2 = await openFind('mc')
const soomgo = await mcCard2.locator('a[href*="soomgo"]').count()
say(soomgo === 1, `사람으로 구하는 갈래에 재능마켓 길이 있다 (${soomgo}개)`)
const soomgoHref = await mcCard2.locator('a[href*="soomgo"]').first().getAttribute('href')
say(soomgoHref === 'https://soomgo.com/', `숨고는 첫 화면으로만 보낸다 (${soomgoHref})`)
say(
  (await mcCard2.getByText('행사 사회자', { exact: false }).count()) > 0,
  '검색창에 칠 말을 글로 알려 준다',
)
const dressCard = await openFind('dress')
say(
  (await dressCard.locator('a[href*="soomgo"]').count()) === 0,
  '공급이 없는 갈래(드레스 대여)에는 재능마켓 길을 만들지 않는다',
)

// ── 자리 비우기 ────────────────────────────────────────────────────
await fresh.getByRole('button', { name: '연주홀 · 대관 고치기' }).click()
await fresh.getByRole('button', { name: '이 자리 비우기' }).click()
await fresh.waitForTimeout(1000)
const cleared = await bookings('demo-event')
say(!cleared?.hall, '비우면 그 자리가 지워진다')

await browser.close()
if (typeof stop === 'function') stop()

if (failures.length) {
  console.error(`\n고칠 것 ${failures.length}가지`)
  for (const f of failures) console.error(`  · ${f}`)
  process.exit(1)
}
console.log('\n함께할 분들 — 모두 통과')
