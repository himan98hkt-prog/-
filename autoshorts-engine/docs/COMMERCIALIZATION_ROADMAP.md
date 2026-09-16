# AutoShorts-Engine 상용화 개발 로드맵

작성일: 2026-09-14
기준 커밋: `488b33efd5281b0184c5c9aa41035c3de1b8f4bd` (PR #8 head)

## 1. 현재 코드 상태 요약

AutoShorts-Engine은 이미 **로컬 프로토타입 수준을 넘어선 영상 처리 엔진**이다.

재사용 가치가 높은 구성요소:

- `pipeline.py`: ingest → transcribe → analyze → render 오케스트레이션
- `downloader.py`: URL/로컬 소스 ingest
- `transcriber.py`: faster-whisper 전사
- `ai_analyzer.py`: Gemini + 오프라인 fallback, 클립 보정/중복 제거
- `video_renderer.py` + `ffmpeg_tools.py`: 9:16 렌더링과 FFmpeg 실행
- `subtitles.py`: ASS 자막 생성
- `trend_finder.py`: YouTube 최근 영상 탐색/점수화
- `uploader.py`: OAuth 기반 업로드, private 기본값
- `automation.py`, `scheduler.py`, `state.py`: 로컬 자동 실행과 이력
- 테스트 스위트와 GitHub Actions

하지만 현재 제품 형태는 **1인 PC에서 실행하는 CLI/Gradio 도구**다. SaaS 판매를 위해서는 웹 제품 계층이 추가되어야 한다.

현재 상용화에 부족한 핵심 계층:

- 사용자 계정/조직/워크스페이스
- PostgreSQL 기반 영속 데이터
- Object Storage(S3/R2 계열)
- Background queue/worker
- Web API
- SaaS용 웹 UI
- 다중 사용자 격리
- Web OAuth 및 토큰 암호화
- 사용량/원가/요금제/결제
- 운영 모니터링/오류 추적
- 프로젝트/클립 편집/검토 승인 흐름
- 데이터 보존/삭제/개인정보 운영 정책

## 2. 즉시 수정해야 할 중요한 발견

### YouTube 업로드 quota 가정이 현재 공식 문서와 다름

현재 `uploader.py`는 `videos.insert = 1,600 units`, `10,000 / 1,600 = 하루 6건`으로 모델링되어 있다.

2026-09-14 기준 Google 공식 Quota Calculator / `videos.insert` 문서는 `videos.insert`가 별도 Video Uploads quota bucket에서 **1 call = 1 unit**, 기본 **100 uploads/day**로 설명한다.

따라서 상용화 브랜치에서 다음을 먼저 처리한다.

1. 하드코딩된 1,600 / 6건 가정을 제거한다.
2. quota 정책을 코드 상수보다 설정/capability로 분리한다.
3. API 오류 응답을 최종 진실(source of truth)로 취급한다.
4. README/시작하기/테스트의 오래된 quota 문구를 갱신한다.

참고:
- https://developers.google.com/youtube/v3/determine_quota_cost
- https://developers.google.com/youtube/v3/docs/videos/insert

### SaaS 업로드는 YouTube API audit 준비가 필요

Google 공식 `videos.insert` 문서에 따르면 2020-07-28 이후 생성된 **미검증 API 프로젝트**의 업로드는 private로 제한될 수 있으며, 제한 해제를 위해 API compliance audit이 필요하다.

즉, 실제 판매 전에 "public/scheduled publish"를 상용 기능으로 약속하기보다 다음 순서로 간다.

- Beta: private upload + 사용자 검토
- OAuth consent / privacy policy / data handling 정비
- API audit 준비
- audit 완료 이후 public/scheduled publish 확대

## 3. 제품 방향

목표는 EasyCut과 같은 단순 `Video → Shorts` 도구에 머물지 않는다.

최종 제품 흐름:

`Trend → Opportunity → Source → Highlights → Edit/Review → Render → Publish → Analytics → Next Recommendation`

초기 MVP는 반드시 좁게 잡는다.

### MVP v1 정의

사용자가 웹에서:

1. 로그인
2. 프로젝트 생성
3. 본인 소유 영상 업로드 또는 권리 확인된 소스 입력
4. AI 전사
5. 하이라이트 3~5개 추천
6. 후보별 Viral/Highlight score 확인
7. 9:16 자동 렌더
8. 자막/제목/시작·종료 구간 수정
9. 재렌더
10. 다운로드
11. 프로젝트 기록 확인

YouTube 업로드는 MVP v1.1에서 private-first로 추가한다.

## 4. 목표 아키텍처

기존 Python 엔진은 버리지 않고 **도메인 엔진**으로 유지한다.

```text
apps/
  web/                Next.js 사용자 UI
  api/                FastAPI REST API
  worker/             영상 처리 worker

packages/
  engine/             기존 AutoShorts Python 엔진
  contracts/          Job/Event/API schema

infra/
  docker/
  migrations/
  deployment/

services
  PostgreSQL          사용자/프로젝트/작업/사용량
  Redis               queue / job coordination
  Object Storage      source/render/subtitle/thumbnail
```

초기에는 monorepo로 운영해도 되지만, 현재 GitHub 저장소의 루트에는 다른 학원 관리 앱이 함께 있으므로 상용화 직전에는 **AutoShorts 전용 저장소로 분리**하는 것을 권장한다.

## 5. 데이터 모델 초안

- `users`
- `workspaces`
- `workspace_members`
- `projects`
- `source_assets`
- `transcripts`
- `clip_candidates`
- `render_jobs`
- `render_outputs`
- `youtube_connections`
- `publish_jobs`
- `analytics_snapshots`
- `trend_items`
- `usage_events`
- `cost_events`
- `subscriptions`
- `audit_logs`

모든 고객 데이터 행에는 `workspace_id`를 포함하고 접근 경계를 강제한다.

## 6. 개발 단계

### Phase 0 — Productization Gate / 1~3일

목표: 기존 엔진의 상용화 전제 오류를 제거하고 기준선을 고정한다.

작업:

- YouTube quota 상수/문서/테스트 수정
- PR #8의 실제 테스트 재실행
- private 실제 업로드 1건 검증
- Windows + Linux smoke test
- 10분/30분/60분 영상 처리시간·CPU·메모리·디스크 기록
- 한 영상당 비용 계산 포맷 정의
- source rights 확인 정책 초안
- 기존 PR의 base/head 정리

Go gate:

- 기존 테스트 green
- private 업로드 실제 성공
- 30분 원본에서 실패 없이 결과 생성
- 실패 시 재현 가능한 로그 확보

### Phase 1 — Engine Service Boundary / 3~7일

목표: CLI에 묶인 엔진을 서버 worker가 호출할 수 있는 형태로 만든다.

작업:

- `JobSpec`, `JobResult`, `ProgressEvent` 계약 추가
- pipeline에서 홈 디렉터리/전역 상태 의존 제거
- 파일 경로 대신 Storage abstraction 추가
- stage별 idempotency 정의
- 취소/timeout/retry 안전성 추가
- FastAPI 최소 API 추가
  - `POST /jobs`
  - `GET /jobs/{id}`
  - `POST /jobs/{id}/cancel`
- 기존 CLI는 새 service layer를 호출하도록 유지

Go gate:

- CLI regression 없음
- API로 같은 파이프라인 실행 가능
- job 재시작 시 중복 렌더 방지

### Phase 2 — Multi-user SaaS Foundation / 1~2주

목표: 여러 사용자가 동시에 쓸 수 있는 웹 제품 골격.

작업:

- Next.js 웹 앱
- Auth
- PostgreSQL
- Workspace/Project
- presigned upload
- Object Storage
- Redis queue
- Worker 프로세스
- 프로젝트 상태 UI
- 진행률 polling 또는 SSE
- 사용자별 quota/limit 초안

Go gate:

- 서로 다른 두 계정이 데이터/파일을 볼 수 없음
- 3개 동시 작업이 정상 queue 처리
- 브라우저 닫아도 작업 지속

### Phase 3 — EasyCut급 Core UX / 1~2주

목표: 판매 가능한 핵심 사용 경험.

화면:

- Dashboard
- Create Project
- Upload / source input
- Processing
- Highlight candidates
- Clip Review
- Caption editor
- Render result
- Download

편집 기능 MVP:

- 시작/종료 시간
- 제목
- 자막 텍스트
- 자막 스타일 preset
- 자막 위치
- crop/blur
- 9:16
- regenerate

처음부터 CapCut/Premiere 수준 timeline editor를 만들지 않는다.

Go gate:

- 신규 사용자가 도움 없이 업로드 → 쇼츠 다운로드 완료
- 10개 테스트 원본에서 후보 품질 수동평가

### Phase 4 — YouTube Connection / Private-first / 1주

목표: SaaS용 OAuth와 검토 기반 업로드.

작업:

- Desktop OAuth 제거/격리
- Web OAuth callback
- refresh token 암호화 저장
- 연결 채널 표시
- private upload
- 실패/재시도/reconciliation
- upload audit log
- 사용자 승인 없이 public 업로드 금지

Go gate:

- 실제 계정 2개 private upload 성공
- 토큰 갱신 성공
- 토큰 폐기/재연결 동작

### Phase 5 — Trend + Channel Intelligence / 1~2주

목표: EasyCut 대비 차별화.

작업:

- 기존 `trend_finder.py`를 provider/service로 분리
- 내 채널 성과 분석
- 경쟁 채널 후보 분석
- Opportunity Score
- Highlight Score breakdown
- 추천 주제 → Create Project 연결

추천 점수 예시:

```text
Opportunity =
  Trend 25%
  Freshness 15%
  Channel Fit 25%
  Historical Performance 20%
  Competition 15%
```

Go gate:

- 추천에서 클릭 한 번으로 프로젝트 생성
- 점수 계산 근거를 UI에서 설명 가능

### Phase 6 — Billing / Usage / Unit Economics / 1주

목표: 실제 판매.

작업:

- Free / Creator / Pro / Agency plan
- 처리 분(minute) 또는 credit 과금
- usage ledger
- cost ledger
- LLM/STT/render/storage 원가 기록
- hard/soft limit
- 결제 webhook idempotency

Go gate:

- 결제 → entitlement → 사용 → 제한 흐름 E2E 통과
- 사용자별 gross margin 계산 가능

### Phase 7 — Closed Beta / 2~4주

목표: 10~30명의 실제 유료/테스트 고객으로 제품 검증.

측정:

- activation rate
- 첫 쇼츠 생성까지 시간
- processing success rate
- 평균 render time
- 평균 원가/처리분
- highlight 선택률
- regenerate 비율
- 다운로드/업로드 전환률
- 7일 재방문

출시 전 필수:

- Terms
- Privacy Policy
- 저작권/권리 확인 UI
- 데이터 삭제
- 장애 대응
- Sentry/metrics/logging
- backup/restore

### Phase 8 — Analytics Feedback Loop / 이후

목표: `만들기`가 아니라 `성장`을 파는 제품으로 진화.

- 업로드 성과 수집
- CTR/Retention/Watch Time 등 분석 가능한 범위 연동
- 성공/실패 패턴 설명
- 다음 아이디어 자동 추천
- 제목/길이/훅/게시시간 실험
- 사용자별 학습 프로필

## 7. 현재 코드에서 그대로 살릴 것

강하게 유지:

- `Transcript`, `Clip` 도메인 모델
- pipeline의 stage separation
- Gemini 실패 시 offline fallback
- clip boundary normalize 로직
- FFmpeg renderer
- ASS subtitle generator
- trend scoring 기본 구조
- private-by-default upload 정책
- secret logging 방지
- heavy dependency lazy import
- 기존 unit/integration test 자산

## 8. 교체 또는 격리할 것

상용 SaaS 경로에서 교체:

- Gradio → Next.js
- `history.json` → PostgreSQL
- 로컬 `work/`, `output/` → ephemeral worker + object storage
- desktop `client_secret.json` / local token → Web OAuth + encrypted DB secret
- local scheduler → server scheduler/queue
- 순차 로컬 렌더 → queue worker
- 사용자 입력 API key → 서버 provider 계정 또는 BYOK 정책을 명확히 분리

## 9. 제품 판매를 위한 우선순위

P0:
- 안정적인 ingest/transcribe/highlight/render
- account/project/storage/queue
- download
- 비용 추적

P1:
- private YouTube upload
- basic editor
- subscription/usage

P2:
- trend intelligence
- channel analytics
- recommendation loop

P3:
- advanced editor
- agency collaboration
- multi-channel automation

## 10. 첫 유료 베타의 성공 기준

상용화의 첫 성공은 기능 수가 아니라 다음 숫자로 판단한다.

- 10명 이상 실제 사용자
- 70% 이상 첫 프로젝트 완성
- 95% 이상 render job 성공
- 10분 이내 첫 결과(원본 길이에 따라 별도 SLA)
- 사용자 1인당 처리 원가 추적 가능
- 최소 3명 이상 재사용
- 최소 1명 이상 실제 결제 의사/결제

이 기준을 통과한 뒤 Trend/Analytics를 크게 확장한다.
