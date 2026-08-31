#!/usr/bin/env node
/**
 * accelssam.com 에 올릴 것을 **한 묶음**으로 만든다.
 *
 *   npm run pack:web   →  web/recital-upload.zip
 *
 * 압축 안에 **폴더를 넣지 않는다.** 파일 관리자에서 폴더가 든 압축을 풀면
 * 한 겹 더 들어가거나 아예 안 열리는 일이 있다. `download` 폴더 안에서 그냥 풀면
 * 세 파일이 그 자리에 그대로 나오게 한다.
 *
 * 파일 이름은 전부 영문이다 — 한글 이름은 서버에서 깨지는 일이 있다.
 */
import { execFileSync } from 'node:child_process'
import { cpSync, existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const STAGE = join('배포', 'web-upload')
const OUT = join('web', 'recital-upload.zip')

rmSync(STAGE, { recursive: true, force: true })
mkdirSync(STAGE, { recursive: true })

cpSync(join('web', 'download', 'index.html'), join(STAGE, 'index.html'))
cpSync(join('web', 'download', '.htaccess'), join(STAGE, '.htaccess'))
cpSync(join('web', 'download', 'recital-manager-detail.html'), join(STAGE, 'recital-manager-detail.html'))
cpSync(join('web', 'download', 'guide.html'), join(STAGE, 'guide.html'))

writeFileSync(
  join(STAGE, 'READ-ME-FIRST.txt'),
  `연주회 매니저 — accelssam.com 업로드용

이 압축은 public_html/download 폴더 **안에서** 푸세요.
폴더가 들어 있지 않으므로, 푼 자리에 아래 네 파일이 그대로 나옵니다.

  index.html                      받는 자리       → accelssam.com/download/
  recital-manager-detail.html     상품 상세페이지  → accelssam.com/download/recital-manager-detail.html
  guide.html                      사용설명서       → accelssam.com/download/guide.html
  .htaccess                       설치 파일이 열리지 않고 내려받아지게 함

설치 파일(.exe)은 올리지 않으셔도 됩니다.
안 올리시면 깃허브에 있는 것을 자동으로 씁니다. 올리시면 그때부터 이 폴더 것을 씁니다.
올리실 때는 이 폴더에 그대로 두시고 이름은 바꾸지 마세요.

  RecitalManager-Setup-Windows.exe
  RecitalManager-Mac.dmg

푼 뒤에는 이 압축 파일과 이 안내문은 지우셔도 됩니다.
`,
  'utf8',
)

rmSync(OUT, { force: true })
// -j 는 폴더 없이 파일만 담는다. 숨은 파일(.htaccess)도 이름을 적어 함께 담는다
execFileSync('zip', ['-q', '-j', join('..', '..', OUT), 'index.html', 'guide.html', 'recital-manager-detail.html', '.htaccess', 'READ-ME-FIRST.txt'], {
  cwd: STAGE,
})
if (!existsSync(OUT)) {
  console.error('묶음을 만들지 못했습니다')
  process.exit(1)
}
console.log(execFileSync('unzip', ['-l', OUT], { encoding: 'utf8' }).trim())
console.log(`\n${OUT} 준비 완료 — public_html/download 안에서 풀면 됩니다.`)
