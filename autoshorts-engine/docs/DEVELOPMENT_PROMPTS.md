# AutoShorts 상용 SaaS — 단계별 개발 프롬프트

이 문서는 Claude Code 또는 Codex에서 **한 단계씩** 실행하기 위한 프롬프트 모음이다.

공통 원칙:

- 기준 브랜치: `feat/autoshorts-commercial-saas`
- 기존 AutoShorts 엔진을 최대한 재사용한다.
- 한 번에 모든 Phase를 구현하지 않는다.
- 각 Phase는 테스트/문서/rollback 가능 상태로 끝낸다.
- 실제 공개 YouTube 업로드는 자동 실행하지 않는다.
- secret/API key/token을 코드나 로그에 남기지 않는다.
- 기존 CLI 기능 regression을 막는다.

---

## Prompt 0 — Productization Gate

```text
당신은 AutoShorts-Engine의 상용화 담당 Staff Engineer다.

Repository:
himan98hkt-prog/-

작업 브랜치:
feat/autoshorts-commercial-saas

먼저 autoshorts-engine/docs/COMMERCIALIZATION_ROADMAP.md를 읽고,
현재 PR #8 코드와 실제 파일을 기준으로 Phase 0 Productization Gate만 수행하라.

목표:
상용 SaaS 개발을 시작하기 전에 기존 엔진의 사실관계, 테스트 기준선, 업로드 정책,
실제 실행 위험요소를 확정한다.

수행할 작업:

1. 전체 AutoShorts 소스와 tests를 다시 audit한다.
2. README/시작하기/uploader/tests에 존재하는 YouTube quota 관련 상수와 설명을
   공식 최신 문서 기준으로 검증하고, 오래된 가정이 있으면 수정한다.
3. quota 값은 가능한 한 정책/설정 계층으로 분리해 하드코딩 의존성을 줄인다.
4. 기존 454개 수준의 테스트가 현재 HEAD에서 실제로 몇 개인지 실행하여 기록한다.
5. lint/type/static check가 없다면 기존 구조를 과도하게 바꾸지 않는 범위에서
   최소 품질 gate를 제안하라.
6. 실제 네트워크/API credential이 필요한 테스트는 자동으로 public 동작시키지 말고
   smoke-test script와 명확한 수동 체크리스트를 만든다.
7. private upload 실기 검증 절차를 작성한다.
8. 10/30/60분 영상 benchmark script를 추가해 처리시간, peak memory, output size,
   stage별 소요시간을 기록할 수 있게 한다.
9. source ownership/rights confirmation이 필요한 지점을 코드와 UI 요구사항으로 정리한다.
10. 결과를 docs/PHASE0_PRODUCTIZATION_REPORT.md에 기록한다.

금지:
- SaaS UI 개발 시작 금지
- DB/Auth/결제 구현 금지
- 기존 pipeline 대규모 리팩터링 금지
- public upload 실행 금지

완료 조건:
- 기존 테스트 green
- quota 정책 검증 및 필요한 수정 완료
- private-upload smoke checklist 존재
- benchmark 도구 존재
- Phase 1에 넘길 위험 목록과 기술 부채가 명확함

작업 후:
변경 파일, 테스트 결과, 남은 위험요소, Phase 1 Go/No-Go를 보고하고 멈춰라.
```

---

## Prompt 1 — Engine Service Boundary

```text
Phase 0가 Go인 경우에만 실행한다.

AutoShorts-Engine을 CLI/Gradio 전용 프로그램에서 SaaS worker가 호출할 수 있는
재사용 가능한 engine/service 구조로 바꿔라.

목표:
기존 기능을 깨지 않고 서버 작업(Job) 단위로 실행 가능한 경계를 만든다.

구현 요구사항:

1. JobSpec
   - source
   - project_id
   - workspace_id
   - render options
   - clip options
   - language
   - provider settings reference

2. JobResult
   - status
   - clips
   - outputs
   - timings
   - warnings
   - error code

3. ProgressEvent
   - stage
   - percent
   - message
   - timestamp

4. 현재 run_pipeline을 바로 삭제하지 말고 service layer로 감싼다.
5. CLI는 service layer를 호출하도록 점진적으로 변경한다.
6. 작업 디렉터리/출력 디렉터리 의존을 명시적으로 주입한다.
7. stage별 idempotency를 정의한다.
8. cancellation token 또는 cooperative cancellation point를 설계한다.
9. timeout/retry 대상과 retry 금지 오류를 구분한다.
10. FastAPI 최소 API를 추가한다.

Endpoints:
POST /jobs
GET /jobs/{job_id}
POST /jobs/{job_id}/cancel

현재 단계에서는 DB 없이 in-memory/local test adapter를 사용해도 된다.
단, 이후 PostgreSQL adapter로 교체 가능한 interface를 사용한다.

테스트:
- 기존 테스트 전부
- service unit tests
- API contract tests
- 같은 Job 재실행 idempotency test
- cancel test
- render failure propagation test

완료 후 architecture decision을
`docs/PHASE1_ENGINE_SERVICE.md`에 기록하고 멈춰라.
```

