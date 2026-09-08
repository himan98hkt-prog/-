/**
 * 상품 페이지에 붙일 코드가 **스크립트 없이도** 제대로 서는지 본다.
 *
 *   npm run verify:embed
 *
 * 워드프레스는 붙여넣은 <script> 를 지우는 일이 잦다. 실제로 그래서 상세페이지가
 * 600px 에서 잘린 채 상품 페이지에 걸렸다. 그래서 높이 맞추는 일을 상세페이지가
 * 스스로 하도록 바꿨고(같은 도메인이면 window.frameElement 로 제 틀을 잡는다),
 * 이 검사는 **스크립트를 한 줄도 넣지 않은 상품 페이지**를 흉내 내어
 * 잘리지 않는지, 가운데 서는지, 남는 공간이 없는지를 잰다.
 *
 * file:// 로는 같은 출처 판정이 안 나오므로 진짜 웹서버를 띄워서 잰다.
 */
import { spawn } from 'node:child_process'
import { createServer } from 'node:net'
import { existsSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { chromium } from 'playwright'

const PORT = 3907
const SNIPPET = 'web/상세페이지-붙여넣기.html'
const HOST_FILE = resolve('web/download/_embed-test.html')

const free = await new Promise((ok) => {
  const s = createServer().once('error', () => ok(false)).once('listening', () => s.close(() => ok(true)))
  s.listen(PORT, '127.0.0.1')
})
if (!free) {
  console.error(`${PORT} 번 문을 누가 쓰고 있습니다. 그대로 재면 엉뚱한 것을 잽니다.`)
  process.exit(1)
}

const raw = readFileSync(SNIPPET, 'utf8')
// 주석 안의 <script> 는 설명글이다. 진짜로 도는 코드만 본다
if (/<script/i.test(raw.replace(/<!--[\s\S]*?-->/g, ''))) {
  console.error(`${SNIPPET} 에 스크립트가 남아 있습니다 — 워드프레스가 지우면 또 잘립니다.`)
  process.exit(1)
}

// 우커머스 상품 페이지를 흉내 낸다. **스크립트는 한 줄도 넣지 않는다.**
writeFileSync(HOST_FILE, `<!doctype html><meta charset=utf-8><title>상품</title>
<style>body{margin:0;font-family:sans-serif;background:#fff}
.site{max-width:1550px;margin:0 auto;padding:20px}
.tabs{border-bottom:2px solid #eee;padding:10px 0;color:#666}
.after{padding:40px 0;font-size:20px}</style>
<div class="site"><div class="tabs">설명 &nbsp; 상품평 (0)</div>
${raw.replace('https://accelssam.com/download/recital-manager-detail.html', 'recital-manager-detail.html')}
<div class="after">연관 상품</div></div>`, 'utf8')

const server = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1',
  '--directory', resolve('web/download')], { stdio: 'ignore' })
const stop = () => { try { server.kill() } catch {} ; rmSync(HOST_FILE, { force: true }) }
process.on('exit', stop)
await new Promise((r) => setTimeout(r, 900))

const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const browser = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})
const failures = []

for (const [name, w, h] of [['컴퓨터', 1920, 1000], ['노트북', 1440, 900], ['태블릿', 768, 1024], ['휴대폰', 390, 844]]) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ko-KR' })
  const page = await ctx.newPage()
  await page.goto(`http://127.0.0.1:${PORT}/_embed-test.html`, { waitUntil: 'load' })
  await page.evaluate(async () => {
    const step = window.innerHeight * 0.8
    for (let y = 0; y < document.body.scrollHeight; y += step) {
      window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 30))
    }
    window.scrollTo(0, 0)
  })
  await page.waitForTimeout(4000)

  const r = await page.evaluate(() => {
    const f = document.querySelector('iframe')
    const box = f.getBoundingClientRect()
    return {
      left: Math.round(box.left), width: Math.round(box.width), height: Math.round(box.height),
      // scrollHeight 는 틀 높이만큼 따라 커진다 — 그걸로 재면 「틀=내용」이라는
      // 당연한 답만 나와서 **너무 크게 잡은 것을 못 잡는다.**
      // 마지막 칸이 실제로 어디서 끝나는지를 잰다.
      inner: Math.round(Math.max(...Array.from(f.contentDocument.body.children)
        .map((el) => el.offsetTop + el.offsetHeight))),
      vw: document.documentElement.clientWidth,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    }
  })
  const gapL = r.left
  const gapR = r.vw - r.left - r.width
  const spare = r.height - r.inner   // 음수면 **잘린 것**이다

  if (spare < 0) failures.push(`${name} — 아래가 ${-spare}px 잘립니다`)
  if (spare > 60) failures.push(`${name} — 아래에 ${spare}px 빈 자리가 남습니다`)
  if (Math.abs(gapL - gapR) > 2) failures.push(`${name} — 가운데가 아닙니다 (${gapL}/${gapR})`)
  if (r.overflow > 1) failures.push(`${name} — 가로로 ${r.overflow}px 넘칩니다`)

  console.log(`${name} ${r.vw}px  폭 ${r.width}  여백 ${gapL}/${gapR}  높이 ${r.height}(내용 ${r.inner})  남는 ${spare}px`)
  await ctx.close()
}

await browser.close()
stop()

if (failures.length) {
  console.error(`\n고칠 것 ${failures.length}가지`)
  for (const f of failures) console.error(`  · ${f}`)
  process.exit(1)
}
console.log('\n스크립트 없는 상품 페이지에서도 4가지 크기 모두 통과')
