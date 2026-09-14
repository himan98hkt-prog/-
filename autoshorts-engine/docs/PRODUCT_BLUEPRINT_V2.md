# AutoShorts 상용 SaaS Product Blueprint v2

작성 목적: 기존 AutoShorts-Engine을 유지하면서, EasyCut류의 완성형 웹 SaaS 경험에 `실시간 인기 + 재사용 허용 소스 + Growth Intelligence + 요금제 + PRIVATE 콘텐츠`를 통합한다.

> 디자인/문구/코드는 경쟁 서비스를 복제하지 않는다. 공개 기능에서 UX 패턴만 참고하고 우리만의 브랜드/정보구조/카피를 만든다.

## 1. 최종 제품 정의

제품은 단순 `Video → Shorts` 변환기가 아니라 아래 폐쇄 루프를 제공한다.

`Trend Discovery → Reusable/Owned Source → Opportunity Score → Create → Highlight → Review/Edit → Render → Download/Private Upload → Analytics → Next Recommendation`

초기 상용화에서는 기능을 단계적으로 열고, 핵심 생성 흐름의 안정성이 검증되기 전에는 고급 기능을 한꺼번에 넣지 않는다.

## 2. 완전한 홈페이지/서비스 정보구조

### Public Marketing Site

- `/` 랜딩
  - Hero: URL/파일 입력 CTA
  - 핵심 가치: "잘될 순간을 찾고 쇼츠로 만든다"
  - 예시 결과
  - Trend Intelligence 미리보기
  - 사용 방법 3단계
  - 신뢰/안전/권리 안내
  - 요금제 요약
  - FAQ
  - Footer: Terms / Privacy / Copyright / Contact

- `/trending` 실시간 인기
- `/reusable` 재사용 허용 소스
- `/templates` 템플릿
- `/pricing` 요금제
- `/private` 회원 전용 콘텐츠/업데이트/가이드
- `/guides` 공개 가이드/SEO 콘텐츠
- `/login`, `/signup`

### Authenticated App

- `/app/dashboard`
- `/app/projects`
- `/app/projects/new`
- `/app/projects/:id`
- `/app/trending`
- `/app/reusable`
- `/app/channel`
- `/app/competitors`
- `/app/billing`
- `/app/settings`

## 3. 실시간 인기(Trend Intelligence)

### 목표

사용자가 카테고리/언어/지역/길이/라이선스/인기 기준을 필터해 "지금 반응이 강한 영상"을 탐색하고 바로 프로젝트 생성으로 연결한다.

### 공식 데이터 경로

1. YouTube `videos.list(chart=mostPopular)`
   - 지역/카테고리별 인기 차트
   - API cost가 낮아 기본 인기 피드에 적합
2. YouTube `search.list`
   - 최근 업로드, 키워드, 조회수 정렬 등 discovery
   - 2026 granular quota 체계에서 Search Queries 별도 bucket(기본 100 calls/day)이므로 캐시/스케줄링 필수
3. Channel uploads 경로
   - `channels.list` → uploads playlist → `playlistItems.list`
   - 경쟁채널/사용자 지정 채널 모니터링에 적합
4. `videos.list` statistics/contentDetails
   - 조회수, 좋아요, 댓글, 길이 등 enrichment

### "실시간" 정의

진짜 초단위 실시간이라고 광고하지 않는다. 데이터 수집 주기를 UI에 명시한다.

권장:
- 기본 인기: 10~30분 캐시
- 중요 watchlist: 15~60분 갱신
- 비용/쿼터에 따라 가변

UI 표기 예:
- `최근 갱신 8분 전`
- `급상승 추정`
- `인기 차트`

### 필터

- 인기 기준
  - 급상승 추정
  - 조회수 상위
  - YouTube Most Popular
  - Opportunity Score
- 지역
  - KR / JP / US / 기타
- 언어
  - 한국어 우선 / 일본어 우선 / 전체
- 카테고리
  - 전체 / 엔터테인먼트 / 게임 / 스포츠 / 음악 / 뉴스·정치 / 과학·기술 / 교육 / 라이프스타일 등
