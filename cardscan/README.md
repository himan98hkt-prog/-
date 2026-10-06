# 명함스캔 (cardscan)

리멤버처럼 **명함을 찍으면 자동으로 읽어서 저장**하고, **휴대폰 연락처와 업무 시스템(구글 시트·HubSpot·ERP 웹훅·슬랙)에 자동 입력**하는 모바일 앱입니다.
안드로이드는 설치 앱(APK), 아이폰은 홈 화면 웹앱으로 — 둘 다 무료 (Expo / React Native 한 코드).

| 명함첩 | 촬영 | 상세·연동 상태 | 설정·연동 |
|---|---|---|---|
| ![](docs/images/list.png) | ![](docs/images/scan.png) | ![](docs/images/detail.png) | ![](docs/images/settings.png) |

## 안드로이드 휴대폰에 설치하기 (5분)

1. **설치 파일 받기** — 휴대폰 브라우저로
   **https://github.com/himan98hkt-prog/-/releases/tag/cardscan-android** 에 들어가
   *Assets* 의 `cardscan-v….apk` 를 눌러 내려받습니다.
   (cardscan 폴더가 바뀌어 올라갈 때마다 GitHub Actions 가 자동으로 새로 빌드해 이 주소에 올립니다.)
2. **설치** — 다운로드 알림을 누릅니다. "출처를 알 수 없는 앱" 경고가 나오면 *설정 → 이 출처 허용* 을 켜고 다시 누릅니다.
   Play 프로텍트 안내가 나오면 *무시하고 설치* 를 누릅니다 (스토어를 거치지 않은 직접 만든 앱이라 나오는 안내).
3. **명함 촬영** 탭에서 고객/거래처를 고르고 찍으면 끝 — 처음에 카메라·연락처 권한을 허용하세요.
   **API 키·회원가입·요금 없이** 바로 됩니다 (휴대폰 안에서 글자를 읽는 무료 인식).

> 업데이트: 새 APK 를 받아 기존 앱 위에 설치하면 저장된 명함이 그대로 유지됩니다.

## 아이폰에 설치하기 (무료 · 홈 화면 웹앱)

아이폰은 앱스토어 밖에서 앱을 설치하려면 유료 개발자 계정($99/년)이 필요해서,
같은 앱을 **웹앱**으로 만들어 Safari 에서 **"홈 화면에 추가"** 하는 방식으로 무료 제공합니다.
계정·컴퓨터·재설치 없이 아이콘을 눌러 앱처럼 씁니다.

1. 아이폰 **Safari** 로 **https://himan98hkt-prog.github.io/-/** 를 엽니다 (크롬이 아닌 Safari).
2. 아래 **공유 버튼(□↑)** → **홈 화면에 추가** → 추가.
3. 홈 화면의 **명함스캔** 아이콘으로 실행 → **명함 촬영** 탭에서 찍기.
   처음 한 번 문자 인식 엔진(약 10MB)을 받고, 이후에는 바로 인식합니다.

안드로이드 앱과의 차이 (아이폰 웹앱의 제약):

| | 안드로이드 앱 | 아이폰 웹앱 |
|---|---|---|
| 명함 인식 | 무료 (Google ML Kit) | 무료 (Tesseract — 휴대폰 안에서 처리) |
| 휴대폰 연락처 저장 | 자동 | 명함마다 **📇 아이폰 연락처에 저장** → 연락처 카드에서 "새로운 연락처 생성" (설정에서 전체 한 번에 옮기기도 가능) |
| 구글 시트·웹훅 | 자동 | 자동 |
| HubSpot·슬랙 직접 연동 | 자동 | 불가 (브라우저 보안 정책) — 웹훅(Zapier·Make)을 거치면 가능 |
| 명함 저장 위치 | 앱 저장소 | 이 아이폰의 Safari 저장소 (홈 화면 앱이면 유지됨). 구글 시트 연동을 켜 두면 백업 |

