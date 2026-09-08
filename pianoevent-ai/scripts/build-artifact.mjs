/**
 * Vite 로 만든 단일 HTML 을 아티팩트 게시용 조각으로 바꾼다.
 * 게시할 때 <!doctype>…<head>…<body> 껍데기가 씌워지므로 본문만 남긴다.
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'

const SRC = '배포/demo/index.html'
const OUT = '배포/demo/artifact.html'

const html = readFileSync(SRC, 'utf8')

const pick = (re) => {
  const m = html.match(re)
  if (!m) throw new Error(`찾지 못함: ${re}`)
  return m
}

const title = pick(/<title>([\s\S]*?)<\/title>/)[1]
// <link> 는 여러 줄에 걸쳐 있을 수 있다
const fontLinks = [...html.matchAll(/<link\b[\s\S]*?>/g)].map((m) => m[0].replace(/\s+/g, ' '))
const styles = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1])
const scripts = [...html.matchAll(/<script type="module"[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1])

if (scripts.length === 0) throw new Error('인라인 스크립트가 없습니다 — singlefile 빌드가 맞는지 확인하세요')

const out = [
  `<title>${title}</title>`,
  ...fontLinks,
  ...styles.map((css) => `<style>\n${css}\n</style>`),
  '<div id="root"></div>',
  ...scripts.map((js) => `<script type="module">\n${js}\n</script>`),
].join('\n')

mkdirSync(dirname(OUT), { recursive: true })
writeFileSync(OUT, out)
console.log(`${OUT} · ${Math.round(out.length / 1024)} KB · 제목 "${title}"`)
console.log(`스타일 ${styles.length} · 스크립트 ${scripts.length} · 링크 ${fontLinks.length}`)
if (!out.includes('fonts.googleapis.com/css2')) throw new Error('구글 폰트 스타일시트가 빠졌습니다')
