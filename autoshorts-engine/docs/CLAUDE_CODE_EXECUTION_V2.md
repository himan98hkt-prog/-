# Claude Code 실행 가이드 v2 — AutoShorts Full SaaS

이 문서는 Claude Code에 그대로 전달해 **한 단계씩** 구현하기 위한 실행용 가이드다.

## A. 최초 1회 시작 방법

```bash
git fetch --all --prune
git checkout feat/autoshorts-commercial-saas
git pull
cd autoshorts-engine
```

Claude Code를 이 디렉터리에서 실행한다.

첫 메시지로 아래 Master Guard를 붙여 넣는다.

---

## Master Guard — 모든 Phase 공통

```text
당신은 AutoShorts 상용 SaaS의 Staff Engineer다.

반드시 먼저 다음 문서를 읽어라.
- docs/COMMERCIALIZATION_ROADMAP.md
- docs/DEVELOPMENT_PROMPTS.md
- docs/PRODUCT_BLUEPRINT_V2.md
- docs/CLAUDE_CODE_EXECUTION_V2.md

중요 원칙:
1. 기존 AutoShorts 엔진을 폐기하거나 처음부터 다시 만들지 않는다.
2. 현재 동작하는 pipeline/transcriber/ai_analyzer/video_renderer/subtitles/trend_finder/uploader 테스트 자산을 최대한 재사용한다.
3. 한 번에 한 Phase만 수행한다.
4. 현재 Phase의 GO 조건을 만족하지 못하면 다음 Phase를 시작하지 않는다.
5. main/default branch에 직접 작업하지 않는다.
6. public YouTube upload, 실제 결제, 실제 사용자 데이터 삭제 등 외부 부작용이 큰 행동은 자동 실행하지 않는다.
7. API key/OAuth token/payment secret은 코드·commit·log에 절대 남기지 않는다.
8. 경쟁 서비스의 HTML/CSS/카피/브랜드를 복제하지 않는다. UX 패턴만 참고해 독립 디자인을 만든다.
9. YouTube 영상은 권리 확인 없이 재사용 가능하다고 판단하지 않는다.
10. 모든 변경은 tests와 문서가 함께 있어야 한다.

각 Phase 작업 전:
- 현재 branch/HEAD 확인
- git status 확인
- 관련 기존 코드 audit
- 구현 계획 10줄 이내 작성

각 Phase 작업 후 반드시 아래 형식으로 보고하고 멈춰라.

PHASE:
STATUS: GO | NO-GO
SUMMARY:
CHANGED FILES:
TESTS:
E2E EVIDENCE:
SECURITY/PRIVACY:
KNOWN RISKS:
MANUAL CHECKS:
NEXT PHASE ENTRY CONDITIONS:
COMMIT(S):

내가 다음 Phase를 명시적으로 지시하기 전에는 다음 단계로 넘어가지 마라.
```

---

# Phase 0 — Productization Gate

기존 `DEVELOPMENT_PROMPTS.md`의 Prompt 0을 수행한다.

Claude Code 추가 지시:

```text
Phase 0만 수행하라.

특히 YouTube API quota 상수를 2026년 공식 정책 기준으로 재검증하라.
2026 granular quota에서 search.list와 videos.insert는 각각 별도 bucket으로 바뀌었으므로
과거 100/1600 point 가정을 그대로 유지하지 마라.

실제 credential이 필요한 검증은 자동 실행하지 말고 manual smoke command를 작성하라.
private upload 실제 검증이 끝나기 전에는 public/scheduled publish를 product promise로 만들지 마라.

완료 후 GO/NO-GO 보고하고 멈춰라.
```

---

# Phase 1 — Engine Service Boundary

