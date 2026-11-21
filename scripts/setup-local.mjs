#!/usr/bin/env node
// 학원 관리노트 — 내 PC(윈도우·맥·리눅스)에서 개발을 시작할 준비를 한 번에 한다.
//
//   npm run setup            준비물 확인 → 패키지 설치 → 테스트 → 빌드 → 다음 할 일 안내
//   npm run setup -- --fast  패키지가 이미 깔려 있으면 설치를 건너뛴다
//
// 이 스크립트는 Node 기본 기능만 쓴다(패키지를 설치하기 전에도 돌아야 하므로).

import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = join(fileURLToPath(new URL('.', import.meta.url)), '..')
process.chdir(ROOT)

const args = process.argv.slice(2)
const FAST = args.includes('--fast')
const WIN = process.platform === 'win32'

const color = (code) => (s) => (process.stdout.isTTY ? `\x1b[${code}m${s}\x1b[0m` : s)
const green = color(32)
const yellow = color(33)
const red = color(31)
const bold = color(1)

const ok = (s) => console.log(`  ${green('[OK]')}  ${s}`)
const warn = (s) => console.log(`  ${yellow('[!!]')}  ${s}`)
const bad = (s) => console.log(`  ${red('[XX]')}  ${s}`)
const step = (s) => console.log(`\n${bold(`== ${s} ==`)}`)

/** 명령을 실행하고 출력을 그대로 보여 준다. 윈도우의 npm.cmd 도 돌도록 셸을 거친다. */
function run(command) {
  const res = spawnSync(command, { stdio: 'inherit', shell: true })
  return res.status === 0
}

/** 명령의 출력만 받는다 (없으면 null) */
function capture(command) {
  const res = spawnSync(command, { encoding: 'utf8', shell: true })
  return res.status === 0 ? String(res.stdout || '').trim() : null
}

// ── 1. 준비물 ──────────────────────────────────────────────
step('1. 준비물 확인')
let ready = true

const [major] = process.versions.node.split('.').map(Number)
if (major >= 20) ok(`Node ${process.versions.node}${major === 22 ? '' : '  (22 LTS 를 권장합니다)'}`)
else { bad(`Node ${process.versions.node} — 20 이상이 필요합니다 → https://nodejs.org (22 LTS)`); ready = false }

const npmVersion = capture('npm -v')
if (npmVersion) ok(`npm ${npmVersion}`)
else { bad('npm 을 찾지 못했습니다 — Node.js 를 다시 설치해 주세요'); ready = false }

const gitVersion = capture('git --version')
if (gitVersion) ok(gitVersion)
else warn('Git 이 없습니다 — 코드를 받거나 올릴 때 필요합니다 → https://git-scm.com')

if (!ready) {
  console.log()
  bad('위 준비물을 설치하고 PowerShell(터미널)을 새로 연 뒤 다시 실행해 주세요')
  process.exit(1)
}

// 작업 브랜치 — 앱 코드가 아직 기본 브랜치에 합쳐지지 않았을 수 있다
if (gitVersion) {
  const branch = capture('git rev-parse --abbrev-ref HEAD')
  if (branch) ok(`지금 브랜치: ${branch}`)
  const dirty = capture('git status --porcelain')
  if (dirty) warn('아직 저장(commit)하지 않은 변경이 있습니다 — 그대로 두고 진행합니다')
}

// 경로에 흔히 문제가 되는 위치
const cwd = process.cwd()
if (/onedrive/i.test(cwd)) {
  warn('OneDrive 로 동기화되는 폴더 안에 있습니다. 설치 파일 수만 개가 계속 동기화돼 느리거나 잠길 수 있습니다.')
  warn('C:\\dev 처럼 OneDrive 밖의 폴더로 옮기는 것을 권합니다 (docs/LOCAL-DEV.md 2장)')
}

// ── 2. 패키지 설치 ─────────────────────────────────────────
step('2. 패키지 설치')
const installed = existsSync(join('node_modules', '.package-lock.json'))
const lockChanged = installed &&
  statSync('package-lock.json').mtimeMs > statSync(join('node_modules', '.package-lock.json')).mtimeMs
if (FAST && installed && !lockChanged) {
  ok('이미 설치되어 있어 건너뜁니다 (--fast)')
} else {
  console.log('  처음에는 1~3분 걸립니다…')
  if (!run('npm ci')) {
    bad('패키지를 설치하지 못했습니다. 위 오류 메시지를 확인해 주세요.')
    console.log('  자주 있는 원인: 인터넷 연결, 회사·학교 방화벽, 백신이 node_modules 를 잠금')
    process.exit(1)
  }
  ok('패키지 설치 완료')
}

// ── 3. 있으면 좋은 것 ──────────────────────────────────────
step('3. 있으면 좋은 것 (없어도 개발은 됩니다)')