- 길이
  - Shorts 제외 / 3~10분 / 10~20분 / 20분+
- 재사용 조건
  - 전체
  - Creative Commons만
  - 내가 소유/연결한 채널만

### DB

- `trend_sources`
- `trend_snapshots`
- `trend_items`
- `trend_metrics`
- `trend_score_components`

시간별 snapshot을 저장해 단순 누적 조회수가 아니라 velocity를 계산한다.

### 점수

초기 설명 가능한 score:

`TrendScore = ViewVelocity + Freshness + Engagement + SubscriberNormalized + Acceleration`

`OpportunityScore = Trend + ChannelFit + HistoricalPerformance + Competition + Freshness`

점수 구성요소를 모두 저장하고 UI에서 이유를 보여준다. "예상 조회수"를 보장하지 않는다.

## 4. 재사용 허용 소스(Reusable Sources)

### 기술적으로 가능

YouTube `search.list`는 `videoLicense=creativeCommon` 필터를 지원한다. 따라서 CC BY로 표시된 영상만 별도 검색할 수 있다.

### 제품상 매우 중요한 안전 원칙

`재사용 허용`을 "법적으로 100% 안전" 또는 "저작권 문제 없음"으로 표현하지 않는다.

UI 명칭 권장:
- `Creative Commons 표시 영상`
- `재사용 후보`
- `권리 확인 필요`

사용자가 실제 제작에 사용하기 전 다음을 확인한다.

- API에서 확인한 license type
- 영상 제목/저자/원본 URL
- 수집 시각
- Attribution 텍스트 자동 생성
- 사용자 `권리 및 라이선스 확인` 체크

CC BY는 attribution이 필요하므로 생성된 프로젝트 metadata에 다음을 보관한다.

- source title
- source author/channel
- source URL
- license snapshot
- attribution text

표준 YouTube license 영상은 "재사용 허용"으로 분류하지 않는다. 사용자가 명시적인 별도 권리를 가지고 있는 경우에만 `rights_confirmed`로 가져오게 한다.

### 추천 UX

카드:
- 썸네일
- 제목
- 채널
- 조회수/게시일
- Trend Score
- `CC BY` badge
- `출처표기 필요`
- `라이선스 확인`
- `프로젝트로 가져오기`

프로젝트 생성 전 modal:
- 현재 확인된 라이선스
- attribution 안내
- 제3자 음악/영상 요소 등 별도 권리 가능성 안내
- 사용자 확인 checkbox

## 5. 쇼츠 제작 Core UX

기존 AutoShorts 엔진 재사용:

- ingest
- faster-whisper
- Gemini/offline highlight
- clip normalize
- FFmpeg 9:16
- ASS subtitles
- render

웹 UX:

1. Source
2. Processing
3. Highlights
4. Review/Edit
5. Render
6. Download / Private YouTube Upload

Highlight card:
- preview
- start/end
- title
- highlight score
- score breakdown
- reason
- select / reject / regenerate

MVP editor:
- start/end
- title
- subtitle text
- caption preset
- caption position/size
- crop/blur
- re-render

Full timeline editor는 초기 범위에서 제외한다.

## 6. 요금제/판매

가격 숫자는 beta 원가 측정 후 확정한다. 처음부터 경쟁사의 숫자를 복제하지 않는다.

과금 단위 권장:
- `processed source minutes`를 기본 단위로 사용
- 추가로 concurrency, storage retention, Growth features를 plan entitlement로 분리

예시 구조:

### Free / Trial
- 10~20분 체험 처리
- watermark 또는 제한된 export(사업전략에 따라 선택)
- 기본 trend preview
- CC 후보 preview

### Creator
- 월 처리시간
- 동시작업 1
- 프로젝트 30일
- 기본 trend filters
- download

### Pro
- 더 높은 처리시간
- 동시작업 2~3
- advanced trend
- channel intelligence
- private YouTube upload
- longer retention

### Agency
- 다중 workspace/channel
- 높은 concurrency
- team member
- priority queue
- export/report