> 사이트 주소는 `cardscan/` 이 바뀌어 올라갈 때마다 GitHub Actions(`cardscan-web.yml`)가 자동으로 새로 배포합니다.
> 처음 한 번만 저장소 **Settings → Pages → Build and deployment → Branch: `gh-pages` / `(root)` → Save** 가 필요합니다.

## 구글 플레이스토어 출시·판매

등록정보·스크린샷·개인정보처리방침·심사 답변표·업로드용 AAB 빌드까지 [`store/`](store/README.md) 에 준비되어 있습니다.
순서·일정·테스트(12명 × 14일)·수익화 방법은 **[store/README.md](store/README.md)** 를 따라 하세요.

## 주요 기능 (안드로이드)

| | 기능 | 리멤버와 비교 |
|---|---|---|
| 📷 | **자동 테두리 인식 촬영** — Google 문서 스캐너로 명함을 찾아 반듯하게 펴고 그림자 제거, **앞·뒷면 함께** | 동등 |
| 🆓 | **무료 인식** — 휴대폰 안에서 처리(ML Kit), 인터넷·요금 없음, 사진이 밖으로 안 나감 | 리멤버는 서버 입력 |
| 🗂 | **앨범에서 여러 장 한 번에 등록** (최대 50장) — 애매한 명함은 `#확인필요` 그룹으로 | 동등 |
| 🔎 | **초성 검색**(ㅎㄱㄷ→홍길동), 메모·그룹·이전 회사로도 검색, 정렬(등록·이름·회사·수정) | 동등 이상 |
| ⭐ | **즐겨찾기·그룹(태그)**, 고객/거래처 구분, **회사별 보기**, 같은 회사 동료 보기 | 동등 |
| 📝 | **메모·미팅 기록** 타임라인 | 동등 |
| 📞 | **팔로업 알림** — "3일 뒤·1주 뒤" 연락할 날을 정하면 그날 아침 9시 알림 + 명함첩 맨 위 "오늘 연락할 사람" | **리멤버에 없음** |
| 🧭 | **경력 이력** — 같은 사람 명함을 다시 찍으면 이전 회사·직책을 기록 (이직·승진 추적) | 리멤버는 네트워크 기반 |
| ☎️ | **전화 올 때 회사명 표시** — 연락처 이름을 "홍길동 (한빛상사 팀장)" 으로 저장 (선택) | 동등 |
| 🔳 | **내 명함 QR** — 상대가 카메라로 찍으면 바로 연락처 저장, 받은 명함도 QR 로 전달 | 동등 |
| 📊 | **엑셀(CSV) 내보내기 무료**, **백업 파일/복원** (휴대폰 교체 대비) | 리멤버는 엑셀이 유료 |
| 🔗 | 연락처·구글 시트·HubSpot·웹훅(ERP)·슬랙 **자동 연동**, 실패 시 자동 재전송 | **리멤버에 없음** |

## 동작 방식

```
 휴대폰 카메라 ──► 자르기·축소(1600px JPEG)
                     │
                     ▼
        [기본·무료] 휴대폰 안 Google ML Kit 한국어 OCR → 규칙 분석(src/core/cardParser.ts)
        [선택·유료] Claude 비전 (claude-opus-5-5) — 앱 직접 호출 또는 Supabase 서버 경유
        → 이름·회사·부서·직책·휴대폰·전화·팩스·이메일·웹·주소
                     │
                     ▼
     번호 정리(+82→010-…), 이메일 소문자, 같은 사람(휴대폰/이메일) 찾기
                     │
     ┌───────────────┼────────────────┬───────────────┬──────────────┐
     ▼               ▼                ▼               ▼              ▼
 휴대폰 연락처     구글 시트         HubSpot CRM      웹훅(ERP 등)     슬랙 알림
 (중복이면 합침)  (id 로 행 갱신)   (이메일로 upsert) (JSON POST)     (첫 등록 시)
```

- **고객 / 거래처 / 기타** 구분을 고르고 찍습니다. 연동마다 어떤 구분을 보낼지 설정할 수 있습니다
  (예: 고객 → HubSpot, 거래처 → ERP 웹훅, 전부 → 구글 시트).
