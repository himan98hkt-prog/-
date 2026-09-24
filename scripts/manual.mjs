#!/usr/bin/env node
// 사용설명서를 **파일 하나**로 만든다 — dist/manual.html
//
//   node scripts/manual.mjs [--out dist/manual.html] [--shots screenshots]
//
// 왜 한 파일인가: 원장님께 메일로 보내거나 USB 에 담아 드릴 수 있어야 한다.
// 이미지 폴더가 따로 있으면 옮기다 빠지고, 빠지면 그림 없는 설명서가 된다.
// 그래서 스크린샷을 줄여서 문서 안에 넣는다.
//
// 스크린샷은 스크립트로 찍는다 (`npm run shots` · `mr/tools/manual_shots.py`).
// 손으로 찍으면 화면이 바뀌었을 때 설명서만 조용히 낡는다.

import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { META, PARTS } from './manual-content.js'
import { lintManual } from './manual-lint.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..')

const args = process.argv.slice(2)
const argOf = (name, fallback) => {
  const i = args.indexOf(name)
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback
}
// 파일 이름은 ASCII 로 둔다. 한글 파일명은 FTP·웹호스팅을 거치며 깨지는 일이 있고,
// 그러면 원장님이 여는 주소 자체가 안 열린다. 화면에 보이는 제목은 한글이다.
// 반주는 관리노트와 **따로 파는 제품**이다. `--product mr` 은 관리노트 쪽
// 원고를 빼고 반주만으로 한 권을 만든다 (원고의 `only` 표시를 본다).
const PRODUCT = argOf('--product', 'all')
if (!['all', 'mr', 'note'].includes(PRODUCT)) {
  console.error(`--product 는 all · mr · note 중 하나입니다: ${PRODUCT}`)
  process.exit(2)
}
// 표지 제목도 제품에 맞춰야 한다. 반주만 사신 분이 받는 책에 「학원 관리노트」가
// 적혀 있으면 잘못 온 물건으로 보인다.
const TITLE = {
  all: META.title,
  mr: '피아노 자동 반주 사용설명서',
  note: '학원 관리노트 사용설명서',
}[PRODUCT]
const OUT = resolve(ROOT, argOf('--out', 'dist/manual.html'))
const SHOTS = resolve(ROOT, argOf('--shots', 'screenshots'))
const WIDTH = Number(argOf('--width', '900'))
const QUALITY = Number(argOf('--quality', '80'))

// ── 그림 ────────────────────────────────────────────────────────────
const missing = []

/** 스크린샷을 줄여 data URI 로. 파이썬 PIL 을 쓴다 (이미지 라이브러리를 새로 넣지 않으려고). */
function imageData(name) {
  const src = join(SHOTS, `${name}.png`)
  if (!existsSync(src)) {
    missing.push(name)
    return null
  }
  const b64 = execFileSync('python3', ['-c', `
import base64, io, sys
from PIL import Image
im = Image.open(sys.argv[1]).convert('RGB')
w = min(${WIDTH}, im.width)
im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
buf = io.BytesIO()
im.save(buf, 'JPEG', quality=${QUALITY}, optimize=True)
sys.stdout.write(base64.b64encode(buf.getvalue()).decode())
`, src], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })
  return `data:image/jpeg;base64,${b64}`
}

