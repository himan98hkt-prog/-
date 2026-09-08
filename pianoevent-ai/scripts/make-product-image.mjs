/**
 * 상품 카드에 걸 **460×460 상품 이미지**를 만든다.
 *
 *   npm run product:image     →  배포/상품이미지/*.png
 *
 * 460px 짜리는 목록에서 250px 안팎으로 줄어 보인다. 그래서 규칙은 하나다 —
 * **줄여도 읽히는 것만 넣는다.** 작은 글씨를 여러 줄 넣느니 큰 것 넷이 낫다.
 *
 * 세 배 크기로 찍고 460 으로 줄인다(계단이 지지 않게).
 */
import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { chromium } from 'playwright'

const OUT = join('배포', '상품이미지')
const SCALE = 3
const SIZE = 460

const b64 = (f) => {
  const ext = f.endsWith('.png') ? 'png' : 'jpeg'
  return `data:image/${ext};base64,${readFileSync(join('detail', 'assets', f)).toString('base64')}`
}

const IMG = {
  logo: b64('logo-gold.png'),
  po1: b64('po-real-stage.jpg'),
  po2: b64('po-deco.jpg'),
  po3: b64('po-oil.jpg'),
  po4: b64('po-engraving.jpg'),
  po5: b64('po-ink.jpg'),
  cover: b64('doc-cover.jpg'),
  kids: b64('po-kids.jpg'),
}

const BASE = `
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:${SIZE}px;height:${SIZE}px}
  body{font-family:'Noto Sans KR',sans-serif;-webkit-font-smoothing:antialiased;
    color:#2B2620;overflow:hidden;position:relative}
  .serif{font-family:'Noto Serif KR',serif;font-weight:900}
  .card{position:absolute;inset:0;display:flex;flex-direction:column}
`

/* ── 갑 · 숫자로 설명한다 ─────────────────────────────────────── */
const A = `
<style>${BASE}
  body{background:#F2E9D8}
  .card{padding:26px 26px 0}
  .rule{width:44px;height:3px;background:#A07C2C;margin:0 auto 12px}
  .eyebrow{text-align:center;font-size:15px;font-weight:700;color:#A07C2C;letter-spacing:.18em;margin-bottom:10px}
  h1{text-align:center;font-size:52px;line-height:1.1;color:#8B1E2E;letter-spacing:-.02em}
  .sub{text-align:center;font-size:18px;font-weight:700;color:#5A544B;margin-top:10px;letter-spacing:-.01em}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:20px}
  .t{background:#fff;border:1px solid rgba(160,124,44,.28);border-radius:14px;
    padding:13px 8px 12px;text-align:center}
  .t b{display:block;font-family:'Noto Serif KR',serif;font-weight:900;
    font-size:34px;line-height:1;color:#1E2A56;white-space:nowrap}
  .t b em{font-style:normal;font-size:20px;margin-left:1px}
  .t span{display:block;font-size:14px;font-weight:700;color:#5A544B;margin-top:6px}
  .band{margin:auto -26px 0;background:#1E2A56;color:#F2E9D8;text-align:center;
    padding:15px 10px;font-size:17px;font-weight:700;letter-spacing:-.01em}
  .band em{font-style:normal;color:#D9B95C}
</style>
<div class="card">
  <div class="rule"></div>
  <div class="eyebrow">아 첼 쌤</div>
  <h1 class="serif">연주회 매니저</h1>
  <div class="sub">피아노학원 연주회 준비 프로그램</div>
  <div class="grid">
    <div class="t"><b>83<em>종</em></b><span>포스터 · 순서지 · 상장</span></div>
    <div class="t"><b>108<em>종</em></b><span>테마 · 한 번에 통일</span></div>
    <div class="t"><b>3<em>분</em></b><span>명단 → 순서표</span></div>
    <div class="t"><b>무제한</b><span>연주회 몇 번이든</span></div>
  </div>
  <div class="band">윈도우 · 맥 설치형 &nbsp;|&nbsp; <em>인터넷 없이 작동</em></div>
</div>`

