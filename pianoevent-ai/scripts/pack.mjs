// 배포용 묶음을 만듭니다.
//   node scripts/pack.mjs
// 결과: 배포/피아노이벤트-프로그램.zip
//   ZIP 을 풀면 맨 위에 "시작하기.bat" 이 보이도록 구성합니다.
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const APP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const OUT = path.join(APP, '배포')
const STAGE = path.join(APP, '.pack')
const BUNDLE = '피아노이벤트-프로그램'
const ZIP = path.join(OUT, `${BUNDLE}.zip`)

// 소스에서 제외할 것 — 용량과 개인정보를 부풀리는 것들
const SKIP = new Set([
  'node_modules', '.next', '.git', '.data', '.pack', '배포',
  '.env', '.env.local', 'test-results', 'playwright-report',
  'promo', 'detail', 'shots', 'screenshots', 'tsconfig.tsbuildinfo',
])

function copy(src, dst) {
  const st = fs.statSync(src)
  if (st.isDirectory()) {
    fs.mkdirSync(dst, { recursive: true })
    for (const name of fs.readdirSync(src)) {
      if (SKIP.has(name)) continue
      copy(path.join(src, name), path.join(dst, name))
    }
    return
  }
  fs.copyFileSync(src, dst)
}

fs.rmSync(STAGE, { recursive: true, force: true })
const root = path.join(STAGE, BUNDLE)
fs.mkdirSync(root, { recursive: true })

// 1) 프로그램 소스
copy(APP, path.join(root, 'pianoevent-ai'))

// 2) 실행기를 맨 위로 — 두 번 클릭할 파일이 제일 먼저 보여야 합니다
for (const name of fs.readdirSync(path.join(APP, 'launcher'))) {
  const dst = path.join(root, name)
  fs.copyFileSync(path.join(APP, 'launcher', name), dst)
  if (name.endsWith('.command')) fs.chmodSync(dst, 0o755)
}

// 3) 안내문과 설치 없이 보는 미리보기
const readme = path.join(APP, 'launcher', '먼저-읽어주세요.txt')
if (fs.existsSync(readme)) fs.copyFileSync(readme, path.join(root, '먼저-읽어주세요.txt'))
const preview = path.join(OUT, '피아노이벤트-미리보기.html')
if (fs.existsSync(preview)) fs.copyFileSync(preview, path.join(root, '피아노이벤트-미리보기.html'))

// 4) 압축
fs.mkdirSync(OUT, { recursive: true })
fs.rmSync(ZIP, { force: true })
const r = spawnSync('zip', ['-r', '-q', ZIP, BUNDLE], { cwd: STAGE, stdio: 'inherit' })
if (r.status !== 0) {
  console.error('zip 명령이 실패했습니다.')
  process.exit(1)
}
fs.rmSync(STAGE, { recursive: true, force: true })

const kb = Math.round(fs.statSync(ZIP).size / 1024)
console.log(`묶음 완료 · ${path.relative(APP, ZIP)} · ${kb} KB`)