DB:
- `plans`
- `plan_entitlements`
- `subscriptions`
- `usage_ledger`
- `cost_ledger`
- `billing_events`

필수: provider 비용, render CPU, storage, egress를 기록해 plan별 gross margin 계산 가능해야 한다.

## 7. PRIVATE / 멤버십 콘텐츠

목표: 제품 이용률과 retention을 올리는 membership center.

콘텐츠 유형:
- 재사용 후보 큐레이션
- 제작 노트
- 훅/제목 가이드
- 카테고리별 사례
- 신규 기능 사전 공개
- 월간 트렌드 리포트

구현은 CMS-lite로 시작한다.

DB:
- `private_posts`
- `private_categories`
- `private_entitlements`

Markdown/MDX 기반 또는 관리자 UI에서 작성. 초기에 실시간 채팅은 만들지 않는다. 사용자가 실제로 원할 때 커뮤니티/채팅을 확장한다.

## 8. Dashboard

표시:
- 이번 달 사용량 / 남은 처리시간
- 진행 중 작업
- 최근 프로젝트
- 오늘의 트렌드
- CC BY 재사용 후보
- 내 채널 추천
- 최근 upload 성과(Phase later)
- plan/upgrade CTA

## 9. Admin/Ops

상용화에 반드시 필요:

- 사용자/워크스페이스 조회
- job retry/cancel
- queue depth
- error rate
- quota usage
- storage usage
- subscription state
- payment reconciliation
- content moderation/abuse flag
- private content publishing
- feature flag

관리자 기능은 일반 사용자 라우트와 권한을 완전히 분리한다.

## 10. 데이터/인프라 권장 구조

```text
apps/
  web/       Next.js
  api/       FastAPI
  worker/    Python

packages/
  engine/    기존 AutoShorts domain engine
  contracts/

infra/
  migrations/
  docker/
```

서비스:
- PostgreSQL
- Redis/durable queue
- S3/R2 compatible object storage
- Error monitoring
- Metrics/logs

## 11. 개발 순서

### Phase 0 — Productization Gate
기존 DEVELOPMENT_PROMPTS Prompt 0 수행. quota/API 정책, 실제 private upload, benchmark 검증.

### Phase 1 — Engine Service Boundary
기존 엔진을 Job 기반 worker-callable service로 감싼다.

### Phase 2 — SaaS Foundation
Auth/Workspace/Project/Postgres/Storage/Queue/Worker.

### Phase 3 — Full Website Shell
랜딩, navigation, pricing placeholder, trending/reusable/private placeholder, authenticated app shell.

### Phase 4 — Core Create UX
Upload → highlight → edit → render → download.

### Phase 5 — Trend Intelligence
mostPopular + scheduled discovery + snapshot scoring + filters.

### Phase 6 — Reusable Source Library
Creative Commons discovery + rights/attribution workflow.

### Phase 7 — YouTube private upload
Web OAuth, encrypted token, explicit approval.

### Phase 8 — Billing & Entitlements
Pricing, usage, payment, limits, margin tracking.

### Phase 9 — PRIVATE content + Guides
회원 콘텐츠/CMS/업데이트.

### Phase 10 — Growth Feedback Loop
Channel analytics → performance → next recommendation.

### Phase 11 — Closed Beta / Production Gate
fault tests, legal pages, deletion, privacy, backups, monitoring, beta metrics.

## 12. 개발 Gate 원칙

각 Phase는 다음 형식으로 끝나야 한다.

- STATUS: GO / NO-GO
- CHANGED FILES
- TESTS
- E2E EVIDENCE
- SECURITY CHECK
- KNOWN RISKS
- MANUAL CHECKS
- NEXT PHASE ENTRY CONDITIONS

GO가 아니면 다음 Phase를 시작하지 않는다.

## 13. 핵심 차별화

경쟁 포지셔닝은 "쇼츠를 자동으로 잘라주는 서비스"가 아니라 다음으로 잡는다.

**"지금 뜨는 기회를 찾고, 권리를 확인한 소스로 쇼츠를 만들고, 결과를 학습해 다음 콘텐츠를 추천하는 AI YouTube Growth Platform."**
