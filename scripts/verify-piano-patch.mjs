#!/usr/bin/env node
// 피아노 관리노트 앱에 패치를 붙이고, 학원 관리노트 키가 실제로 열리는지 브라우저로 확인한다.
//
//   node scripts/verify-piano-patch.mjs <피아노앱 index.html 경로> [출력 경로]
//
// 하는 일
//   1) 원본을 열어 '지금은 학원 키가 거부되는지' 확인
//   2) </body> 앞에 패치를 붙인 파일을 만들고
//   3) 다시 열어 통합키·피아노 전용키는 통과, 학원 전용키·엉터리는 거부되는지 확인
//   4) 마지막으로 인증 화면에 키를 직접 넣어 잠금이 풀리는지까지 확인
//
// 피아노 앱이 새 버전으로 바뀌면 이 스크립트만 다시 돌리면 된다.

import { chromium } from 'playwright'
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { readdirSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const APP = process.argv[2]
const OUT = process.argv[3] || '/tmp/piano-note-patched.html'
if (!APP) {
  console.error('사용법: node scripts/verify-piano-patch.mjs <피아노앱 index.html> [출력 경로]')
  process.exit(2)
}

// 패치를 </body> 앞에 붙인다. 주석 안의 닫는 태그 때문에 HTML 파싱이 끊기지 않도록 이스케이프한다.
const patch = readFileSync('integration/piano/학원관리노트-키-인정-패치.js', 'utf8').replaceAll('</script', '<\\/script')
const original = readFileSync(resolve(APP), 'utf8')
if (!original.includes('</body>')) { console.error('</body> 를 찾지 못했습니다'); process.exit(2) }
writeFileSync(OUT, original.replace('</body>', `<script>\n${patch}\n</script>\n</body>`))
console.log(`패치본 생성: ${OUT}`)
function chromeExecutable() {
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH
  if (!base || !existsSync(base)) return null
  const d = join(base, 'chromium'); if (existsSync(d)) return d
  for (const x of readdirSync(base)) { const p = join(base, x, 'chrome-linux', 'chrome'); if (existsSync(p)) return p }
  return null
}
const b = await chromium.launch(chromeExecutable() ? { executablePath: chromeExecutable() } : {})

async function probe(file, label) {
  const page = await b.newPage()
  const errs = []
  page.on('pageerror', e => errs.push(e.message))
  await page.goto('file://' + file)
  await page.waitForTimeout(1500)
  const r = await page.evaluate(() => {
    const has = (n) => typeof window[n] === 'function'
    const test = (k) => { try { return !!window.licSelfValid?.(k) } catch { return 'ERR' } }
    return {
      hasSelf: has('licSelfValid'), hasKey: has('licKey'), hasValid: has('licValid'),
      patched: !!window.anVerifyAcademyNoteKey,
      pianoSelf: test('79AK-3MCU-ADYC'),
      anAll: test('AL2H-4K7P-KGMK'),
      anPro: test('AP9R-3TQX-71C3'),
      anPiano: test('KL5M-8VNC-41GX'),
      anAcademyOnly: test('ML6Q-2WJD-7PG7'),
      junk: test('ABCD-EFGH-JKMN'),
      nameKey: (() => { try { return window.licKey?.('아첼음악학원') } catch { return 'ERR' } })(),
      licValidWithName: (() => { try { return !!window.licValid?.('아무학원', 'AL2H-4K7P-KGMK') } catch { return 'ERR' } })(),
      activateVisible: !!document.querySelector('#lic-go')
    }
  })
  console.log(`\n[${label}]`, JSON.stringify(r, null, 1))
  if (errs.length) console.log('  page errors:', errs.slice(0, 3))
  await page.close()
  return r
}

const before = await probe(resolve(APP), '원본')
const after = await probe(resolve(OUT), '패치본')

// 패치본에서 실제 인증 화면에 키를 넣어 잠금이 풀리는지
const page = await b.newPage()
page.on('pageerror', e => console.log('PAGEERROR', e.message))
await page.goto('file://' + resolve(OUT))
await page.waitForSelector('#lic-go', { timeout: 15000 })
await page.fill('#lic-name', '테스트 학원')
await page.fill('#lic-key', 'AP9R-3TQX-71C3')
await page.click('#lic-go')
await page.waitForTimeout(1200)
const unlocked = await page.evaluate(() => ({
  stillLocked: !!document.querySelector('#lic-go'),
  toast: document.querySelector('.toast, #toast')?.textContent?.trim() || '',
  bodyClass: document.body.className,
  tabs: !!document.querySelector('.tabbar')
}))
console.log('\n[인증 시도 결과]', JSON.stringify(unlocked, null, 1))
await b.close()

const checks = [
  ['원본은 학원 통합키를 거부한다', before.anAll === false],
  ['패치 후 통합키(A)가 열린다', after.anAll === true && after.anPro === true],
  ['패치 후 피아노 전용키(K)가 열린다', after.anPiano === true],
  ['학원 전용키(M)는 여전히 거부한다', after.anAcademyOnly === false],
  ['엉터리 키는 거부한다', after.junk === false],
  ['기존 피아노 키는 그대로 열린다', after.pianoSelf === true],
  ['학원명 방식 키 계산이 그대로다', after.nameKey === before.nameKey],
  ['인증 화면에서 실제로 잠금이 풀린다', unlocked.stillLocked === false]
]
console.log(`\n─ 검증 결과 ${'─'.repeat(38)}`)
for (const [name, ok] of checks) console.log(`  ${ok ? '✅' : '❌'} ${name}`)
const failed = checks.filter(([, ok]) => !ok)
console.log(failed.length ? `\n  ${failed.length}건 실패\n` : `\n  ${checks.length}건 전부 통과 — 이 패치본을 그대로 배포하시면 됩니다\n`)
process.exit(failed.length ? 1 : 0)
