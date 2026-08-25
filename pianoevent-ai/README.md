# PianoEvent AI

피아노학원 **정기 연주회 · 시즌 특강 올인원 기획** 도구.
학생 명단 하나로 연주 순서표 → 사회자 대본 → 모바일 초대장 → 참석 집계까지 한 번에 만듭니다.

```bash
npm install
npm run dev      # http://localhost:3000  (환경변수 없이 바로 전 기능 동작)
npm test         # 순수 로직 단위 테스트 62건
npm run build && npm run smoke   # 실제 서버를 띄워 원장 작업 흐름 26건 검증
```

> 환경변수를 하나도 설정하지 않아도 됩니다. Supabase 가 없으면 로컬 데모 저장소로, Gemini 키가 없으면
> 내장 규칙 엔진으로 자동 전환되어 **모든 화면이 그대로 동작**합니다.

---

## 1. 무엇이 자동으로 되는가

| 원장이 하던 일 | 이 도구에서 |
|---|---|
| 엑셀로 순서를 짜고 러닝타임을 손으로 계산 | 명단 붙여넣기 → **오프닝·초급·중급·앙상블·피날레 자동 배치 + 종료 시각 계산** |
| 곡 해설과 학생 소개 멘트를 밤새 작성 | 곡·작곡가·학생 특징을 엮은 **사회자 대본 곡별 자동 생성** |
| 순서표를 워드로 다시 옮겨 인쇄 | **A4 인쇄용 순서표** (브라우저 인쇄 → PDF 저장) |
| 초대장 이미지를 만들어 단톡방에 배포 | **모바일 초대장 링크 `/e/{id}`** + 카카오톡 공유 + 참석 회신 |
| 참석 인원을 카톡 답장으로 세기 | **실시간 참석 집계** (가정 수·총 인원·응원 메시지) |
| 시즌 특강 자료를 사서 짜깁기 | 테마 선택 → **주차별 계획서 + 인쇄용 활동지** 한 번에 |

### 순서 배치 규칙 (`lib/program/order.ts`)

1. **오프닝** — 짧고 안정적인 중급 곡 한 곡으로 무대의 긴장을 푼다.
2. **기초/초급 → 중급 → 듀엣·앙상블** — 난이도와 길이 오름차순.
3. **피날레** — 가장 어렵고 긴 솔로를 마지막에 남긴다.
4. **인접 중복 회피** — 같은 작곡가·같은 학생이 연달아 오면 같은 구간 안에서 자리를 바꾼다.
5. **시간 계산** — 곡 사이 전환 시간(기본 40초)을 더해 누적하고, 50분을 넘어가면 중간 휴식을 넣되
   마지막 곡 앞에는 넣지 않는다.
6. **경고** — 러닝타임 초과, 한 학생의 3회 이상 출연, 연속 출연, 10분 초과 곡, 작곡가 누락을 표시한다.

이 규칙 엔진은 **AI 없이 단독으로 완결**됩니다. Gemini 는 이 결과를 더 좋게 다듬는 역할이고,
호출이 실패하면 규칙 엔진 결과로 조용히 내려앉되 화면에 그 사실을 표시합니다.

---

## 2. 구조

