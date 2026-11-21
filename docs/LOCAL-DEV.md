# 내 PC에서 개발하기 — 학원 관리노트

윈도우 PC 기준으로 썼습니다(맥도 명령은 같습니다). 처음이면 **1 → 2 → 3** 순서대로 하세요.
3장까지 한 번 해 두면, 그다음부터는 4장의 `npm start` 하나로 시작합니다.

| 하고 싶은 일 | 명령 |
|---|---|
| 처음 한 번 설치·점검 | `npm run setup` |
| 개발 서버 열기 (고치고 저장하면 바로 반영) | `npm start` |
| 올리기 전 점검 (테스트 + 빌드) | `npm run check` |
| 실제 브라우저로 전체 흐름 검사 | `npm run smoke` |

> 같은 저장소의 `cardscan/`(명함스캔 앱)은 따로 안내가 있습니다 → `cardscan/HANDOVER.md`

---

## 1. 준비물

| 준비물 | 필요한 경우 | 받는 곳 |
|---|---|---|
| **Git** | 항상 | https://git-scm.com/download/win (설치 옵션은 기본값 그대로) |
| **Node.js 22 LTS** | 항상 | https://nodejs.org → LTS (20 이상이면 동작) |
| **VS Code** | 권장 (코드 편집기) | https://code.visualstudio.com |
| PHP 8 | 퍼널모아 플러그인을 고칠 때만 (7장) | https://windows.php.net/download |
| Claude Code | AI 도우미로 이어서 개발할 때 (8장) | Claude 데스크톱 앱 또는 `npm install -g @anthropic-ai/claude-code` |

윈도우 10·11 이면 PowerShell 에서 한 번에 설치할 수도 있습니다.

```powershell
winget install --id Git.Git -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Microsoft.VisualStudioCode -e
```

설치가 끝나면 **PowerShell 을 닫았다가 새로 여세요.** 새 창에서 아래 두 줄이 버전을 보여 주면 준비 끝입니다.

```powershell
git --version
node -v
```

## 2. 코드 받기 (처음 한 번)

### 2-1. 폴더 위치 — OneDrive 밖에

`문서`(Documents)·`바탕 화면` 폴더는 OneDrive 로 동기화되는 경우가 많습니다. 설치 파일(node_modules) 수만 개가
계속 동기화되면서 느려지거나 파일이 잠깁니다. **`C:\dev` 처럼 OneDrive 밖의 폴더**에 받으세요.

```powershell
mkdir C:\dev
cd C:\dev
git clone https://github.com/himan98hkt-prog/-.git academy-note
cd academy-note
```

> 저장소가 비공개면 처음 `git clone` 할 때 GitHub 로그인 창이 뜹니다. 로그인하면 됩니다.

### 2-2. 작업 브랜치