```text
Phase 0 STATUS가 GO인 경우에만 수행하라.

기존 DEVELOPMENT_PROMPTS Prompt 1을 기반으로 구현한다.

추가 요구:
- SaaS가 기존 pipeline을 library/service로 호출할 수 있게 한다.
- JobSpec/JobResult/ProgressEvent를 JSON serializable contract로 고정한다.
- source rights 상태 필드를 추가한다.
  rights_status = owned | licensed | creative_commons | unverified
- unverified source는 production render/publish 전 approval gate가 필요하도록 contract에 표현한다.
- provider별 외부 호출을 adapter로 분리한다.
- 기존 CLI/Gradio는 regression 없이 계속 동작해야 한다.

완료 후 멈춰라.
```

---

# Phase 2 — SaaS Foundation

```text
Phase 1 GO 후에만 수행하라.

목표:
두 명 이상의 사용자가 독립적으로 브라우저에서 프로젝트를 만들고 worker job을 실행할 수 있는 기반을 만든다.

구조 권장:
apps/web      Next.js
apps/api      FastAPI
apps/worker   Python worker
packages/contracts 또는 동등 구조
기존 autoshorts Python engine은 재사용

필수:
- Auth
- User/Workspace/WorkspaceMember
- Project
- PostgreSQL migrations
- Object Storage abstraction
- presigned upload
- durable queue(Redis 기반 또는 동등)
- Worker
- Job progress
- workspace isolation
- usage_events/cost_events skeleton

DB 최소:
users
workspaces
workspace_members
projects
source_assets
transcripts
clip_candidates
render_jobs
render_outputs
usage_events
cost_events
rights_confirmations

E2E:
User A project → upload → job → result
User B → A project/file 접근 거부
3 jobs concurrent queue
browser close 후 worker 지속

결제/YouTube upload/trend UI는 아직 구현하지 마라.
완료 후 멈춰라.
```

---

# Phase 3 — Full Website Shell + Brand System

```text
Phase 2 GO 후 수행하라.

목표:
완전한 홈페이지 구성과 authenticated app shell을 만든다.
아직 모든 기능을 fake로 꾸미지 말고, 구현되지 않은 부분은 명확한 placeholder/feature flag로 둔다.

Public routes:
/
/trending
/reusable
/templates
/pricing
/private
/guides
/login
/signup
/terms
/privacy
/copyright
/contact

Authenticated routes:
/app/dashboard
/app/projects
/app/projects/new
/app/trending
/app/reusable
/app/channel
/app/competitors
/app/billing
/app/settings

UI 원칙:
- dark premium SaaS 스타일 가능
- 경쟁 서비스 디자인 그대로 복사 금지
- 자체 brand tokens, spacing, typography, color system
- responsive desktop/mobile
- keyboard/focus/accessibility
- loading/empty/error states

Landing page sections:
Hero
Create CTA
How it works
Trend preview
Reusable source safety preview
Example outputs
Features
Pricing preview
FAQ
Footer/legal

Navigation:
프로젝트 / 실시간 인기 / 재사용 소스 / 템플릿 / 요금제 / PRIVATE

Pricing은 아직 실제 결제와 연결하지 말고 entitlement schema를 읽는 presentation layer로 만든다.
PRIVATE는 CMS placeholder와 entitlement gate만 만든다.

테스트:
- route smoke
- responsive
- auth guard
- accessibility basic
- no competitor branding/text/assets

완료 후 screenshots 또는 Playwright evidence와 함께 멈춰라.
```

---

# Phase 4 — Core Create UX

```text
Phase 3 GO 후 수행하라.

목표:
웹에서 실제 사용 가능한 Upload → AI highlight → edit → render → download 흐름 완성.

화면:
1. New Project
2. Source upload / rights-approved source
3. Processing progress
4. Highlight candidates
5. Clip review/edit
6. Render
7. Result/download

Highlight card:
- preview
- start/end
- duration
- title
- highlight score
- reason
- selected state

Editor MVP:
- start/end
- title
- subtitle text
- caption preset
- caption size/position
- crop/blur
- preview
- rerender

기존 engine을 호출한다. 브라우저 request가 긴 FFmpeg 작업을 직접 기다리지 않게 queue/worker를 사용한다.

Instrumentation:
project_created
source_uploaded
processing_started
highlight_generated
highlight_selected
render_started
render_completed
download_clicked

금지:
CapCut/Premiere급 full timeline editor

완료 후 실제 샘플 영상 E2E와 실패 케이스를 기록하고 멈춰라.
```