/* ── 을 · 나오는 것을 보여 준다 ──────────────────────────────── */
const B = `
<style>${BASE}
  body{background:#141118}
  .top{height:236px;position:relative;overflow:hidden;background:#0E0C11}
  .top img{position:absolute;top:52%;width:124px;border-radius:3px;
    box-shadow:0 10px 22px rgba(0,0,0,.55)}
  .p1{left:-6px;transform:translateY(-50%) rotate(-8deg)}
  .p2{left:124px;transform:translateY(-50%) rotate(-2deg);z-index:3;width:142px !important}
  .p3{left:288px;transform:translateY(-50%) rotate(7deg)}
  .veil{position:absolute;inset:0;background:linear-gradient(180deg,rgba(20,17,24,0) 52%,#141118 97%)}
  .bot{flex:1;background:#141118;padding:4px 26px 22px;text-align:center;position:relative}
  .eyebrow{font-size:14px;font-weight:700;color:#C8A24A;letter-spacing:.2em}
  h1{font-size:48px;line-height:1.1;color:#F4EDE0;margin-top:6px;letter-spacing:-.02em}
  .sub{font-size:17px;font-weight:700;color:#B6AC9A;margin-top:9px;letter-spacing:-.01em}
  .row{display:flex;justify-content:center;gap:8px;margin-top:16px}
  .chip{background:rgba(200,162,74,.13);border:1px solid rgba(200,162,74,.45);
    border-radius:99px;padding:8px 13px;font-size:15px;font-weight:700;color:#EBDCB6}
  .foot{margin-top:14px;font-size:14px;font-weight:700;color:#8E8676}
</style>
<div class="card">
  <div class="top">
    <img class="p1" src="${IMG.po2}"><img class="p3" src="${IMG.po4}">
    <img class="p2" src="${IMG.po1}">
    <div class="veil"></div>
  </div>
  <div class="bot">
    <div class="eyebrow">아 첼 쌤</div>
    <h1 class="serif">연주회 매니저</h1>
    <div class="sub">명단만 넣으면 연주회 인쇄물이 한 벌로</div>
    <div class="row"><span class="chip">인쇄물 83종</span><span class="chip">테마 108종</span><span class="chip">3분</span></div>
    <div class="foot">윈도우 · 맥 설치형 · 인터넷 없이 작동</div>
  </div>
</div>`

/* ── 병 · 반반 (제목·결과물·숫자) ────────────────────────────── */
const C = `
<style>${BASE}
  body{background:#F2E9D8}
  .head{padding:24px 26px 0;text-align:center}
  .eyebrow{font-size:14px;font-weight:700;color:#A07C2C;letter-spacing:.2em}
  h1{font-size:47px;line-height:1.08;color:#8B1E2E;margin-top:5px;letter-spacing:-.02em}
  .sub{font-size:16.5px;font-weight:700;color:#5A544B;margin-top:8px;letter-spacing:-.015em}
  .strip{display:flex;justify-content:center;gap:7px;margin:15px 0 0;padding:0 20px}
  .strip img{width:78px;height:110px;object-fit:cover;border-radius:4px;
    box-shadow:0 5px 13px rgba(83,62,38,.26)}
  .cap{text-align:center;font-size:13px;font-weight:700;color:#A07C2C;margin-top:9px;letter-spacing:-.01em}
  .grid{display:flex;gap:7px;margin:13px 22px 0}
  .t{flex:1;background:#fff;border:1px solid rgba(160,124,44,.26);border-radius:12px;
    padding:10px 4px 9px;text-align:center}
  .t b{display:block;font-family:'Noto Serif KR',serif;font-weight:900;font-size:27px;
    line-height:1;color:#1E2A56}
  .t b em{font-style:normal;font-size:16px}
  .t span{display:block;font-size:12.5px;font-weight:700;color:#5A544B;margin-top:5px}
  .band{margin-top:auto;background:#1E2A56;color:#F2E9D8;text-align:center;
    padding:13px 10px;font-size:16px;font-weight:700;letter-spacing:-.01em}
  .band em{font-style:normal;color:#D9B95C}
</style>
<div class="card">
  <div class="head">
    <div class="eyebrow">아 첼 쌤</div>
    <h1 class="serif">연주회 매니저</h1>
    <div class="sub">피아노학원 연주회 준비 프로그램</div>
  </div>
  <div class="strip">
    <img src="${IMG.po2}"><img src="${IMG.po1}"><img src="${IMG.po5}">
    <img src="${IMG.po4}"><img src="${IMG.kids}">
  </div>
  <div class="cap">테마 하나를 고르면 83종이 같은 옷을 입습니다</div>
  <div class="grid">
    <div class="t"><b>83<em>종</em></b><span>인쇄물</span></div>
    <div class="t"><b>108<em>종</em></b><span>테마</span></div>
    <div class="t"><b>3<em>분</em></b><span>명단 → 순서표</span></div>
  </div>
  <div class="band">윈도우 · 맥 설치형 &nbsp;|&nbsp; <em>인터넷 없이 작동</em></div>
</div>`

