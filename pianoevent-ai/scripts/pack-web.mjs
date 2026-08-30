#!/usr/bin/env node
/**
 * accelssam.com 에 올릴 것들을 **한 묶음**으로 만든다.
 *
 *   npm run pack:web   →  web/accelssam-upload.zip
 *
 * 파일 관리자에 이 하나만 올려 「압축 풀기」 하면 폴더가 제자리에 만들어진다.
 * 올리는 파일 이름은 전부 영문이다 — 한글 이름은 서버에서 깨지는 일이 있다.
 */
import { execFileSync } from 'node:child_process'
import { cpSync, mkdirSync, rmSync, writeFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const STAGE = join('배포', 'web-upload')
const OUT = join('web', 'accelssam-upload.zip')

rmSync(STAGE, { recursive: true, force: true })
mkdirSync(join(STAGE, 'download'), { recursive: true })
mkdirSync(join(STAGE, 'pages'), { recursive: true })

cpSync(join('web', 'download', 'index.html'), join(STAGE, 'download', 'index.html'))
cpSync(join('web', 'download', '.htaccess'), join(STAGE, 'download', '.htaccess'))
cpSync(join('web', 'pages', 'recital-manager-detail.html'), join(STAGE, 'pages', 'recital-manager-detail.html'))

writeFileSync(
  join(STAGE, '읽어보세요.txt'),
  `연주회 매니저 — accelssam.com 업로드용 묶음
============================================

이 압축을 WP 파일 관리자의  public_html  에 올리고 「압축 풀기」 하시면
아래가 제자리에 만들어집니다.

  public_html/download/index.html
  public_html/download/.htaccess
  public_html/pages/recital-manager-detail.html

그다음 설치 파일을 download 폴더에 올리시면 끝입니다.

  RecitalManager-Setup-Windows.exe   (92MB)
  RecitalManager-Mac.dmg             (110MB)  ※ 맥 손님이 계실 때만

받는 곳: https://github.com/himan98hkt-prog/-/releases/tag/installer-latest

파일 이름은 **그대로** 두세요. 이름이 다르면 받는 자리의 단추가 동작하지 않습니다.
`,
  'utf8',
)

rmSync(OUT, { force: true })
execFileSync('zip', ['-q', '-r', join('..', '..', OUT), 'download', 'pages', '읽어보세요.txt'], { cwd: STAGE })
if (!existsSync(OUT)) {
  console.error('묶음을 만들지 못했습니다')
  process.exit(1)
}
const list = execFileSync('unzip', ['-l', OUT], { encoding: 'utf8' })
console.log(list.trim())
console.log(`\n${OUT} 준비 완료 — 이 하나만 public_html 에 올리시면 됩니다.`)
