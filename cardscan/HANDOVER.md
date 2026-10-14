# 명함스캔(CardScan) 개발 인수인계 — 집 PC 에서 이어서 개발하기

> 이 문서 하나로 집 PC 에서 바로 개발을 이어갈 수 있게 정리했습니다. 처음이면 **1 → 2 → 3** 순서대로 하세요.
> AI 코딩 도우미(Claude Code)로 이어서 개발한다면 같은 폴더의 `CLAUDE.md` 를 자동으로 읽습니다 (11장).

## 0. 현재 상태 (2026-10 기준)

| 항목 | 상태 |
|---|---|
| 앱 | 안드로이드 앱(Expo SDK 57 / React Native) + 아이폰 홈 화면 웹앱 — **같은 코드** |
| 최신 빌드 | APK build #19 (직접 설치용) · 플레이스토어용 AAB 자동 빌드 · 아이폰 웹앱 자동 배포 |
| 테스트 | 자동 테스트 187개 통과 (명함 분석·국제 전화번호·번역 누락·Pro 규칙 등) |
| 기능 | 무료 온디바이스 명함 인식(한·영), 연락처·구글 시트·HubSpot·웹훅·슬랙 연동, 행사 태그·연속 촬영, 팔로업 알림, 내 명함 QR, 한국어/영어, Pro 평생 이용권(구글 플레이 결제) |
| 출시 준비 | `store/` 에 등록정보·스크린샷(한/영)·개인정보처리방침·심사 답변·출시 가이드 완료. 플레이 콘솔 작업은 아직 (`store/README.md`) |
| 코드 위치 | GitHub `himan98hkt-prog/-` 저장소의 `cardscan/` 폴더, 브랜치 **`claude/tender-thompson-w3ghh5`** (PR #16, 아직 기본 브랜치에 합치지 않음) |

### 먼저 권장: PR #16 을 기본 브랜치에 합치기
지금 앱 코드는 작업 브랜치에만 있습니다. 합쳐 두면 집 PC 에서 기본 브랜치만 받으면 되고, GitHub Actions 의 **Run workflow** 버튼(플레이스토어 AAB 수동 빌드 등)도 생깁니다.
1. https://github.com/himan98hkt-prog/-/pull/16 → 아래 **Ready for review** → **Merge pull request** → **Confirm merge**
2. 이후 집 PC 에서는 기본 브랜치에서 새 브랜치를 만들어 작업하세요 (4장).

합치지 않고 그대로 써도 됩니다 — 그때는 2-3 의 `git checkout claude/tender-thompson-w3ghh5` 로 받으세요.

---

## 1. 집 PC 준비물

| 준비물 | 필요한 경우 | 받는 곳 |
|---|---|---|
| **Git** | 항상 | https://git-scm.com/download/win (설치 옵션은 기본값) |
| **Node.js 22 LTS** | 항상 | https://nodejs.org → LTS (20 이상이면 동작) |
| **VS Code** | 권장 (코드 편집기) | https://code.visualstudio.com — 폴더를 열면 추천 확장(Expo Tools·Prettier·Vitest)을 설치하라고 안내합니다 |
| **Android Studio** | 내 안드로이드폰에 개발 버전을 직접 설치해 볼 때 (3-2) | https://developer.android.com/studio — JDK·안드로이드 SDK 가 함께 들어옵니다 |
| 안드로이드폰 + USB 케이블 | 3-2 | 폰에서 개발자 옵션 → USB 디버깅 켜기 |
| GitHub 계정 로그인 | 코드 올리기(push) | 처음 push 할 때 브라우저 로그인 창이 뜹니다 |

> 웹 미리보기(3-1)와 자동 테스트만 할 거면 **Git + Node 만** 있으면 됩니다.

## 2. 처음 한 번만 — 코드 받고 설치

### 2-1. 코드 받기 (PowerShell 또는 터미널)
```powershell
cd $HOME\Documents          # 원하는 위치
git clone https://github.com/himan98hkt-prog/-.git cardscan-repo
cd cardscan-repo
git checkout claude/tender-thompson-w3ghh5   # PR #16 을 합쳤다면 이 줄은 생략
cd cardscan
```
> 윈도우에서 경로가 너무 길다는 오류가 나면 관리자 PowerShell 에서 `git config --system core.longpaths true` 를 한 번 실행하세요.

### 2-2. (휴대폰 개발 빌드를 할 때만) 안드로이드 SDK 설정
1. Android Studio 실행 → **More Actions → SDK Manager**
   - SDK Platforms: **Android 16 (API 36)** 체크
   - SDK Tools: **Android SDK Build-Tools**, **Android SDK Platform-Tools**, **NDK (Side by side)**, **CMake** 체크 → Apply
2. 환경 변수 (윈도우: 시작 → "환경 변수" 검색 → 사용자 변수 → 새로 만들기)
   - `ANDROID_HOME` = `C:\Users\<사용자이름>\AppData\Local\Android\Sdk`
   - `JAVA_HOME` = `C:\Program Files\Android\Android Studio\jbr` (Android Studio 에 들어 있는 JDK)
   - Path 에 추가: `%ANDROID_HOME%\platform-tools`
3. PowerShell 을 새로 열고 `adb version`, `java -version` 이 나오면 완료

### 2-3. 한 번에 설치·점검 (스크립트)
cardscan 폴더에서:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup-local.ps1     # 윈도우
bash scripts/setup-local.sh                                            # 맥·리눅스
```
준비물 확인 → `npm ci`(패키지 설치) → 타입검사 + 자동 테스트 187개까지 한 번에 하고, 다음 할 일을 알려 줍니다.

## 3. 개발하는 방법 3가지

### 3-1. 웹 미리보기 — 화면 고칠 때 가장 빠름
```bash
npm run web
```
브라우저가 열리고, 코드를 저장하면 바로 바뀝니다. 명함 인식은 웹용 엔진(Tesseract)으로 동작하고, **연락처 직접 저장·구글 플레이 결제·문서 스캐너는 웹에 없습니다**(앱에서만).
휴대폰 크기로 보려면 크롬 개발자 도구(F12) → 휴대폰 모양 아이콘.

### 3-2. 내 안드로이드폰에서 실행 (개발 빌드) — 실제 기능 확인
이 앱은 직접 만든 네이티브 모듈(`modules/card-ocr`: ML Kit 인식·문서 스캐너)과 결제 모듈이 있어 **Expo Go 앱으로는 실행되지 않습니다.** 대신 개발 빌드를 폰에 설치합니다.
1. 폰: 설정 → 휴대전화 정보 → 소프트웨어 정보 → **빌드번호 7번 누르기** → 개발자 옵션 → **USB 디버깅 켜기**
2. USB 로 PC 와 연결 → 폰에 뜨는 "USB 디버깅 허용" → 허용. PC 에서 `adb devices` 에 기기가 보이면 OK
3. cardscan 폴더에서
   ```bash
   npm run android:dev
   ```
   처음은 10~20분 걸립니다 (안드로이드 프로젝트 생성 + 빌드). 폰에 **"명함스캔"** 개발 버전이 설치·실행되고, 이후에는 코드를 저장하면 폰 화면이 바로 바뀝니다.
4. 다음부터는 `npm start` 만 해도 됩니다 (네이티브 쪽 — `app.json`, 패키지 추가, `modules/` — 을 바꿨을 때만 다시 `npm run android:dev`)

> 개발 빌드는 디버그 키로 서명되어, 이미 설치된 Releases 의 APK 와 서명이 같아 **덮어 설치됩니다(명함 유지)**. 안 되면 설정 → 백업 파일 만들기 후 지우고 설치 → 복원.
> 개발 빌드는 결제가 꺼진 "개인용" 모드라 Pro 기능이 모두 열려 있습니다(정상).

### 3-3. 배포용 빌드 — GitHub 가 자동으로
코드를 GitHub 에 올리면(push) `cardscan/` 이 바뀐 경우 자동으로:
| 워크플로 | 결과 | 받는 곳 |
|---|---|---|
| 명함스캔 앱 / CI | 타입검사·테스트·번들 검사 | Actions 탭 (빨간 X 면 실패) |
| 명함스캔 APK | 직접 설치용 APK | https://github.com/himan98hkt-prog/-/releases/tag/cardscan-android |
| 명함스캔 플레이스토어 AAB | 플레이 업로드용 AAB (업로드 키로 서명, 결제 켜짐) | Actions → 해당 실행 → Artifacts |
| 명함스캔 아이폰 웹앱 | 아이폰 웹앱 사이트 | https://himan98hkt-prog.github.io/-/ |

로컬 PC 에서 APK/AAB 를 직접 만들 필요는 없습니다. (꼭 필요하면 11-3)

## 4. 날마다 작업 흐름

```bash
git pull                                 # 최신 받기
git checkout -b feature/무엇을-고치는지   # 새 작업 브랜치 (선택)
npm run web  또는  npm start             # 고치면서 확인
npm run check                            # 올리기 전에 꼭: 타입검사 + 테스트
git add -A
git commit -m "무엇을 왜 바꿨는지"
git push -u origin 브랜치이름
```
→ GitHub 에서 Pull Request 를 만들어 기본 브랜치에 합치면 빌드가 돌아갑니다. (혼자 개발이면 기본 브랜치에 바로 push 해도 됩니다)

## 5. 폴더 지도 (`cardscan/`)

```
src/app/            화면 (expo-router — 파일 하나가 화면 하나)
  (tabs)/index.tsx    명함첩 (목록·검색·팔로업·무료 사용량)
  (tabs)/scan.tsx     촬영 (행사 태그·연속 촬영·여러 장 등록)
  (tabs)/settings.tsx 설정 (언어·Pro·인식 방식·연동·백업)
  card/[id].tsx       명함 상세 (원본 사진·전화·메모·팔로업·연동 상태)
  review.tsx          인식 결과 확인/수정   mycard.tsx  내 명함 QR
  _layout.tsx         앱 뼈대 (Pro → 저장소 → 언어 순서로 감쌈)
src/core/           화면과 무관한 순수 로직 (테스트 대상)
  cardParser.ts       한국 명함 분석 (규칙 기반)
  cardParserLatin.ts  영어권 명함 분석 (국제 전화번호 libphonenumber + 줄 점수)
  normalize.ts        번호·이메일 정리   mapping.ts  연락처·vCard·시트·슬랙 형식
  organize.ts         검색(초성)·정렬·그룹·경력 이력   exportData.ts  CSV·백업
  pro.ts              무료 한도(50장)·Pro 기능·가격 규칙   settings.ts  설정 기본값
src/integrations/   외부 연결 — ocr.ts(인식 진입점), sync.ts·http.ts(시트·HubSpot·웹훅·슬랙), deviceContacts.ts
src/ui/             공통 UI·상태 — store.tsx(명함 저장·동기화), pro.tsx(결제 상태·결제 화면), billing.ts(구글 플레이 결제),
                    theme.ts(색·글꼴), components.tsx, DigitalCard.tsx(원본 명함 보기), capture.ts(촬영)
src/i18n/           다국어 — core.ts(t 함수), en.ts(영어 사전 350문장), index.ts(휴대폰 언어 감지)
src/storage/        휴대폰 저장 (AsyncStorage·보안 저장소·사진 파일 / 웹은 IndexedDB)
modules/card-ocr/   직접 만든 안드로이드 모듈 (Kotlin): ML Kit 한국어 인식 + 구글 문서 스캐너 / 웹은 Tesseract
plugins/            빌드 설정 플러그인 (업로드 키 서명)
tests/              자동 테스트 (vitest) — 명함 견본: 한국 다수 + 영어권 31장
store/              플레이스토어 자료 (등록정보·그래픽·방침·가이드·전략)
scripts/            pwa.mjs(아이폰 웹앱 마무리), setup-local.*(이 문서 2-3)
supabase/           (선택·유료) Claude 인식 서버 함수
docs/               연동 안내(INTEGRATIONS.md), 구글 시트 스크립트
app.json            앱 이름·권한·아이콘·플러그인 (네이티브 설정은 여기서만 — android/ 폴더는 자동 생성물)
../.github/workflows/cardscan*.yml   자동 빌드 (APK·AAB·웹앱·검사)
```

## 6. 꼭 지킬 규칙 (지금까지의 결정 사항)

1. **화면 문구는 `t('한국어 문장')`** 으로 쓰고 영어는 `src/i18n/en.ts` 에 추가. 빠뜨리면 `tests/i18n.test.ts` 가 실패합니다. 파일 맨 위에 정의한 라벨 맵은 쓰는 곳에서 `t(MAP[k])` (언어 전환을 따라가게).
2. **무료가 기본**: 명함 인식은 휴대폰 안(ML Kit)에서, 인터넷·요금 없이. 유료 API 는 사용자가 직접 켤 때만.
3. **원본 명함은 꾸미지 않는다**: 사진이 있으면 실제 명함 사진을 그대로 보여 줌 (디지털 명함은 사진이 없을 때만).
4. **데이터를 볼모로 잡지 않는다**: 무료 한도(50장)를 넘어도 저장한 명함 보기·수정·백업은 언제나 가능. 새 사람 저장·외부 연동·CSV·여러 장·연속 촬영만 Pro.
5. **한국 명함 분석은 건드릴 때 테스트부터**: 실제 명함에서 틀린 사례를 `tests/cardParser*.test.ts` 에 견본으로 추가한 뒤 고치기.
6. **네이티브 설정은 `app.json`·플러그인으로만** — `android/`·`ios/` 폴더는 만들어지는 결과물이라 직접 고치지 않음 (git 에도 안 올림).
7. 패키지 추가는 `npx expo install 패키지명` (SDK 에 맞는 버전으로). `.npmrc` 의 `legacy-peer-deps=true` 는 그대로 둠.
8. 버전 올리기: 사용자에게 보이는 버전은 `app.json` 의 `"version"` (예: 1.0.1). 내부 버전 코드는 빌드가 자동으로 올립니다.

## 7. 비밀값·키 (저장소에 없음)

| 무엇 | 어디에 | 비고 |
|---|---|---|
| 플레이 업로드 키 `cardscan-upload.jks` + 비밀번호 | 전에 전달한 파일 2개 → **GitHub Secrets 4개** (`CARDSCAN_UPLOAD_*`) | USB·개인 클라우드 두 곳에 보관. 잃어버려도 플레이 콘솔에서 재설정 요청 가능 |
| 연동 토큰(HubSpot 등)·API 키 | 사용자 휴대폰 보안 저장소 | 코드·저장소에 넣지 않음 |
| GitHub Secrets 위치 | https://github.com/himan98hkt-prog/-/settings/secrets/actions | |

`.gitignore` 가 `*.jks`, `*.keystore`, `.env*.local` 을 막고 있습니다. 키 파일은 cardscan 폴더 밖에 두세요.

## 8. 배포·출시 절차 요약

- **직접 설치 APK**: push 하면 자동 → Releases `cardscan-android`. (판매 시작 전 공개 배포 중단 권장 — `store/README.md` 0단계 5번)
- **플레이스토어**: push 하면 AAB 자동 → Artifacts 에서 받아 콘솔에 업로드. 전체 순서·심사·테스트(12명×14일)는 `store/README.md`
- **Pro 결제 상품**: `store/pro-billing.md` (상품 ID `pro_lifetime`, 출시 1,900원 → 정가 3,900원 / $1.99 → $2.99)
- **영어권 확장**: `store/README.md` "영어권 나라로 넓히기"
- **아이폰 웹앱**: push 하면 자동 배포 (처음 한 번 Settings → Pages 에서 `gh-pages` 지정 필요)

## 9. 자주 생기는 문제

| 증상 | 해결 |
|---|---|
| `npm ci` 에서 ERESOLVE (의존성 충돌) | cardscan 폴더 안에서 실행했는지 확인 (`.npmrc` 가 있어야 함) |
| `npm run android:dev` — `SDK location not found` | 2-2 의 `ANDROID_HOME` 설정 후 터미널 새로 열기 |
| `JAVA_HOME is not set` / Java 버전 오류 | `JAVA_HOME` 을 Android Studio 의 `jbr` 폴더로 (또는 Temurin JDK 17 설치) |
| `No connected devices` | 케이블(데이터 지원)·USB 디버깅 허용 확인, `adb devices` |
| 화면이 이상하게 옛날 그대로 | `npx expo start -c` (캐시 지우고 시작) |
| `app.json`·플러그인을 바꿨는데 반영 안 됨 | `npm run android:clean` 후 `npm run android:dev` |
| 설치 시 "서명이 다르다"며 실패 | 기존 앱의 백업 파일을 만들고 앱 삭제 → 설치 → 복원 |
| 윈도우 경로 길이 오류 | `git config --system core.longpaths true`, 저장소를 `C:\dev` 처럼 짧은 경로에 |
| GitHub Actions 빨간 X | Actions → 실패한 실행 → 빨간 단계 로그 확인. 대부분 `npm run check` 를 먼저 돌리면 미리 잡힘 |

## 10. 남은 일 (우선순위)

1. **플레이 콘솔**: 개발자 계정·결제 프로필 → 업로드 키 Secrets 등록 → AAB 업로드 → 비공개 테스트 12명 × 14일 → 프로덕션 (`store/README.md`)
2. **판매 전 정리**: 저장소 Private 전환 검토, 공개 APK 배포 중단, 개인정보처리방침 주소 유지 방안
3. **Pro 결제 실기기 테스트**: 라이선스 테스터로 구매·복원·환불 확인 (`store/pro-billing.md` 4번)
4. 인식 개선: 한국 주소 "5층"이 "55"로 읽히는 사례 등 — 실제 명함 사진에서 틀린 것 모아 테스트로 추가
5. 구글 드라이브 자동 백업 (휴대폰 교체 대비) — `store/strategy.md` 약점 표
6. 영어권 출시 (한국 출시 약 1개월 뒤) — 앱 쪽 준비는 완료

## 11. 참고

### 11-1. Claude Code(AI 코딩 도우미)로 이어서 개발
1. 설치: https://claude.com/claude-code 안내대로 (윈도우는 PowerShell 설치 명령 또는 VS Code 확장)
2. cardscan 폴더에서 `claude` 실행 → `CLAUDE.md`(프로젝트 요약·명령·규칙)를 자동으로 읽고 시작합니다
3. 예: "명함 상세 화면에 ○○ 기능 추가해줘", "테스트 돌리고 실패하면 고쳐줘"

### 11-2. 주요 명령 모음 (cardscan 폴더에서)
| 명령 | 하는 일 |
|---|---|
| `npm run web` | 웹 미리보기 |
| `npm start` | 개발 서버 (개발 빌드가 폰에 설치된 뒤) |
| `npm run android:dev` | 폰에 개발 빌드 설치·실행 |
| `npm run android:clean` | 안드로이드 프로젝트 새로 만들기 (네이티브 설정 바꾼 뒤) |
| `npm run check` | 타입검사 + 테스트 (올리기 전 필수) |
| `npm run test:watch` | 저장할 때마다 테스트 |
| `npm run format` | 코드 모양 정리 (Prettier) |
| `npm run doctor` | Expo 설정·패키지 버전 진단 |

### 11-3. (선택) 내 PC 에서 서명된 배포 빌드 만들기
보통은 필요 없습니다(GitHub 가 만듦). 꼭 필요하면 2-2 를 마친 뒤:
```powershell
npm run android:clean
$env:CARDSCAN_UPLOAD_STORE_FILE="C:\keys\cardscan-upload.jks"
$env:CARDSCAN_UPLOAD_STORE_PASSWORD="(비밀번호)"; $env:CARDSCAN_UPLOAD_KEY_PASSWORD="(비밀번호)"; $env:CARDSCAN_UPLOAD_KEY_ALIAS="upload"
$env:EXPO_PUBLIC_STORE="play"          # 플레이 결제 켜기 (스토어용일 때만)
cd android; .\gradlew bundleRelease     # 결과: android\app\build\outputs\bundle\release\app-release.aab
```
스토어용은 패키지 이름이 `io.github.himan98hktprog.cardscan` 이어야 하므로 GitHub 워크플로(`cardscan-play.yml`)를 쓰는 편이 안전합니다.

### 11-4. 더 읽을 문서
- `README.md` — 기능 소개·설치 방법·인식 방식
- `docs/INTEGRATIONS.md` — 연동(웹훅 형식 등)
- `store/` — 출시·판매 전부
- `AGENTS.md` — Expo 개발 일반 규칙