지금 앱 코드는 작업 브랜치에만 있고, 기본 브랜치(main)에는 아직 합쳐지지 않았습니다(PR #1).

- **권장 — PR #1 을 합치기:** https://github.com/himan98hkt-prog/-/pull/1 → **Merge pull request** → **Confirm merge**.
  그다음부터는 `main` 만 받으면 됩니다. (명함스캔 작업도 이 PR 에 함께 들어 있어 같이 합쳐집니다)
- **합치지 않고 쓰려면:**
  ```powershell
  git checkout claude/dev-instructions-review-n1xsty
  ```

### 2-3. 윈도우에서 한 번만

```powershell
git config --global core.longpaths true        # 긴 경로 오류 방지 (명함스캔 폴더 때문)
git config --global core.autocrlf false        # 줄바꿈은 저장소 설정(.gitattributes)을 따름
```

## 3. 처음 한 번 — 설치와 점검

```powershell
npm run setup
```

준비물 확인 → 패키지 설치(1~3분) → 자동 테스트 → 배포용 빌드까지 한 번에 하고, 마지막에 다음 할 일을 알려 줍니다.
`[!!]` 로 표시되는 것은 없어도 개발은 됩니다(브라우저 검사용 브라우저, PHP, Pro 설정 등).

> **`npm.ps1 파일을 로드할 수 없습니다 … 스크립트를 실행할 수 없으므로` 오류가 나면**
> 윈도우 PowerShell 의 기본 보안 설정 때문입니다. 아래를 한 번 실행하고 PowerShell 을 새로 여세요.
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

VS Code 로 폴더를 열면(`code .`) 추천 확장(Vitest 등)을 설치하라고 안내합니다. 설치하면 됩니다.

## 4. 날마다 — 고치면서 보기

```powershell
npm start
```

브라우저가 `http://localhost:5173/lite.html` 로 열립니다. 코드를 고치고 저장하면 화면이 바로 바뀝니다.
끌 때는 터미널에서 `Ctrl + C`.

VS Code 에서는 메뉴 **터미널 → 작업 실행** 에서 "개발 서버 열기", "자동 테스트", "올리기 전 점검" 등을 고를 수 있습니다.
(`Ctrl + Shift + B` 는 바로 "개발 서버 열기")

### 처음 화면부터 다시 보고 싶을 때

앱은 자료를 브라우저 안(IndexedDB)에 저장합니다. 처음 상태로 돌리려면:

- **샘플·원생 자료만 지우기:** 앱의 설정 → 고급 → 자료 모두 지우기 (인증은 남습니다)
- **인증까지 지우고 첫 화면부터:** 브라우저에서 `F12` → **Application(애플리케이션)** → **Storage** → **Clear site data**

### 인증키가 필요할 때

개발 서버가 켜진 상태에서 `http://localhost:5173/tools/keygen.html` 을 열면 판매자용 발급기로 키를 만들 수 있습니다.
또는 첫 화면에서 **14일 무료로 써 보기** 를 누르면 키 없이 모든 기능을 씁니다.

### 휴대폰으로 보기 (같은 와이파이)

```powershell
npm run dev -- --host
```

터미널에 나오는 `Network: http://192.168.x.x:5173/` 주소 뒤에 `lite.html` 을 붙여 휴대폰 브라우저로 엽니다.
윈도우 방화벽이 허용할지 물으면 **개인 네트워크 허용**.

## 5. 고친 뒤 확인

| 언제 | 명령 | 걸리는 시간 |
|---|---|---|
| 항상 (올리기 전에 꼭) | `npm run check` | 10초 |
| 화면이나 흐름을 바꿨을 때 | `npm run smoke` | 1~2분 |
| 목록·통계처럼 자료를 많이 읽는 곳을 바꿨을 때 | `npm run perf` | 처음 3~5분, 다음부터 `npm run perf -- --skip-seed` |
| 눈으로 전 화면 보기 | `npm run shots -- piano` | 1분 → `screenshots/` 폴더 |

`smoke`·`perf`·`shots` 는 실제 브라우저를 띄웁니다. 윈도우에는 Edge 가 기본으로 깔려 있어 그대로 돕니다.
브라우저를 못 연다고 나오면 검사용 크로미움을 한 번 받으세요.

```powershell
npx playwright install chromium
```

## 6. GitHub 에 올리기

```powershell
git pull                                   # 다른 곳에서 고친 것 먼저 받기
git checkout -b feature/무엇을-고치는지      # 새 작업 브랜치 (선택)
npm run check                              # 통과해야 올립니다
git add -A
git commit -m "무엇을 왜 바꿨는지"
git push -u origin feature/무엇을-고치는지
```

GitHub 에서 Pull Request 를 만들면 자동 점검(테스트·빌드·플러그인 점검)이 돌고, 통과하면 합칩니다.
혼자 개발한다면 `main` 에 바로 올려도 됩니다.

### 배포 (웹호스팅에 올리기)

```powershell
npm run build                              # dist/ 폴더가 만들어집니다
```

`dist/` 안의 `index.html`·`lite.html`·`assets/` 를 웹호스팅에 올립니다. `dist/tools/` 는 **올리지 마세요**(판매자 전용 발급기).
구매 버튼 주소를 바꾸려면 빌드할 때 넣습니다.

```powershell
$env:VITE_BUY_URL="https://내사이트.com/상품주소"; npm run build
```

자세한 절차: `docs/DEPLOY.md`. Pro(Supabase)를 시험하려면 `.env.example` 을 `.env` 로 복사해 채웁니다(커밋 금지).

## 7. 퍼널모아 플러그인을 고칠 때

플러그인 코드는 `integration/funnelmoa/academy-note-keys/` 에 있습니다(PHP).

**점검 돌리기** — PHP 가 있어야 합니다.

1. https://windows.php.net/download 에서 최신 PHP 8 의 **x64 Non Thread Safe** zip 을 받아 `C:\php` 에 풉니다
2. `C:\php\php.ini-development` 를 복사해 `C:\php\php.ini` 로 만들고, 아래 두 줄 앞의 `;` 를 지웁니다
   ```ini
   extension_dir = "ext"
   extension=sqlite3
   ```
3. 시작 → "환경 변수" → 사용자 변수 `Path` 에 `C:\php` 추가 → PowerShell 새로 열기
4. `npm run test:plugin` (61가지) — PHP 가 있으면 `npm test` 도 "플러그인이 만든 키가 앱에서 열리는지"까지 확인합니다

PHP 가 없어도 GitHub 에 올리면 자동 점검에서 같은 것이 돕니다.

**진짜 워드프레스에서 시험하기** — 무료 프로그램 **Local**(https://localwp.com)로 PC 안에 워드프레스를 만들 수 있습니다.
우커머스를 설치하고 `npm run plugin` 으로 만든 `dist-plugin/academy-note-keys.zip` 을 올린 뒤,
**관리노트 인증키 → 직접 보내기 → 내 메일로 시험 발송** 으로 메일 모양과 버튼을 확인합니다.
Local 은 메일을 실제로 내보내지 않고 자체 메일함 화면에 모아 보여 줍니다.
(코스모스팜 회원관리 결제는 실제 퍼널모아 사이트에서 확인해야 합니다 — `integration/funnelmoa/README.md`)

## 8. Claude Code 로 이어서 개발하기

저장소 맨 위의 `CLAUDE.md` 에 프로젝트 구조, 명령, 꼭 지킬 것(인증키 규칙을 바꾸지 말 것 등)을 적어 두었습니다.
Claude Code 를 이 폴더에서 열면 자동으로 읽습니다.

```powershell
cd C:\dev\academy-note
claude
```

> 클라우드 세션에서 이 PC 폴더를 바로 쓰려면 Claude 데스크톱 앱의 **설정 → Claude Code → Remote Control** 에 이 폴더를 추가합니다.
> 지금 목록에 있는 폴더들은 클라우드 세션에 열리지 않는 상태라고 나옵니다 — 대개 Claude 앱을 최신으로 업데이트하면 됩니다.
> 이 기능은 아직 모든 계정에 열려 있지 않을 수 있습니다.

## 9. 문제가 생기면

| 증상 | 해결 |
|---|---|
| `'npm' 은(는) … 인식되지 않습니다` | Node 설치 뒤 PowerShell 을 새로 열지 않았습니다. 창을 닫고 새로 여세요 |
| `npm.ps1 … 스크립트를 실행할 수 없으므로` | 3장의 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `npm run setup` 의 패키지 설치가 아주 느림 | 백신이 node_modules 를 검사 중입니다. OneDrive 폴더라면 2-1 대로 옮기세요 |
| 화면이 바뀌지 않음 | 저장했는지 확인 후 브라우저에서 `Ctrl + F5` |
| `…번 포트를 다른 프로그램이 쓰고 있습니다` | 이전 검사나 개발 서버 창을 닫고 다시 실행 |
| `브라우저(…)를 열지 못했습니다` | `npx playwright install chromium` |
| 고치지 않은 파일이 전부 바뀐 것으로 나옴 | 줄바꿈 문제입니다. `git config --global core.autocrlf false` 후 `git checkout -- .` |
| 터미널의 한글이 깨짐 | 윈도우 터미널(Windows Terminal) 앱이나 VS Code 터미널을 쓰세요 |

## 10. 폴더 지도

```
src/core/       계산·판정 로직 (테스트 대상)          tests/        자동 테스트
src/data/       저장소(IndexedDB · Supabase)          scripts/      검사·빌드 스크립트
src/ui/         화면 (views/ 가 메뉴 하나씩)           docs/         문서
src/styles.css  디자인 (색·글씨·버튼)                  integration/  퍼널모아 플러그인 · 피아노 앱 패치
lite.html       Lite 시작 페이지                      tools/        판매자용 키 발급기
index.html      Pro 시작 페이지                       supabase/     Pro 데이터베이스 설정
```

더 자세한 구조는 `README.md` 와 `docs/ARCHITECTURE.md` 에 있습니다.
