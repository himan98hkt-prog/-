/**
 * 인증키 발급기(브라우저용 HTML)에 **내 비밀값**을 넣어 한 부 만들어 낸다.
 *
 *   RECITAL_LICENSE_SECRET='…' npm run keygen:build
 *   →  배포/인증키-발급기.html
 *
 * 저장소에 있는 web/keygen/recital-keygen.html 에는 비밀값 자리가 비어 있다.
 * 비밀값이 든 판은 `배포/` 안에만 만들어지고 저장소에 올라가지 않는다.
 * 이 파일은 **홈페이지에 올리지 말고** 판매하시는 분 컴퓨터에만 두어야 한다.
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const SRC = join('web', 'keygen', 'recital-keygen.html')
const OUT = join('배포', '인증키-발급기.html')
const MARK = '__RECITAL_LICENSE_SECRET__'

const secret = process.env.RECITAL_LICENSE_SECRET?.trim()
if (!secret) {
  console.error(`비밀값이 없습니다.

  RECITAL_LICENSE_SECRET='내-비밀값' npm run keygen:build

깃허브 저장소 Settings → Secrets and variables → Actions 에 넣어 두신
RECITAL_LICENSE_SECRET 과 **똑같은 값**을 쓰셔야 합니다.
값이 다르면 발급기가 만든 키를 프로그램이 받지 않습니다.`)
  process.exit(1)
}

const html = readFileSync(SRC, 'utf8')
if (!html.includes(MARK)) {
  console.error(`${SRC} 안에 비밀값 자리(${MARK})가 없습니다.`)
  process.exit(1)
}

mkdirSync('배포', { recursive: true })
writeFileSync(OUT, html.replace(MARK, secret.replace(/["\\]/g, '\\$&')), 'utf8')

console.log(`${OUT} 준비 완료

  · 두 번 클릭하면 브라우저에서 열립니다. 인터넷이 없어도 됩니다.
  · 이 파일은 **절대 홈페이지에 올리지 마세요.** 남이 열면 키를 마음대로 만듭니다.
  · 잃어버리셔도 위 명령으로 다시 만드시면 됩니다.`)