// 브라우저 검사(npm run smoke · perf · shots)용 브라우저
const browser = findBrowser()
if (browser) ok(`브라우저 검사용 브라우저: ${browser}`)
else warn('브라우저 검사(npm run smoke)용 브라우저가 없습니다 → npx playwright install chromium')

// 퍼널모아 플러그인 점검(PHP)
const php = capture('php -r "echo PHP_VERSION;"')
if (php) {
  const sqlite = spawnSync('php -r "exit(class_exists(\'SQLite3\') ? 0 : 1);"', { shell: true }).status === 0
  if (sqlite) ok(`PHP ${php} — 플러그인 점검(npm run test:plugin)도 돌아갑니다`)
  else warn(`PHP ${php} 는 있지만 sqlite3 확장이 꺼져 있습니다 — php.ini 에서 extension=sqlite3 를 켜면 플러그인 점검이 돕니다`)
} else {
  warn('PHP 없음 — 퍼널모아 플러그인 점검은 건너뜁니다 (GitHub 에 올리면 자동 점검에서 돕니다)')
}

// Pro(Supabase) 설정
if (existsSync('.env')) ok('.env 있음 (Pro 동기화 설정)')
else console.log('  [--]  .env 없음 — Lite 개발에는 필요 없습니다. Pro 를 시험할 때만 .env.example 을 복사해 채웁니다')

// ── 4. 자동 테스트 ─────────────────────────────────────────
step('4. 자동 테스트')
if (!run('npm test')) {
  bad('테스트가 실패했습니다. 위에서 ✗ 표시된 항목을 확인해 주세요.')
  process.exit(1)
}
ok('테스트 통과')

// ── 5. 빌드 ────────────────────────────────────────────────
step('5. 배포용 빌드')
if (!run('npm run build')) {
  bad('빌드가 실패했습니다. 위 오류 메시지를 확인해 주세요.')
  process.exit(1)
}
ok('dist/ 에 배포용 파일이 만들어졌습니다')

// ── 끝 ─────────────────────────────────────────────────────
step('준비 끝! 다음 할 일')
const lines = [
  ['개발 서버 열기 (저장하면 바로 반영)', 'npm start'],
  ['올리기 전 점검 (테스트 + 빌드)', 'npm run check'],
  ['실제 브라우저로 전체 흐름 검사', 'npm run smoke'],
  ['화면 캡처 다시 찍기', 'npm run shots -- piano'],
  ['파일 하나짜리 체험판 만들기', 'npm run demo'],
  ['퍼널모아 플러그인 zip 만들기', 'npm run plugin'],
  ['자세한 안내', 'docs/LOCAL-DEV.md']
]
// 명령(영문)을 앞에 둬야 한글 폭 때문에 줄이 어긋나지 않는다
const width = Math.max(...lines.map(([, c]) => c.length))
for (const [label, cmd] of lines) console.log(`  ${bold(cmd.padEnd(width + 3, ' '))}${label}`)
console.log()
if (WIN) console.log('  VS Code 에서는 메뉴 "터미널 → 작업 실행" 으로 위 명령을 고를 수 있습니다.\n')

/** 브라우저 검사에 쓸 브라우저 — scripts/lib/browser.mjs 와 같은 순서로 찾는다 (패키지 없이) */
function findBrowser() {
  if (process.env.CHROMIUM_PATH && existsSync(process.env.CHROMIUM_PATH)) return process.env.CHROMIUM_PATH
  // 미리 받아 둔 브라우저 폴더 (CI·클라우드)
  const pre = process.env.PLAYWRIGHT_BROWSERS_PATH
  if (pre && pre !== '0' && existsSync(pre)) {
    const dir = readdirSync(pre).filter((d) => /^chromium-\d+$/.test(d)).sort().pop()
    if (dir) return `미리 받아 둔 크로미움 (${dir})`
  }
  // 플레이라이트가 받아 둔 크로미움
  try {
    const pkg = JSON.parse(readFileSync(join('node_modules', 'playwright-core', 'browsers.json'), 'utf8'))
    const rev = pkg.browsers?.find((b) => b.name === 'chromium')?.revision
    const home = process.env.PLAYWRIGHT_BROWSERS_PATH ||
      (WIN ? join(process.env.LOCALAPPDATA || '', 'ms-playwright')
        : process.platform === 'darwin' ? join(process.env.HOME || '', 'Library', 'Caches', 'ms-playwright')
          : join(process.env.HOME || '', '.cache', 'ms-playwright'))
    if (rev && existsSync(join(home, `chromium-${rev}`))) return `플레이라이트 크로미움 (${rev})`
  } catch { /* 패키지 정보가 없다 */ }
  if (WIN) {
    const edge = ['ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA']
      .map((v) => process.env[v] && join(process.env[v], 'Microsoft', 'Edge', 'Application', 'msedge.exe'))
      .find((p) => p && existsSync(p))
    if (edge) return 'Microsoft Edge'
  }
  if (process.platform === 'darwin' && existsSync('/Applications/Google Chrome.app')) return 'Google Chrome'
  return null
}
