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
import { zipFolder } from './zip-utf8.mjs'

const STAGE = join('배포', 'web-upload')
const OUT = join('web', 'recital-upload.zip')

rmSync(STAGE, { recursive: true, force: true })
mkdirSync(STAGE, { recursive: true })

cpSync(join('web', 'download', 'index.html'), join(STAGE, 'index.html'))
cpSync(join('web', 'download', '.htaccess'), join(STAGE, '.htaccess'))
cpSync(join('web', 'download', 'recital-manager-detail.html'), join(STAGE, 'recital-manager-detail.html'))
cpSync(join('web', 'download', 'guide.html'), join(STAGE, 'guide.html'))

/*
 * 상품 편집 화면에 **붙여넣는 글** 셋.
 *
 * 서버에 올리는 것이 아니라 워드프레스 상품 편집 화면에 붙이는 것인데,
 * 따로 드리면 「어느 것이 최신인지」가 금방 어긋난다. 상세페이지를 새로 만들 때
 * 같이 담아 한 묶음으로 드린다.
 */
for (const paste of ['상세페이지-붙여넣기.html', '상품요약설명-붙여넣기.html', '커리큘럼-붙여넣기.html']) {
  cpSync(join('web', paste), join(STAGE, paste))
}

writeFileSync(
  join(STAGE, 'READ-ME-FIRST.txt'),
  `연주회 매니저 — accelssam.com 업로드용

이 압축은 public_html/download 폴더 **안에서** 푸세요.
폴더가 들어 있지 않으므로, 푼 자리에 아래 네 파일이 그대로 나옵니다.

  index.html                      받는 자리       → accelssam.com/download/
  recital-manager-detail.html     상품 상세페이지  → accelssam.com/download/recital-manager-detail.html
  guide.html                      사용설명서       → accelssam.com/download/guide.html
  .htaccess                       설치 파일이 열리지 않고 내려받아지게 함

  ※ 「붙여넣기」로 끝나는 파일 셋은 **올리는 것이 아닙니다.** 아래를 보세요.

설치 파일(.exe)은 올리지 않으셔도 됩니다.
안 올리시면 깃허브에 있는 것을 자동으로 씁니다. 올리시면 그때부터 이 폴더 것을 씁니다.
올리실 때는 이 폴더에 그대로 두시고 이름은 바꾸지 마세요.

  RecitalManager-Setup-Windows.exe
  RecitalManager-Mac.dmg

■ 상품 페이지에 붙여넣는 글 (올리는 것이 아닙니다)

워드프레스 → 상품 → 연주회 매니저 → 편집 에서, 파일을 메모장으로 열어
안에 있는 것을 통째로 복사해 아래 자리에 붙여넣으세요.

  상세페이지-붙여넣기.html     「설명」란 → 오른쪽 위 ⋮ → 코드 편집기
                               → 안에 있던 것을 전부 지우고 붙여넣기
  상품요약설명-붙여넣기.html   「상품 요약 설명」 칸 → 「코드」 탭에 붙여넣기
                               (「비주얼」 탭에 붙이면 태그가 글자로 보입니다)
  커리큘럼-붙여넣기.html       커리큘럼(또는 추가 정보) 탭 → 텍스트(HTML) 모드에 붙여넣기

  ※ recital-manager-detail.html 을 먼저 올리신 뒤에 붙여넣으세요 —
    상세페이지-붙여넣기.html 이 그 파일을 불러다 씁니다.

푼 뒤에는 이 압축 파일과 이 안내문은 지우셔도 됩니다.
`,
  'utf8',
)

rmSync(OUT, { force: true })
/*
 * 우리 압축기로 담는다.
 *
 * `zip -j` 는 이름이 UTF-8 이라는 표시를 안 붙인다 — 한글 이름이 윈도우에서 깨진다.
 * 「붙여넣기」 파일 셋이 그렇게 되면 원장님은 무엇을 어디에 붙일지 알 수 없다.
 * 폴더는 담기지 않는다(STAGE 안이 전부 파일이다) — 푼 자리에 그대로 나온다.
 */
await zipFolder(STAGE, OUT)
if (!existsSync(OUT)) {
  console.error('묶음을 만들지 못했습니다')
  process.exit(1)
}
console.log(execFileSync('unzip', ['-l', OUT], { encoding: 'utf8' }).trim())
console.log(`\n${OUT} 준비 완료 — public_html/download 안에서 풀면 됩니다.`)