- **자동 저장**(기본 켬): 이름과 연락처가 읽히면 확인 화면 없이 바로 저장·연동합니다. 부족하면 확인 화면을 띄웁니다.
- **같은 사람**(휴대폰 번호나 이메일이 같음)의 명함을 다시 찍으면 새로 만들지 않고 최신 정보로 갱신합니다 — 이직·승진 반영.
- 연동이 실패하면(오프라인 등) 기록해 두었다가 **앱을 다시 열 때 자동 재전송**합니다. 상세 화면에서 개별 재시도도 됩니다.
- 명함 상세에서 바로 전화·문자·메일, vCard 공유가 됩니다.
- API 키·토큰·비밀키는 기기 보안 저장소(Android Keystore / iOS Keychain)에 보관합니다.

## 명함 인식 방식

| | **무료** — 기본 (안드로이드: ML Kit / 아이폰: Tesseract) | **Claude** (선택) | **내 서버** (선택) |
|---|---|---|---|
| 요금 | 없음 | 장당 약 $0.02~0.04 (추정) | 장당 약 $0.02~0.04 (추정) |
| 인터넷 | 필요 없음 | 필요 | 필요 |
| 사진 전송 | 휴대폰 밖으로 안 나감 | Anthropic 으로 전송 | 내 서버 → Anthropic |
| 정확도 | 일반적인 명함은 대부분 정확, 디자인이 복잡하거나 흐리면 일부 칸을 손으로 고쳐야 할 수 있음 | 복잡한 명함도 잘 읽음 | Claude 와 같음 |
| 준비 | 없음 | 앱에 Anthropic API 키 입력 | Supabase 함수 배포 |

무료 인식은 Google ML Kit(온디바이스, 무료 SDK)로 글자를 읽고 `src/core/cardParser.ts` 가
M/T/F 표기, (주)·주식회사, 팀·본부, 직급, 시·구·로 주소 같은 한국 명함 관례로 칸을 나눕니다.
인식이 틀린 칸은 상세 화면 **수정** 으로 고치면 연락처·연동에도 다시 반영됩니다.
유료 모드를 골라도 키나 서버 설정이 비어 있으면 무료 인식으로 동작합니다.

### 내 서버 모드 설정 (선택·유료, 약 10분)