rmSync(OUT, { recursive: true, force: true })
mkdirSync(OUT, { recursive: true })

const exe = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const browser = await chromium.launch(existsSync(exe) ? { executablePath: exe } : {})
const ctx = await browser.newContext({
  viewport: { width: SIZE, height: SIZE },
  deviceScaleFactor: SCALE,
})

// 한글 글꼴이 없으면 네모(두부)만 찍힌다. 그 그림이 상품 카드에 걸리는 것이
// 가장 나쁘므로, 찍기 전에 글꼴이 **실제로 먹었는지** 재 본다.
{
  const page = await ctx.newPage()
  await page.setContent(`<span id=a style="font:900 100px 'Noto Serif KR',serif">연주회 매니저</span>
    <span id=b style="font:900 100px serif">연주회 매니저</span>`)
  await page.evaluate(() => document.fonts.ready)
  const [wa, wb] = await page.evaluate(() => ['a', 'b'].map(
    (id) => document.getElementById(id).getBoundingClientRect().width))
  if (wa === wb) {
    console.error(`한글 글꼴(Noto Serif KR)이 없습니다 — 글자가 네모로 찍힙니다.

  ~/.fonts 에 NotoSansKR / NotoSerifKR 을 넣고 fc-cache -f 를 돌리세요.`)
    process.exit(1)
  }
  await page.close()
}

for (const [name, html] of [['갑-숫자형', A], ['을-결과물형', B], ['병-혼합형', C]]) {
  const page = await ctx.newPage()
  await page.setContent(html, { waitUntil: 'load' })
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(300)

  const big = join(OUT, `_${name}.png`)
  await page.screenshot({ path: big, type: 'png' })

  // 3배로 찍은 것을 460 으로 줄인다 — 글자 가장자리가 매끈해진다
  const out = join(OUT, `연주회매니저-상품이미지-${name}.png`)
  execFileSync('ffmpeg', ['-y', '-v', 'error', '-i', big,
    '-vf', `scale=${SIZE}:${SIZE}:flags=lanczos`, out])
  rmSync(big)

  // 실제로 460×460 인지 재 본다
  const size = execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0',
    '-show_entries', 'stream=width,height', '-of', 'csv=p=0', out], { encoding: 'utf8' }).trim()
  if (size !== `${SIZE},${SIZE}`) {
    console.error(`${out} 가 ${size} 로 나왔습니다`)
    process.exit(1)
  }
  console.log(`${out}  ${size}`)
  await page.close()
}

await browser.close()
console.log(`\n${OUT} 에 세 가지가 나왔습니다.`)