---

# Phase 5 — Real-time Trend Intelligence

```text
Phase 4 GO 후 수행하라.

목표:
첨부 레퍼런스처럼 카테고리/언어/인기 기준별 인기 영상을 카드 그리드로 탐색하되,
독립적인 UI와 설명 가능한 scoring을 구현한다.

Data providers:
A. videos.list(chart=mostPopular, regionCode, videoCategoryId)
B. search.list for recent discovery
C. channel uploads playlist path for watched channels
D. videos.list statistics/contentDetails enrichment

매 요청마다 외부 API를 직접 때리지 말고 scheduled ingestion + cache + DB snapshot으로 설계한다.

DB:
trend_sources
trend_snapshots
trend_items
trend_metrics
trend_score_components

필터:
- 인기 급상승 추정
- 조회수 상위
- YouTube Most Popular
- Opportunity Score
- region
- category
- language preference
- duration
- Creative Commons only

카드:
rank
thumbnail
title
channel
views
published age
duration
trend status
trend score
license badge when known

TrendScore 구성요소:
view_velocity
freshness
engagement
subscriber_normalized
acceleration

시간별 snapshot이 있어야 acceleration/velocity를 계산할 수 있다.
UI에는 `최근 갱신 N분 전`을 표시한다.
`실시간`을 초단위 live라는 의미로 오인시키지 않는다.

Quota:
- API request budget을 추적한다.
- search.list 호출 budget 초과 시 graceful degradation.
- mostPopular/cache를 fallback으로 사용.

추천 카드의 `이 소스로 만들기`는 rights flow 없이 바로 다운로드/렌더하지 않는다.

완료 후 멈춰라.
```

---

# Phase 6 — Reusable / Creative Commons Source Library

```text
Phase 5 GO 후 수행하라.

목표:
재사용 후보 영상을 안전하게 탐색하고 attribution/rights 확인 후 프로젝트로 가져오는 기능을 만든다.

공식 YouTube API의 search.list videoLicense=creativeCommon을 사용한다.

절대 표현 금지:
- 저작권 100% 안전
- 무조건 재사용 가능
- 법적 문제 없음

UI 명칭:
`Creative Commons 표시 영상`
`재사용 후보`
`권리 확인 필요`

필수 metadata:
source_title
source_author/channel
source_url
video_id
license_type
license_checked_at
attribution_text
rights_status
user_confirmation_at

카드:
thumbnail
title
channel
views/date
Trend Score
CC BY badge
출처표기 필요
라이선스 상세
프로젝트로 가져오기

Import modal:
- 현재 API에서 확인된 license
- CC BY attribution 요구
- third-party music/visual 권리 가능성 안내
- 사용자가 권리/라이선스 확인 checkbox

표준 YouTube license는 자동으로 reusable로 분류하지 않는다.
사용자가 별도 서면 허가/소유권을 가진 경우에는 `licensed` 또는 `owned`로 확인 가능하게 한다.

자동 attribution generator를 만들되 사용자가 수정/확인할 수 있게 한다.

테스트:
creativeCommon filter
standard license exclusion
rights confirmation required
attribution persistence
license snapshot audit

완료 후 멈춰라.
```

---

# Phase 7 — YouTube Private-first Upload

```text
Phase 6 GO 후 수행하라.

기존 DEVELOPMENT_PROMPTS Prompt 4를 수행한다.

추가:
- rights_status=unverified인 project는 upload block
- user explicit approval required
- default private
- API project audit 상태를 config/admin에서 표시 가능하게 설계
- unverified API project 제한을 docs에 반영

실계정 public upload 자동 실행 금지.
완료 후 멈춰라.
```

---

# Phase 8 — Pricing, Billing, Entitlements

