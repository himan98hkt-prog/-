# CLAUDE.md — 학원 관리노트 (AI 도우미용)

전 계열 학원·공부방(특히 피아노학원)용 원생·출결·수강료 관리 앱. 프레임워크 없는 바닐라 JS + Vite, PWA.
Lite(`lite.html`) = IndexedDB(Dexie) 완전 오프라인, Pro(`index.html`) = 같은 화면 + Supabase 동기화.
사용자(판매자이자 개발자)는 한국어로 대화한다. 화면 문구·커밋 메시지·코드 주석·문서는 한국어로 쓴다.
쓰는 사람은 컴퓨터가 익숙하지 않은 원장님이다 — 화면 문구는 전문용어 없이 쉬운 말로.

사람용 안내: `docs/LOCAL-DEV.md`(내 PC 개발), `README.md`(전체), `docs/SALES.md`(판매 점검).
`cardscan/` 은 별개 앱(명함스캔, Expo)이다 — 그 폴더에서 작업할 때는 `cardscan/CLAUDE.md` 를 따른다.

## 명령 (저장소 맨 위 폴더에서)
- `npm run check` — 테스트 + 빌드. **작업을 마치기 전에 반드시 통과시킬 것**
- `npm start` — 개발 서버 + 브라우저(`/lite.html`). `npm run dev` 는 브라우저를 열지 않는다
- `npm run smoke` — 실제 브라우저 시나리오(첫 화면·체험·인증·출결·교재 진도·백업…). **화면·흐름을 바꿨으면 돌릴 것**
- `npm run perf` — 원생 1,000 · 출결 20만 건에서 모든 화면 1초 이내 (`--skip-seed` 로 재측정)
- `npm run shots -- piano` — `screenshots/` 에 전 화면 캡처 (눈으로 확인할 때)
- `npm run test:plugin` — 퍼널모아 플러그인(PHP) 점검. PHP + sqlite3 확장이 있어야 함 (없으면 `npm test` 의 교차 검증도 건너뜀)
- `npm run demo` — `dist-demo/` 파일 하나짜리 체험판 · `npm run plugin` — `dist-plugin/` 플러그인 zip
- 브라우저 검사는 Playwright 크로미움 → 윈도우 Edge / 맥 Chrome 순으로 찾는다(`scripts/lib/browser.mjs`). 없으면 `npx playwright install chromium`

## 구조
- `src/core/` 순수 로직(전부 단위 테스트 대상, DOM 금지): `license.js`·`license-piano.js`(인증키), `fees.js`(청구·할인), `todo.js`(오늘 할 일), `books.js`(교재·진도), `onboarding.js`(시작 가이드), `store.js`(구매 주소·체험 안내), `templates.js`(문자 문구), `customfields.js`(학습 기록 항목) …
- `src/data/` `db.js`(Dexie 스키마), `repo.js`(화면은 이것만 쓴다 — 캐시 + 쓰기 후 이벤트), `sync.js`(Pro), `seed.js`(샘플 학원 5종·성능 더미)
- `src/ui/` `shell.js`(사이드바·탭·라우팅·안내 띠·도움말), `activation.js`(첫 화면·인증·메일 링크), `dom.js`(`h()` 헬퍼·modal·toast), `views/*.js`(화면 하나 = `render(root, ctx)`)
- `src/styles.css` 디자인 토큰(`:root`)과 전체 스타일. 브랜드 색 파생값은 `branding.js` 가 실행 중에 넣는다
- `integration/funnelmoa/` 결제 → 인증키 자동 발송 워드프레스 플러그인(PHP) + 점검(`tests/run.php`)
- `integration/piano/` 피아노 관리노트 앱에 붙이는 키 인정 패치
- `tests/` vitest, `scripts/` 검사·빌드 스크립트(`lib/` 공용), `docs/` 문서

## 꼭 지킬 것
- `LICENSE_SALT`(license.js), `PIANO_SALT`·`PIANO_CHARS`(license-piano.js), 플러그인 `class-ank-keys.php` 의 같은 값은 **절대 바꾸지 말 것** — 이미 판매된 키가 전부 열리지 않게 된다. 키 규칙을 고치면 JS·PHP 양쪽과 `tests/license*.test.js`·`tests/funnelmoa-plugin.test.js` 가 함께 맞아야 한다
- `tools/keygen.html`·플러그인 zip·웹훅 비밀값은 판매자 전용. 고객 배포 경로에 두지 말 것
- 피아노 관리노트 원본 소스(`index.html` v3.9 등)는 저작권 문제로 **저장소에 커밋 금지**. 패치 검증은 `node scripts/verify-piano-patch.mjs <파일>` 로 로컬에서만
- Supabase `service_role` 키를 프런트에 넣지 말 것. `.env` 는 커밋 금지(`.env.example` 만)
- Lite 는 자료를 `localStorage` 에 두지 않는다(IndexedDB 만). 세션·화면 설정 정도만 예외
- 출결·수납은 전체를 읽지 말 것 — 월·반 단위 인덱스 범위 질의만(`docs/ARCHITECTURE.md`). 성능 기준이 깨지면 `npm run perf` 가 실패한다
- 원생 `custom` 의 `_` 로 시작하는 키(`_books` 등)는 예약 항목. 원생 수정 저장 시 `keepReserved()` 로 이어 붙여야 지워지지 않는다
- 브라우저 기본 창(`alert`·`confirm`·`prompt`)을 쓰지 말 것 — 뜨지 않는 환경이 있다. `confirmDialog`·`modal` 사용
- 새 화면 동작은 `scripts/smoke.mjs` 에 시나리오를 추가한다. 샘플 학원은 평일에만 수업이 있으니 요일에 기대지 말 것(`showBoard()` 참고)

## 커밋
- 한국어로 "무엇을 왜" 를 쓴다. 작업 브랜치에서 하고, 기본 브랜치 반영은 PR 로