---

## Prompt 2 — SaaS Foundation

```text
Phase 1 완료 후 실행한다.

목표:
두 명 이상의 실제 사용자가 브라우저를 통해 독립적으로 프로젝트를 생성하고,
영상 처리 job을 서버에서 실행할 수 있는 SaaS 기반을 만든다.

권장 구조:

apps/web      Next.js
apps/api      FastAPI
apps/worker   Python worker
packages/engine 또는 기존 autoshorts engine

기술 선택은 현재 저장소와 배포 복잡도를 검토해 확정하되,
불필요한 프레임워크 추가를 피하라.

필수 기능:

1. Authentication
2. Workspace
3. Project
4. PostgreSQL
5. Object Storage abstraction
6. Presigned upload
7. Redis 기반 queue 또는 동등한 durable queue
8. Worker
9. Job 상태 저장
10. 진행률 API
11. 사용자별 데이터 격리
12. 최소 Dashboard

DB 최소 모델:
users
workspaces
workspace_members
projects
source_assets
clip_candidates
render_jobs
render_outputs
usage_events
cost_events

보안 요구사항:
- 모든 tenant data는 workspace_id 경계를 가진다.
- 다른 workspace의 project/job/file 접근을 integration test로 막는다.
- local path를 사용자에게 직접 노출하지 않는다.
- secrets는 DB 평문 저장 금지.

E2E 시나리오:
User A 로그인 → 프로젝트 생성 → 영상 업로드 → Job 실행 → 결과 다운로드
User B 로그인 → User A 리소스 접근 시 403/404

동시 작업 3건을 queue에 넣어 처리한다.
브라우저를 닫아도 작업이 계속되어야 한다.

이 Phase에서는 결제와 YouTube upload를 구현하지 않는다.

완료 후 `docs/PHASE2_SAAS_FOUNDATION.md`에 운영 방법과 E2E 결과를 기록하라.
```

---

## Prompt 3 — EasyCut급 Core UX

```text
목표:
기술 데모가 아니라 일반 사용자가 설명 없이 사용할 수 있는 쇼츠 제작 UX를 만든다.

참고 제품의 UX 원칙은 참고하되 디자인/코드/문구를 복제하지 않는다.
우리만의 독립 UI를 만든다.

필수 화면:

1. Login
2. Dashboard
3. Create Project
4. Upload / Source Input
5. Processing
6. Highlight Candidates
7. Clip Review/Edit
8. Render Result
9. Download

Create 화면의 핵심 행동은 하나로 단순화한다.

[영상 업로드 또는 권리 확인된 source]
             ↓
       [AI 쇼츠 만들기]

Highlight 화면:
- 3~5개 후보
- start/end
- title
- score
- reason
- preview
- 선택/제외

MVP 편집 기능:
- start/end 조정
- 제목 수정
- 자막 텍스트 수정
- subtitle preset
- subtitle position
- crop/blur
- re-render

금지:
- Premiere/CapCut 수준 full timeline editor
- 다중 트랙 편집기
- 과도한 animation builder

UX 지표를 instrumentation 가능하게 한다.
- project_created
- source_uploaded
- processing_started
- highlight_selected
- render_completed
- download_clicked

E2E 테스트와 실제 10개 샘플 영상 수동 QA checklist를 만든다.

완료 후 screenshots/UX notes를 포함해 `docs/PHASE3_CORE_UX.md` 작성.
```

---

## Prompt 4 — YouTube Private-first Integration

```text
목표:
로컬 Desktop OAuth 방식을 SaaS Web OAuth 방식으로 전환하고,
사용자가 검토한 영상만 자신의 YouTube 채널에 private 업로드할 수 있게 한다.

기존 uploader.py의 metadata sanitize, upload request, 오류 분류 로직은 재사용 가능한지 분석한다.

필수:

1. OAuth web flow
2. callback validation/state/PKCE 또는 적절한 CSRF 보호
3. refresh token encrypted storage
4. channel connection status
5. disconnect/revoke flow
6. private upload only as default
7. user explicit approval gate
8. resumable upload
9. retry/reconciliation
10. audit log

절대 하지 말 것:
- 사용자 승인 없는 public upload
- token 로그 출력
- refresh token 평문 저장
- 실패 후 무조건 새 upload 생성

테스트:
- OAuth mock integration
- token refresh
- revoked token
- upload retry
- lost response reconciliation
- duplicate-click idempotency

실계정 smoke test는 private 영상 1개로 수행하도록 별도 manual checklist를 작성한다.

완료 후 `docs/PHASE4_YOUTUBE_PRIVATE_UPLOAD.md` 작성.
```

---

## Prompt 5 — Trend & Growth Intelligence

