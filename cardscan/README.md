# 명함스캔 (cardscan)

리멤버처럼 **명함을 찍으면 자동으로 읽어서 저장**하고, **휴대폰 연락처와 업무 시스템(구글 시트·HubSpot·ERP 웹훅·슬랙)에 자동 입력**하는 모바일 앱입니다.
iOS·Android 공용(Expo / React Native).

| 명함첩 | 촬영 | 상세·연동 상태 | 설정·연동 |
|---|---|---|---|
| ![](docs/images/list.png) | ![](docs/images/scan.png) | ![](docs/images/detail.png) | ![](docs/images/settings.png) |

## 동작 방식

```
 휴대폰 카메라 ──► 자르기·축소(1600px JPEG)
                     │
                     ▼
        명함 인식 서버 (Supabase Edge Function)
        Claude 비전 → JSON 스키마로 이름·회사·부서·직책·휴대폰·전화·팩스·이메일·웹·주소
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
- 토큰·비밀키는 기기 보안 저장소(iOS Keychain / Android Keystore)에 보관하고, **Claude API 키는 앱이 아닌 서버에만** 둡니다.

## 1. 명함 인식 서버 배포 (최초 1회, 약 10분)

필요한 것: [Supabase](https://supabase.com) 무료 계정, [Anthropic API 키](https://console.anthropic.com).

```bash
cd cardscan
npx supabase login
npx supabase link --project-ref <프로젝트 ref>          # Supabase 대시보드 URL 의 영문 ID
npx supabase secrets set ANTHROPIC_API_KEY=sk-ant-... APP_SHARED_SECRET=<아무 긴 문자열>
npx supabase functions deploy scan-card
```

배포가 끝나면 앱 **설정·연동 > 명함 인식 서버** 에 입력합니다.

| 항목 | 값 |
|---|---|
| 서버 주소 | `https://<프로젝트 ref>.supabase.co/functions/v1/scan-card` |
| 앱 비밀키 | 위에서 정한 `APP_SHARED_SECRET` (서버는 이 값이 맞는 요청만 처리) |
| Supabase key | 비워 두어도 됩니다 (`anon`/publishable 키를 넣으면 함께 전송) |

**서버 연결 확인** 을 눌러 성공이 뜨면 준비 끝입니다.
인식 모델은 `claude-opus-5-5` 입니다 (`supabase/functions/scan-card/extract.ts` 의 `MODEL`).

## 2. 앱 실행

```bash
cd cardscan
npm install
npx expo start          # 휴대폰에 Expo Go 앱을 설치하고 QR 코드를 찍으면 바로 실행
```

### 설치 파일(APK/스토어) 만들기

```bash
npx eas-cli@latest login
npx eas-cli@latest build --profile preview --platform android    # 바로 설치 가능한 APK
npx eas-cli@latest build --profile production --platform ios     # App Store / TestFlight
```

`app.json` 의 `ios.bundleIdentifier`, `android.package`(현재 `com.cardscan.app`)는 출시 전에 회사 도메인으로 바꾸세요.

## 3. 연동 켜기

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
    (tabs)/settings.tsx     인식 서버, 자동 저장, 연동별 설정·테스트
    review.tsx              인식 결과 확인·수정
    card/[id].tsx           상세, 전화/문자/메일, 수정, 연동 재시도, vCard 공유
  core/                   순수 로직 (테스트 대상)
    normalize.ts            전화번호·이름·이메일 정리, 서버 응답 검증
    mapping.ts              연락처/시트/HubSpot/웹훅/슬랙/vCard 변환, 중복 판정, 검색
    settings.ts             설정 기본값·병합, 구분별 연동 대상
  integrations/
    ocr.ts                  인식 서버 호출
    http.ts                 구글 시트·HubSpot·웹훅·슬랙
    deviceContacts.ts       휴대폰 주소록 (expo-contacts)
    sync.ts                 연동 실행·재시도
  storage/                명함(AsyncStorage)·사진(문서 폴더)·설정(SecureStore)
supabase/functions/scan-card/   명함 인식 서버 (Deno, Anthropic SDK)
```

## 알아둘 점

- 명함 사진은 인식을 위해 서버(Supabase → Anthropic API)로 전송됩니다. 사진과 명함 데이터는 서버에 저장하지 않습니다.
  고객 개인정보를 다루므로 사내 개인정보 처리 방침에 위탁 처리 사실을 반영하세요.
- 명함 데이터는 휴대폰 안(앱 저장소)에 있습니다. 휴대폰을 바꿀 때는 구글 시트 연동을 켜 두면 백업이 됩니다.
- 앱에서 명함을 지워도 연락처·연동 시스템에 이미 들어간 정보는 지우지 않습니다.
