// 배포용 묶음을 만듭니다.
//   node scripts/pack.mjs
// 결과: 배포/피아노이벤트-프로그램.zip
//   ZIP 을 풀면 맨 위에 "시작하기.bat" 이 보이도록 구성합니다.
import fs from 'node:fs'
import { zipFolder } from './zip-utf8.mjs'
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
  'promo', 'detail', 'shots', 'screenshots', 'carousel', 'tsconfig.tsbuildinfo',
  // 자동 저장 폴더에는 아이 이름과 사진이 들어 있다. 묶음에 딸려 나가면 안 된다.
  '백업',
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

// 4) 연습용 엑셀 — 처음 켜시면 "그래서 뭘 올려요?" 에서 멈추신다.
//    끌어다 놓아 보실 파일이 손에 있어야 한다.
const samples = path.join(root, '연습용-명단')
fs.mkdirSync(samples, { recursive: true })
for (const name of ['학생명단-예시.xlsx', '학생명단-학년별-예시.xlsx']) {
  const src = path.join(OUT, name)
  if (fs.existsSync(src)) fs.copyFileSync(src, path.join(samples, name))
}

// 4-2) 연습용 사진 — 사진 넣기를 한 번 해 보셔야 무대 화면·감동영상이 무엇인지 아신다.
//      학원 아이 사진을 쓰시기 전에 연습부터 하시라고 그린 얼굴 그림을 같이 넣는다.
const faces = path.join(root, '연습용-사진')
const faceSrc = path.join(OUT, '연습용-사진')
if (fs.existsSync(faceSrc)) {
  fs.mkdirSync(faces, { recursive: true })
  for (const name of fs.readdirSync(faceSrc)) {
    fs.copyFileSync(path.join(faceSrc, name), path.join(faces, name))
  }
}

// 5) 압축
fs.mkdirSync(OUT, { recursive: true })
fs.rmSync(ZIP, { force: true })
// 리눅스의 zip 명령은 "이름이 UTF-8 이다" 라는 표시를 켜 주지 않는다.
// 그러면 윈도우에서 한글 이름이 깨지고, 원장님 화면에는 "풀었는데 아무것도 없다" 로 나타난다.
// 이름이 전부 한글인 묶음이라 그 표시 하나가 묶음 전체를 못 쓰게 만든다. 그래서 직접 쓴다.
// STAGE 안에는 묶음 폴더 하나뿐이므로, STAGE 를 묶으면 맨 위가 그 폴더가 된다
const files = await zipFolder(STAGE, ZIP)
fs.rmSync(STAGE, { recursive: true, force: true })

const kb = Math.round(fs.statSync(ZIP).size / 1024)
console.log(`묶음 완료 · ${path.relative(APP, ZIP)} · ${kb} KB · 파일 ${files}개 (이름 UTF-8 표시 켬)`)