```text
목표:
단순 Video→Shorts 도구에서 "잘될 콘텐츠를 찾아 제작하는" Growth Product로 확장한다.

기존 trend_finder.py를 재사용하되 UI/DB/API에서 직접 호출하지 않도록 service/provider 계층을 만든다.

구현:

1. Trend Provider
2. Channel Profile
3. Competitor Channel
4. Trend Item
5. Opportunity Score
6. AI Recommendation
7. 추천 → Create Project 원클릭 연결

Opportunity Score는 설명 가능한 구조여야 한다.
예:
Trend 25
Freshness 15
ChannelFit 25
HistoricalPerformance 20
Competition 15

각 score component를 DB와 API에서 별도로 보관한다.
단일 magic number만 저장하지 않는다.

UI:
- 오늘의 기회
- 내 채널 추천
- 경쟁채널 outlier
- 추천 이유
- "이 주제로 만들기"

초기 버전에서는 예측 조회수를 확정적으로 표현하지 않는다.
"가능성/기회 점수"로 표현한다.

완료 후 `docs/PHASE5_GROWTH_INTELLIGENCE.md` 작성.
```

---

## Prompt 6 — Billing, Usage & Unit Economics

```text
목표:
서비스 사용량과 실제 원가를 추적하고 유료 plan을 적용한다.

먼저 결제 provider 추상화를 만들고 한국/해외 타깃에 따라 provider를 선택한다.

Plan 초안:
FREE
CREATOR
PRO
AGENCY

반드시 구현:

1. entitlement
2. monthly usage
3. processing minutes 또는 credits
4. usage ledger
5. cost ledger
6. plan limits
7. soft warning
8. hard limit
9. billing webhook idempotency
10. admin reconciliation

cost_events 예:
- transcription_seconds
- llm_input_tokens
- llm_output_tokens
- render_cpu_seconds
- storage_gb_days
- egress_bytes

프로젝트/사용자/워크스페이스 단위 원가를 계산할 수 있어야 한다.

테스트:
결제 성공 → plan 변경 → 사용 → limit → renewal
중복 webhook
실패 webhook
refund/cancel

완료 후 `docs/PHASE6_BILLING.md` 작성.
```

---

## Prompt 7 — Closed Beta Release Gate

```text
목표:
10~30명 대상 비공개 베타를 안전하게 시작할 수 있는 상태를 만든다.

기능 추가보다 안정성/운영 준비에 집중한다.

필수 release gate:

- Terms
- Privacy Policy 요구사항 체크리스트
- copyright/source rights confirmation
- account deletion
- project/file deletion
- token revocation
- log redaction
- backup/restore
- Sentry 또는 동등 error tracking
- metrics
- worker health
- queue depth
- storage cleanup
- DB migration rollback
- rate limit
- abuse controls

대시보드 운영 지표:
activation
first_render_time
job_success_rate
render_duration
cost_per_processed_minute
highlight_accept_rate
regenerate_rate
download_rate
private_upload_rate
7-day return

배포 전에 staging에서 fault test를 수행한다.

- worker kill
- Redis outage
- DB transient failure
- storage timeout
- provider timeout
- duplicate job delivery
- upload response loss

결과를 `docs/PHASE7_BETA_RELEASE_REPORT.md`로 작성하고
Go/No-Go를 명확히 보고하라.
```

---

## Prompt 8 — Analytics Feedback Loop

```text
Closed Beta에서 core workflow가 검증된 이후에만 실행한다.

목표:
제작 결과의 실제 성과를 수집해 다음 콘텐츠 추천에 반영하는 폐쇄 루프를 만든다.

흐름:
Publish
→ Analytics Snapshot
→ Performance Normalization
→ Pattern Analysis
→ Recommendation
→ New Project

가능한 데이터만 공식 API/사용자 권한 범위에서 수집한다.

분석 예:
- topic
- hook style
- clip duration
- upload time
- title pattern
- retention/watch metrics
- engagement

AI는 인과관계를 단정하지 말고
"관찰된 상관/패턴"과 "실험 제안"을 구분한다.

UI:
What worked
What underperformed
What to test next
Next 10 ideas

A/B 실험은 처음부터 자동 public posting하지 않는다.
사용자 승인을 요구한다.

완료 후 `docs/PHASE8_FEEDBACK_LOOP.md` 작성.
```

---

# 매 Phase 공통 종료 프롬프트

각 Phase 개발 마지막에 아래 프롬프트를 추가로 실행한다.

```text
이번 Phase 구현을 release-review하라.

1. git diff 전체 리뷰
2. security regression
3. secret leakage
4. tenant isolation
5. idempotency
6. retry behavior
7. failure path
8. 기존 테스트
9. 신규 테스트
10. 문서 일치 여부
11. 불필요한 dependency
12. dead code
13. 사용자 데이터 삭제 가능성
14. 실제 운영 시 비용 폭증 가능성

문제가 있으면 고치고 테스트를 다시 실행하라.

마지막 출력은 아래 형식:

PHASE:
STATUS: GO / NO-GO
TESTS:
NEW FILES:
CHANGED FILES:
KNOWN RISKS:
MANUAL CHECKS:
NEXT PHASE ENTRY CONDITIONS:

GO가 아니면 다음 Phase 코드를 작성하지 마라.
```
