#!/usr/bin/env node
// 단일 HTML 데모 빌드 — 파일 하나로 실행되는 체험판을 만든다.
//
// 정식 배포본(dist/)은 코드 스플리팅으로 빠르게 뜨지만, 파일이 여러 개라
// "메일로 보내서 바로 열어 보기" 가 안 된다. 이 빌드는 그 반대 목적이다:
//   - 동적 import 를 하나로 합치고(inlineDynamicImports)
//   - CSS·JS 를 HTML 안에 인라인해서
//   - 파일 하나만 열면 IndexedDB 로 모든 기능이 도는 체험판을 만든다

import { build } from 'vite'
import { readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs'
import { join } from 'node:path'

const OUT_DIR = 'dist-demo'
const TMP = join(OUT_DIR, '_tmp')

rmSync(OUT_DIR, { recursive: true, force: true })
mkdirSync(OUT_DIR, { recursive: true })

await build({
  base: './',
  logLevel: 'warn',
  build: {
    target: 'es2020',
    outDir: TMP,
    emptyOutDir: true,
    cssCodeSplit: false,
    assetsInlineLimit: 100000000,
    rollupOptions: {
      input: 'lite.html',
      output: { inlineDynamicImports: true, entryFileNames: 'app.js', assetFileNames: 'app.[ext]' }
    }
  }
})

let html = readFileSync(join(TMP, 'lite.html'), 'utf8')
const js = readFileSync(join(TMP, 'app.js'), 'utf8')
let css = ''
try { css = readFileSync(join(TMP, 'app.css'), 'utf8') } catch { /* CSS 가 JS 에 합쳐진 경우 */ }

html = html
  .replace(/<script type="module"[^>]*src="[^"]*"[^>]*><\/script>/, () =>
    `<script type="module">\n${js}\n</script>`)
  .replace(/<link rel="stylesheet"[^>]*href="[^"]*"[^>]*>/, () =>
    css ? `<style>\n${css}\n</style>` : '')

const outFile = join(OUT_DIR, '학원관리노트-체험판.html')
writeFileSync(outFile, html)
rmSync(TMP, { recursive: true, force: true })

const kb = (Buffer.byteLength(html) / 1024).toFixed(0)
console.log(`\n  ✓ ${outFile} (${kb} KB) — 파일 하나로 실행되는 체험판\n`)