필요한 것: [Supabase](https://supabase.com) 무료 계정, [Anthropic API 키](https://console.anthropic.com).

```bash
cd cardscan
npx supabase login
npx supabase link --project-ref <프로젝트 ref>          # Supabase 대시보드 URL 의 영문 ID
npx supabase secrets set ANTHROPIC_API_KEY=sk-ant-... APP_SHARED_SECRET=<아무 긴 문자열>
npx supabase functions deploy scan-card
```

앱 **설정·연동 → 명함 인식 → 내 서버** 에 입력합니다.

| 항목 | 값 |
|---|---|
| 서버 주소 | `https://<프로젝트 ref>.supabase.co/functions/v1/scan-card` |
| 앱 비밀키 | 위에서 정한 `APP_SHARED_SECRET` (서버는 이 값이 맞는 요청만 처리) |
| Supabase key | 비워 두어도 됩니다 (`anon`/publishable 키를 넣으면 함께 전송) |

## 개발자용: 직접 실행·빌드

```bash
cd cardscan
npm install
npx expo start          # 휴대폰에 Expo Go 앱을 설치하고 QR 코드를 찍으면 바로 실행
```

APK 는 `.github/workflows/cardscan-apk.yml` 이 GitHub 에서 빌드합니다(`expo prebuild` → `gradlew assembleRelease`).
Actions 탭의 **명함스캔 APK → Run workflow** 로 수동 빌드도 됩니다. EAS 를 쓰려면:

```bash
npx eas-cli@latest build --profile preview --platform android    # APK
npx eas-cli@latest build --profile production --platform ios     # App Store / TestFlight
```

- 현재 APK 는 Expo 템플릿의 기본 서명키로 서명됩니다 — 직접 설치(사이드로드)용으로는 문제없고 빌드가 바뀌어도 업데이트 설치가 됩니다.
  **Play 스토어에 올릴 때는** 자체 서명키(EAS 관리 키 등)로 바꾸세요.
- `app.json` 의 `android.package`/`ios.bundleIdentifier`(현재 `com.cardscan.app`)는 스토어 출시 전에 회사 도메인으로 바꾸세요.

## 연동 켜기

설정 방법과 전송 형식은 [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) 에 있습니다.

- 휴대폰 연락처 — 기본 켜짐, 권한만 허용
- 구글 시트 — [docs/google-sheets.gs](docs/google-sheets.gs) 를 시트에 붙여 웹 앱으로 배포
- HubSpot — Private App 토큰
- 웹훅 — 사내 ERP·그룹웨어, Zapier/Make/n8n 을 거치면 더존·세일즈포스·노션 등 거의 모든 시스템
- 슬랙 — Incoming Webhook 주소

연동마다 **테스트 전송** 버튼으로 샘플 명함(홍길동)을 보내 확인할 수 있습니다.

## 개발

```bash
npm test            # 단위 테스트 (번호·이름 정리, 중복 판정, 각 연동 요청 형식, 서버 함수)
npm run typecheck   # TypeScript
```

```
src/
  app/                    화면 (Expo Router)
    (tabs)/index.tsx        명함첩 — 검색, 고객/거래처 필터, 연동 상태 점
    (tabs)/scan.tsx         촬영 → 인식 → 자동 저장 / 확인 화면
    (tabs)/settings.tsx     명함 인식(무료/Claude/서버), 자동 저장, 연동별 설정·테스트
    review.tsx              인식 결과 확인·수정
    card/[id].tsx           상세, 전화/문자/메일, 수정, 연동 재시도, vCard 공유
  core/                   순수 로직 (테스트 대상)
    cardParser.ts           무료 인식 — OCR 줄 → 이름·회사·직책·부서·번호·주소 (규칙 기반)
    normalize.ts            전화번호·이름·이메일 정리, 서버 응답 검증
    mapping.ts              연락처/시트/HubSpot/웹훅/슬랙/vCard 변환, 중복 판정, 검색
    settings.ts             설정 기본값·병합, 구분별 연동 대상
  integrations/
    ocr.ts                  명함 인식 (무료: 기기 OCR+규칙 분석 / 유료: Claude 직접·서버)
    http.ts                 구글 시트·HubSpot·웹훅·슬랙
    deviceContacts.ts       휴대폰 주소록 (expo-contacts)
    sync.ts                 연동 실행·재시도
  storage/                명함(AsyncStorage)·사진(문서 폴더)·설정(SecureStore)
modules/card-ocr/       온디바이스 OCR — index.ts: 안드로이드(Kotlin, ML Kit 한국어 내장)
                        index.web.ts: 아이폰 웹앱(Tesseract 한국어+영어, 큰 글씨 한글 재인식)
scripts/pwa.mjs         웹 빌드를 아이폰 홈 화면 앱으로 마무리 (아이콘·manifest·인식 엔진 동봉)
supabase/functions/scan-card/   명함 인식 서버 (Deno, Anthropic SDK) — extract.ts 의 요청·해석 코드는 앱도 공유
```

## 알아둘 점

- 기본(무료) 인식은 사진을 휴대폰 밖으로 보내지 않습니다. Claude·내 서버 모드를 고르면 사진이 Anthropic 으로 전송되므로,
  그때는 사내 개인정보 처리 방침에 위탁 처리 사실을 반영하세요.
- 무료 인식은 안드로이드 설치 앱(ML Kit)과 아이폰 웹앱(Tesseract)에서 동작합니다. Expo Go 에서는 직접 입력 화면으로 넘어갑니다.
- 명함 데이터는 휴대폰 안(앱 저장소)에 있습니다. 휴대폰을 바꿀 때는 구글 시트 연동을 켜 두면 백업이 됩니다.
- 앱에서 명함을 지워도 연락처·연동 시스템에 이미 들어간 정보는 지우지 않습니다.