```text
Phase 7 GO 후 수행하라.

목표:
/pricing을 실제 plan entitlement와 payment state에 연결한다.

Plan 이름/가격 숫자는 코드에 산발적으로 하드코딩하지 않는다.
DB/config 기반으로 관리한다.

권장 entitlement:
processed_minutes
concurrent_jobs
retention_days
trend_basic
trend_advanced
reusable_library
private_content
youtube_upload
channel_intelligence
workspace_members
priority_queue

Plan 후보:
Trial
Creator
Pro
Agency

가격은 benchmark/cost ledger를 보고 확정한다.
경쟁 서비스 가격을 그대로 복제하지 않는다.

결제 provider abstraction을 먼저 만든다.
한국 시장 기준 PG/정기결제 requirements를 별도 ADR에 기록한다.

필수:
usage ledger
cost ledger
subscription state
payment webhooks idempotency
cancel/refund state model
upgrade/downgrade
limit warning/hard stop
admin reconciliation

UI:
pricing page
billing page
usage progress
upgrade CTA
payment status/error

실제 production charge는 staging/sandbox를 통과한 뒤 별도 승인 없이 실행하지 않는다.
완료 후 멈춰라.
```

---

# Phase 9 — PRIVATE + Guides + Retention Content

```text
Phase 8 GO 후 수행하라.

목표:
회원 전용 정보 허브를 만든다.

콘텐츠 종류:
- 재사용 후보 큐레이션
- 제작 노트
- 쇼츠 훅/제목/자막 가이드
- 카테고리별 사례
- 제품 업데이트/early access
- 월간 trend report

초기에는 실시간 채팅을 만들지 않는다.
CMS-lite로 시작한다.

DB:
private_posts
private_categories
private_entitlements

기능:
public preview
entitlement gate
post detail
search/category
admin draft/publish
scheduled publish optional
read analytics

SEO용 공개 guides와 유료 PRIVATE를 분리한다.
완료 후 멈춰라.
```

---

# Phase 10 — Channel Intelligence + Feedback Loop

```text
Phase 9 GO 후 수행하라.

목표:
제작 도구를 Growth Platform으로 완성한다.

사용자의 연결 채널에서 허용된 analytics 데이터를 수집한다.

기능:
channel summary
video performance
historical topic performance
shorts performance
competitor watchlist
opportunity score
next content recommendations

추천은 설명 가능해야 한다.
"조회수 보장" 표현 금지.

Closed loop:
Trend → Create → Publish → Analytics → Recommendation

추천 생성 시 실제 performance와 trend signals를 분리 저장한다.
완료 후 멈춰라.
```

---

# Phase 11 — Closed Beta / Production Gate

```text
기존 DEVELOPMENT_PROMPTS Prompt 7을 확장해 실행한다.

목표:
10~30명 closed beta를 안전하게 판매/운영할 수 있는지 최종 판정.

필수:
Terms
Privacy
Copyright/rights policy
billing terms/refund requirements
account deletion
file/project deletion
OAuth revoke
log redaction
backup/restore
rate limiting
abuse control
worker health
queue metrics
storage lifecycle
error monitoring
DB migration rollback
admin support flow

Fault tests:
worker kill
queue outage
DB transient error
storage timeout
LLM timeout
transcription failure
FFmpeg failure
duplicate job delivery
payment webhook duplicate
YouTube lost response

Beta metrics:
activation
first_render_time
job_success_rate
cost_per_processed_minute
highlight_accept_rate
regenerate_rate
download_rate
paid_conversion
7-day return

STATUS GO가 아니면 production launch 금지.
완료 후 멈춰라.
```

---

## B. 실제 운영 방식

Claude Code에는 항상 **Master Guard + 현재 Phase 하나만** 제공한다.

권장 commit:

```text
phase0/productization
phase1/engine-service
phase2/saas-foundation
phase3/web-shell
phase4/core-create
phase5/trend-intelligence
phase6/reusable-library
phase7/youtube-upload
phase8/billing
phase9/private-content
phase10/growth-loop
phase11/beta-gate
```

각 Phase 종료 후 ChatGPT에 Claude Code의 최종 보고서와 PR/commit을 가져와 코드 리뷰를 받은 뒤 다음 단계로 진행한다.