```
app/
  page.tsx                        홈 · 진행 중인 행사
  events/                         행사 목록 · 생성 · 상세(명단/순서표 탭)
  events/[id]/program/print/      A4 인쇄용 순서표
  events/[id]/script/             사회자 대본 (전체 복사 · 인쇄)
  events/[id]/invite/             초대장 공유 + 참석 집계 + 미리보기
  e/[id]/                         공개 모바일 초대장 (로그인 불필요)
  seasons/                        시즌 특강 팩 (계획서 + 활동지 인쇄)
  settings/                       학원 정보 · 연결 상태 · 계정 삭제
  privacy/                        개인정보처리방침 (Play Console 등록용 URL)
  api/
    generate-program/             무상태 순서표 API (개발 지시서 Step 2 형태)
    events/[id]/program/          순서표 생성 + DB 확정 저장
    events/[id]/students/         엑셀 붙여넣기 파싱 · 명단 등록
    rsvp/                         학부모 참석 회신 (공개)
    season/                       시즌 특강 팩 생성
    account/delete/               계정·전체 데이터 삭제

lib/
  program/order.ts    순서 배치·러닝타임·경고 (순수 함수, 단위 테스트 대상)
  program/script.ts   사회자 대본 폴백 생성기 + 곡·작곡가 지식 베이스
  program/roster.ts   엑셀/CSV 붙여넣기 파서 (헤더 자동 인식, 시간 표기 해석)
  program/ai.ts       Gemini 프롬프트·응답 검증·폴백 결정
  season/             테마별 커리큘럼 템플릿 + AI 생성
  ai/gemini.ts        서버 전용 Gemini 래퍼 (타임아웃·JSON 추출)
  store/              저장소 파사드 — demo(파일) / supabase 드라이버 자동 선택

supabase/schema.sql                4개 테이블 + RLS + 계정 삭제 함수
supabase/functions/gemini-proxy/   모바일 앱용 API 키 은닉 프록시
```

---

## 3. 설정

`.env.example` 을 `.env.local` 로 복사해 필요한 값만 채웁니다.

| 변수 | 없을 때 동작 |
|---|---|
| `GEMINI_API_KEY` | 내장 규칙 엔진으로 순서표·대본 생성 (품질은 낮지만 항상 동작) |
| `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | `.data/store.json` 로컬 데모 저장소 사용 |
| `NEXT_PUBLIC_KAKAO_JS_KEY` | 링크 복사 · 기기 공유 시트로 대체 |
| `NEXT_PUBLIC_OPERATOR_NAME` / `NEXT_PUBLIC_CONTACT_EMAIL` | 개인정보처리방침에 안내 문구로 표시 |

### Supabase 붙이기

1. 프로젝트 생성 → SQL Editor 에서 `supabase/schema.sql` 실행
2. Project URL · anon key · service_role key 를 `.env.local` 에 입력
3. 재시작하면 설정 화면의 **데이터 저장소** 배지가 `Supabase PostgreSQL` 로 바뀝니다

`SUPABASE_SERVICE_ROLE_KEY` 는 RLS 를 우회하므로 **서버에만** 둡니다. 클라이언트에는 anon key 만 전달됩니다.

### 모델 이름에 대한 참고

개발 지시서는 `gemini-1.5-pro` / `gemini-1.5-flash` 를 명시하지만, 이 모델들은 신규 프로젝트에서
더 이상 제공되지 않을 수 있습니다. 그래서 기본값을 `gemini-2.5-pro` / `gemini-2.5-flash` 로 두고
`GEMINI_MODEL_PRO` · `GEMINI_MODEL_FLASH` 로 언제든 되돌릴 수 있게 했습니다.

---

## 4. 검증

```bash
npm test     # 62건 — 순서 배치, 시간 계산, 파서, 대본, AI 응답 방어 파싱, 집계
npm run smoke  # 26건 — 실제 서버에 요청해 원장·학부모 흐름 전체를 밟는다
```

스모크는 `.data` 를 임시로 옮겨 두고 돌기 때문에 실제 작업 데이터를 건드리지 않습니다.

---

## 5. 배포와 정책 준수

- [docs/DEPLOY.md](docs/DEPLOY.md) — Vercel 배포, Supabase 연결, 도메인·환경변수 체크리스트
- [docs/PLAY_COMPLIANCE.md](docs/PLAY_COMPLIANCE.md) — Google Play 필수 정책 대응 현황과 남은 작업

핵심 보안 원칙: **`GEMINI_API_KEY` 는 어떤 경우에도 클라이언트로 나가지 않습니다.**
웹은 서버 API Route 가, 모바일 앱은 `supabase/functions/gemini-proxy` 가 키를 대신 들고 호출합니다.
