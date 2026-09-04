#!/usr/bin/env node
// Artifact(웹 공유 페이지)용 단일 파일 빌드.
//
// 단일 HTML 체험판과 내용은 같지만, Artifact 는 <html>/<head>/<body> 를 스스로 감싸므로
// 그 태그를 빼고 <title> + <style> + 본문 + <script> 만 남긴다.

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'

const src = readFileSync('dist-demo/학원관리노트-체험판.html', 'utf8')

const style = src.match(/<style>[\s\S]*?<\/style>/)?.[0] || ''
const script = src.match(/<script type="module">[\s\S]*?<\/script>/)?.[0] || ''
if (!script) throw new Error('인라인 스크립트를 찾지 못했습니다. 먼저 npm run demo 를 실행하세요.')

const page = `<title>학원 관리노트</title>
<meta name="theme-color" content="#2563eb" />
${style}
<style>
  /* Artifact 뷰어는 자체 배경을 칠하므로 앱 배경을 명시한다 */
  body { background: var(--bg, #f5f6f8); margin: 0; }
</style>
<div id="app"></div>
${script}
`

mkdirSync('dist-demo', { recursive: true })
writeFileSync('dist-demo/artifact-demo.html', page)
console.log(`  ✓ dist-demo/artifact-demo.html (${(Buffer.byteLength(page) / 1024).toFixed(0)} KB)`)