// ── 글자 ────────────────────────────────────────────────────────────
const esc = (s) => String(s ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;')
  .replace(/>/g, '&gt;').replace(/"/g, '&quot;')

/** `**굵게**` 와 `` `코드` `` 만 지원한다. 원고에서 쓰는 건 이 둘뿐이다. */
function rich(s) {
  return esc(s)
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
}

// ── 조립 ────────────────────────────────────────────────────────────
function sectionHtml(sec, num) {
  const parts = [`<section id="s-${esc(sec.id)}">`,
    `<h3><span class="num">${esc(num)}</span> ${rich(sec.title)}</h3>`]
  if (sec.shot) {
    const data = imageData(sec.shot)
    if (data) {
      // `loading="lazy"` 를 붙이지 않는다. 그림이 문서 안에 이미 들어 있어서
      // 미룰 통신이 없고, 미루면 **종이로 뽑을 때 아래쪽 그림이 빈칸으로 나온다.**
      // 이 설명서는 원장님이 인쇄해서 두고 보시라고 만든 것이다.
      parts.push(`<figure><img src="${data}" alt="${esc(sec.title)} 화면">`,
        `<figcaption>${esc(sec.title)}</figcaption></figure>`)
    }
  }
  for (const line of sec.body || []) parts.push(`<p>${rich(line)}</p>`)
  if (sec.table) {
    parts.push('<table><thead><tr>',
      sec.table.head.map((h) => `<th>${rich(h)}</th>`).join(''),
      '</tr></thead><tbody>',
      sec.table.rows.map((r) =>
        `<tr>${r.map((c) => `<td>${rich(c)}</td>`).join('')}</tr>`).join(''),
      '</tbody></table>')
  }
  // 표 **뒤에** 오는 본문. 표가 목록이고 그 뒤에 「그래서 어떻게 하시라」가
  // 붙는 절에 쓴다 (13-6 악보 구하기). body 에 넣으면 표 앞으로 올라간다.
  for (const line of sec.body2 || []) parts.push(`<p>${rich(line)}</p>`)
  if (sec.trap) {
    parts.push(`<div class="trap"><b>자주 하는 실수</b><p>${rich(sec.trap)}</p></div>`)
  }
  parts.push('</section>')
  return parts.join('\n')
}

/** `only` 표시를 보고 이 제품의 원고만 남긴다.
 *
 * 절이 전부 빠진 장과, 장이 전부 빠진 부는 같이 사라진다 — 빈 제목만 남으면
 * 목차에 빈 칸이 생긴다. 부 번호는 남은 순서대로 다시 매긴다.
 */
function forProduct(parts, product) {
  if (product === 'all') return parts
  const keep = (x) => !x.only || x.only === product
  const out = []
  for (const part of parts) {
    if (!keep(part)) continue
    const chapters = []
    for (const ch of part.chapters || []) {
      if (!keep(ch)) continue
      const sections = (ch.sections || []).filter(keep)
      if (sections.length) chapters.push({ ...ch, sections })
    }
    if (chapters.length) out.push({ ...part, chapters })
  }
  return out.map((part, i) => ({
    ...part, title: part.title.replace(/^\d+부/, `${i + 1}부`),
  }))
}

const CHOSEN = forProduct(PARTS, PRODUCT)
if (!CHOSEN.length) {
  console.error(`--product ${PRODUCT} 로 남는 원고가 없습니다`)
  process.exit(2)
}

const toc = []
const bodyParts = []

for (const part of CHOSEN) {
  toc.push(`<li class="toc-part"><a href="#${esc(part.id)}">${rich(part.title)}</a><ul>`)
  bodyParts.push(`<div class="part" id="${esc(part.id)}">`,
    `<h1>${rich(part.title)}</h1>`)
  if (part.lead) bodyParts.push(`<p class="lead">${rich(part.lead)}</p>`)

  for (const [ci, ch] of part.chapters.entries()) {
    const chNum = ch.id.replace(/^ch/, '')
    toc.push(`<li><a href="#${esc(ch.id)}">${esc(chNum)}. ${rich(ch.title)}</a></li>`)
    bodyParts.push(`<h2 id="${esc(ch.id)}">`,
      `<span class="num">${esc(chNum)}</span> ${rich(ch.title)}</h2>`)
    for (const [si, sec] of ch.sections.entries()) {
      bodyParts.push(sectionHtml(sec, `${chNum}.${si + 1}`))
    }
    void ci
  }
  toc.push('</ul></li>')
  bodyParts.push('</div>')
}

const CSS = `
:root{
  --paper:#fbfaf7; --ink:#23211d; --muted:#6b6459; --line:#e3ddd2;
  --accent:#7a5c3e; --accent-soft:#f3ece1;
  --warn-bg:#fff8e4; --warn-line:#e8b93c; --warn-ink:#7a5a0c;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",
    "Noto Sans KR",sans-serif;
  font-size:16px; line-height:1.75; word-break:keep-all;
}
.wrap{display:grid; grid-template-columns:260px minmax(0,1fr); gap:0; max-width:1180px; margin:0 auto}
nav{
  position:sticky; top:0; align-self:start; max-height:100vh; overflow:auto;
  padding:26px 18px 40px; border-right:1px solid var(--line); font-size:14px;
}
nav h2{font-size:15px; margin:0 0 4px}
nav .sub{color:var(--muted); font-size:12px; margin-bottom:16px}
nav ul{list-style:none; margin:0; padding:0}
nav ul ul{margin:2px 0 12px 10px}
nav a{display:block; padding:3px 6px; border-radius:6px; color:inherit; text-decoration:none}
nav a:hover{background:var(--accent-soft)}
nav .toc-part>a{font-weight:700; margin-top:10px; color:var(--accent)}
main{padding:26px 34px 90px; min-width:0}
header.cover{border-bottom:2px solid var(--accent); padding-bottom:18px; margin-bottom:26px}
header.cover h1{font-size:27px; margin:0 0 4px}
header.cover .sub{color:var(--muted)}
.part{margin-top:56px}
.part:first-of-type{margin-top:0}
h1{font-size:24px; margin:0 0 6px; padding-bottom:8px; border-bottom:2px solid var(--accent)}
h2{font-size:19px; margin:38px 0 6px; display:flex; gap:9px; align-items:baseline}
h3{font-size:16px; margin:26px 0 6px; display:flex; gap:9px; align-items:baseline}
.num{
  font-size:12px; color:var(--accent); background:var(--accent-soft);
  border-radius:5px; padding:1px 7px; font-weight:700; white-space:nowrap;
}
.lead{color:var(--muted); margin:0 0 6px}
p{margin:7px 0}
code{
  background:#f0ece4; border:1px solid var(--line); border-radius:4px;
  padding:1px 5px; font-size:13px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
}
figure{margin:14px 0 6px}
figure img{
  width:100%; max-width:720px; display:block; border:1px solid var(--line);
  border-radius:8px; background:#fff;
}
figcaption{color:var(--muted); font-size:12px; margin-top:5px}
table{border-collapse:collapse; margin:12px 0; width:100%; max-width:720px; background:#fff}
th,td{border:1px solid var(--line); padding:7px 11px; text-align:left; font-size:14px}
th{background:var(--accent-soft); font-weight:700}
.trap{
  background:var(--warn-bg); border:1px solid var(--warn-line); border-left-width:4px;
  border-radius:8px; padding:11px 15px; margin:14px 0;
}
.trap>b{color:var(--warn-ink); font-size:13px}
.trap p{margin:3px 0 0}
footer{margin-top:70px; padding-top:18px; border-top:1px solid var(--line);
  color:var(--muted); font-size:13px}

@media (max-width:820px){
  .wrap{grid-template-columns:1fr}
  nav{position:static; max-height:none; border-right:0; border-bottom:1px solid var(--line)}
  main{padding:20px 18px 70px}
}

/* 인쇄 — A4. 원장님이 종이로 두고 보실 수 있게. */
@media print{
  @page{size:A4; margin:16mm 14mm}
  body{background:#fff; font-size:10.5pt; line-height:1.6}
  .wrap{display:block; max-width:none}
  nav{display:none}
  main{padding:0}
  .part{margin-top:0; break-before:page}
  .part:first-of-type{break-before:auto}
  h2{break-before:page; break-after:avoid}
  .part>h1+.lead+h2{break-before:auto}
  h3{break-after:avoid}
  section, figure, table, .trap{break-inside:avoid}
  figure img{max-width:430px; border-color:#ccc}
  a{text-decoration:none; color:inherit}
}
`

const html = `<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(TITLE)}</title>
<style>${CSS}</style>
</head>
<body>
<div class="wrap">
<nav>
  <h2>${esc(TITLE)}</h2>
  <div class="sub">${esc(META.version)} · 찾으실 때는 Ctrl+F</div>
  <ul>${toc.join('\n')}</ul>
</nav>
<main>
  <header class="cover">
    <h1>${esc(TITLE)}</h1>
    <div class="sub">${esc(META.subtitle)} · ${esc(META.version)}</div>
  </header>
  ${bodyParts.join('\n')}
  <footer>
    이 설명서는 화면이 바뀔 때마다 다시 만들어집니다 (<code>npm run manual</code>).
    그림은 실제 화면을 그대로 찍은 것입니다.
  </footer>
</main>
</div>
</body>
</html>
`

let sections = 0
let figures = 0
// **`CHOSEN` 을 센다.** `PARTS` 를 세면 반주만 뽑을 때 그림 수가 안 맞아
// 린터가 멀쩡한 책을 거부한다 — 실제로 그렇게 걸렸다.
for (const p of CHOSEN) for (const c of p.chapters) for (const s of c.sections) {
  sections++
  if (s.shot) figures++
}

const problems = lintManual(html, { figures: figures - missing.length })
if (missing.length) {
  problems.unshift(`스크린샷이 없습니다 (${missing.length}장): ${missing.join(', ')}\n` +
    '    npm run manual:shots  로 먼저 찍으세요')
}
// 반쪽짜리 설명서를 파일로 남기지 않는다. 남겨 두면 그게 배포된다.
if (problems.length) {
  console.error('설명서를 내보내지 않았습니다 — 먼저 고쳐야 합니다:')
  for (const line of problems) console.error(`  · ${line}`)
  process.exit(1)
}

mkdirSync(dirname(OUT), { recursive: true })
writeFileSync(OUT, html, 'utf8')

const kb = statSync(OUT).size / 1024
console.log(`${OUT}`)
console.log(`  ${CHOSEN.length}부 · ${sections}절 · 그림 ${figures}장 · ${kb.toFixed(0)} KB`
  + (PRODUCT === 'all' ? '' : `  (${PRODUCT} 전용판)`))
