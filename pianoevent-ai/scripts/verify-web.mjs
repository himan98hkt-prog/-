/**
 * 홈페이지에 올리는 쪽들(받는 자리 · 사용설명서 · 상세페이지)을
 * 휴대폰 · 태블릿 · 컴퓨터 세 크기에서 눈으로 보지 않고 검사한다.
 *
 *   npm run verify:web
 *
 * 보는 것: 가로로 넘치는 곳 · 너무 작은 글씨 · 손가락으로 누르기 힘든 단추 ·
 *          끊어진 안쪽 링크.
 */
import { existsSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { chromium } from 'playwright'

const DIR = resolve('web/download')
const PAGES = ['index.html', 'guide.html', 'recital-manager-detail.html'].filter((f) =>
  existsSync(resolve(DIR, f)),
)
const HAVE = new Set(readdirSync(DIR))

const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const browser = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})
const failures = []

for (const file of PAGES) {
  for (const [size, width, height, mobile] of [
    ['휴대폰', 390, 844, true],
    ['태블릿', 768, 1024, true],
    ['컴퓨터', 1280, 900, false],
  ]) {
    const ctx = await browser.newContext({
      viewport: { width, height },
      deviceScaleFactor: 1,
      isMobile: mobile,
      locale: 'ko-KR',
    })
    // 검사 중에 설치 파일이 저절로 내려가면서 쪽이 넘어가지 않게 막는다
    await ctx.addInitScript(() => {
      document.addEventListener(
        'click',
        (e) => {
          const a = e.target instanceof Element ? e.target.closest('a[download]') : null
          if (a) e.preventDefault()
        },
        true,
      )
    })
    const page = await ctx.newPage()
    await page.goto(`file://${resolve(DIR, file)}`, { waitUntil: 'load' })
    await page.evaluate(async () => {
      const step = window.innerHeight * 0.7
      for (let y = 0; y < document.body.scrollHeight; y += step) {
        window.scrollTo(0, y)
        await new Promise((r) => setTimeout(r, 60))
      }
      window.scrollTo(0, 0)
    })
    await page.waitForTimeout(1200)

    const report = await page.evaluate(() => {
      const seen = (el) => el.offsetParent !== null || getComputedStyle(el).position === 'fixed'
      const small = []
      for (const el of document.querySelectorAll('p,li,td,th,span,a')) {
        if (!seen(el) || !el.textContent.trim()) continue
        const fs = parseFloat(getComputedStyle(el).fontSize)
        if (fs && fs < 13) small.push(`${el.tagName.toLowerCase()} ${fs}px`)
      }
      const tiny = []
      for (const el of document.querySelectorAll('a,button')) {
        if (!seen(el)) continue
        const r = el.getBoundingClientRect()
        if (r.height && r.height < 32 && getComputedStyle(el).display !== 'inline') {
          tiny.push(`${el.textContent.trim().slice(0, 16)} ${Math.round(r.height)}px`)
        }
      }
      return {
        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        small: small.slice(0, 4),
        tiny: tiny.slice(0, 4),
        links: Array.from(document.querySelectorAll('a[href]'))
          .map((a) => a.getAttribute('href'))
          .filter((h) => h && !/^(https?:|mailto:|#)/.test(h)),
        title: document.title,
      }
    })

    const where = `${file} · ${size}`
    if (report.overflow > 1) failures.push(`${where} — 가로로 ${report.overflow}px 넘침`)
    if (report.small.length) failures.push(`${where} — 글씨가 작음: ${report.small.join(', ')}`)
    if (report.tiny.length) failures.push(`${where} — 누르기 힘든 단추: ${report.tiny.join(', ')}`)
    for (const href of report.links) {
      const target = href.split(/[?#]/)[0]
      if (target && !HAVE.has(target)) failures.push(`${where} — 없는 곳으로 가는 링크: ${href}`)
    }
    if (!report.title.trim()) failures.push(`${where} — 제목이 비었음`)

    console.log(`${where}  넘침 ${report.overflow}px  링크 ${report.links.length}개`)
    await ctx.close()
  }
}

await browser.close()

if (failures.length) {
  console.error(`\n고칠 것 ${failures.length}가지`)
  for (const f of failures) console.error(`  · ${f}`)
  process.exit(1)
}
console.log(`\n${PAGES.length}쪽 × 3크기 — 모두 통과`)
