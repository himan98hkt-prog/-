# CLAUDE.md — 명함스캔(CardScan) 프로젝트 안내 (AI 도우미용)

명함을 찍으면 휴대폰 안에서 읽어(무료·오프라인) 연락처와 업무 시스템(구글 시트·HubSpot·웹훅·슬랙)에 자동 입력하는 앱.
Expo SDK 57 · React Native 0.86 · expo-router · TypeScript. 안드로이드 앱 + 아이폰 홈 화면 웹앱(같은 코드).
사용자는 한국어로 대화한다. 사용자에게 보이는 설명·커밋 메시지·코드 주석은 한국어로 쓴다.
사람용 전체 인수인계: `HANDOVER.md`. Expo 일반 규칙: `AGENTS.md` (Expo 문서는 기억 대신 버전별 문서 확인).

## 명령 (이 폴더에서)
- `npm run check` — 타입검사 + 테스트(vitest). **작업을 마치기 전에 반드시 통과시킬 것**
- `npm run web` — 웹 미리보기 / `npm run android:dev` — 폰에 개발 빌드 (Expo Go 불가: 자체 네이티브 모듈)
- `npm run android:clean` — prebuild --clean (app.json·플러그인 변경 후)
- 패키지 추가: `npx expo install <pkg>` (`.npmrc` legacy-peer-deps=true 유지)

## 구조
- `src/app/` 화면 (expo-router). `_layout.tsx`: ProProvider > StoreProvider > LanguageGate(언어 바뀌면 key 로 다시 그림) > Stack
- `src/core/` 순수 로직(테스트 대상): `cardParser.ts`(한국 명함, 한글이 있으면), `cardParserLatin.ts`(한글 없는 명함 — libphonenumber-js/max + 줄 점수), `normalize.ts`, `mapping.ts`, `organize.ts`, `pro.ts`, `settings.ts`, `types.ts`
- `src/integrations/` `ocr.ts`(scanCardImage: device|direct|server, region 전달), `sync.ts`/`http.ts`(커넥터), `deviceContacts.ts`
- `src/ui/` `store.tsx`(명함 상태·addCard·동기화, 무료 한도 시 ProLimitError), `pro.tsx`(usePro: isPro/requirePro/결제 화면), `billing.ts`(expo-iap, `.web.ts` 는 끔), `theme.ts`(Ink & Gold 디자인 토큰, Pretendard)
- `src/i18n/` `t('한국어 문장', {1: 값})` — 한국어 문장이 열쇠, 영어는 `en.ts`. `core.ts` 는 순수(테스트·core 에서 import), `index.ts` 는 expo-localization
- `modules/card-ocr/` 로컬 Expo 모듈(Kotlin): ML Kit 한국어 인식 + 구글 문서 스캐너. 웹은 `index.web.ts`(Tesseract)
- `plugins/withUploadSigning.js` 업로드 키 env 가 있으면 release 서명
- `store/` 플레이스토어 자료, `scripts/pwa.mjs` 아이폰 웹앱 마무리
- CI: `../.github/workflows/cardscan*.yml` (APK→Releases `cardscan-android`, AAB→Artifacts, 웹앱→gh-pages)

## 규칙
- 화면 문구는 반드시 `t()`. 파일 수준 라벨 맵(KIND_LABEL 등)은 정의는 한국어 그대로, 쓰는 곳에서 `t(MAP[k])`. 새 문장은 `src/i18n/en.ts` 에 영어 추가 — 누락 시 `tests/i18n.test.ts` 실패. `t` 이름을 콜백 변수로 쓰지 말 것(가림)
- core/integrations 에서는 `../i18n/core` 를 import (expo 의존 없게)
- 명함 분석 수정은 실패 사례를 테스트 견본으로 먼저 추가 (`tests/cardParser.test.ts`, `tests/cardParserEn.test.ts`). 한국 경로를 바꾸면 기존 한국 테스트 전부 통과해야 함
- 무료 원칙: 기본 인식은 온디바이스. 유료 API 는 사용자가 켤 때만
- 원본 명함 사진이 있으면 그대로 보여 줌(`CardHero`). 디지털 명함은 사진 없을 때만
- Pro 경계(`src/core/pro.ts`): 무료 50장(같은 사람 갱신은 무제한). 저장한 명함 보기·수정·백업은 언제나 무료. 외부 연동·CSV·여러 장·연속 촬영은 Pro. 결제는 `EXPO_PUBLIC_STORE=play` 빌드에서만 켜짐(개인 APK·웹은 전부 열림)
- 네이티브 설정은 `app.json`·config plugin 으로만. `android/`·`ios/` 는 생성물(커밋 금지)
- 비밀값(업로드 키 jks, 토큰)은 절대 커밋 금지 (`.gitignore` 에 *.jks)
- 코드 모양: Prettier (`.prettierrc`: printWidth 160, 작은따옴표)

## 알려진 사항
- Tesseract(웹) 인식은 "5층"을 "55"로 읽는 등 한국 주소 숫자 오인식이 있음 (안드로이드 ML Kit 와 별개)
- 플레이용 패키지 이름은 `io.github.himan98hktprog.cardscan`(워크플로가 바꿈), 직접 설치 APK 는 `com.cardscan.app`
- 남은 일 목록: `HANDOVER.md` 10장
