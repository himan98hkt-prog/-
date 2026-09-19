# Phase 2 — SaaS Foundation (ADR / 인계 문서)

상태: **완료** — 실엔진 E2E 증거를 확보했고 GO/NO-GO 보고서를 작성했다
(`docs/PHASE2_GO_NO_GO.md`). 남은 항목은 아래 "남은 일" 로 좁혀졌고 모두
Phase 3 이후 또는 배포 전 과제다.

목표(명세): *두 명 이상의 사용자가 독립적으로 브라우저에서 프로젝트를 만들고
worker job 을 실행할 수 있는 기반을 만든다.*

---

## 1. 의존 방향

```
saas  ──▶  autoshorts        (한 방향. 엔진은 saas 를 모른다)
```

엔진은 Phase 1 에서 만든 `autoshorts.contracts` / `autoshorts.service` 경계로만
호출한다. 그래서 CLI(`autoshorts …`)와 Gradio UI 는 SaaS 계층 없이 그대로 돈다.

| 프로세스 | 진입점 | 하는 일 |
|---|---|---|
| API | `apps/api/main.py` (`uvicorn apps.api.main:app`) | 인증·검증·크레딧 예약·큐 삽입까지. **렌더하지 않는다.** |
| Worker | `apps/worker/main.py` (`python -m apps.worker.main`) | 큐에서 꺼내 엔진 실행, 진행률·산출물·정산 기록 |
| DB | PostgreSQL 16 | 작업 상태 + 큐 + 원장 (같은 트랜잭션) |

---

## 2. 결정과 이유

### 2.1 durable queue 를 Redis 가 아니라 PostgreSQL `SKIP LOCKED` 로

명세는 "Redis 기반 **또는 동등**"을 허용한다. PostgreSQL 을 고른 이유:

1. **원자성** — `render_jobs` INSERT 와 `job_queue` INSERT 가 같은 트랜잭션이다.
   Redis 면 "큐에는 있는데 DB 에는 없는" 상태가 반드시 생기고, 막으려면 outbox
   패턴을 따로 만들어야 한다.
2. **재수거** — lease 만료 회수가 UPDATE 한 줄이다. Redis 는 sorted set + 별도
   reaper 프로세스가 필요하다.
3. **운영 부담** — PostgreSQL 은 이미 필수다. 인프라를 하나 더 늘리지 않는다.

보장은 **at-least-once**. 멱등성은 `render_jobs.idempotency_key` 의 부분 유니크
인덱스와 엔진의 단계별 캐시가 담당한다.

### 2.2 ORM 을 쓰지 않는다

이 계층에서 가장 중요한 성질이 workspace 격리인데, ORM 이 조건을 숨기면 위험하다.
모든 조회에 `WHERE workspace_id = %s` 가 눈에 보이게 남는다.

### 2.3 격리는 두 겹

1. **질의 수준** — 저장소 메서드가 `workspace_id` 를 **필수 인자**로 받는다.
   빠뜨리면 타입 오류가 나지 조용히 성공하지 않는다.
2. **권한 수준** — `saas.tenancy.require_role`.

없는 자원과 남의 자원은 **같은 404** 로 답한다(403 이면 "그 ID 는 존재한다"가
새어나간다). 소속은 맞지만 역할이 모자라면 403 이다.

### 2.4 비밀번호·토큰

- `hashlib.scrypt` (표준 라이브러리). 파라미터를 해시 문자열에 같이 저장해서
  나중에 비용을 올려도 기존 해시가 검증된다.
- 세션 토큰은 **원문을 저장하지 않는다.** DB 에는 SHA-256 지문만 남는다.
- 로그인 실패는 이유를 구분해 알려주지 않고, 계정이 없어도 해시 검증을 한 번
  돌려 응답 시간 차이를 줄인다.

### 2.5 크레딧 (Master Guard 11)

```
제출   → reserve  (잔액 → 예약, 총액 불변)
성공   → commit   (실제 사용분만 차감, 나머지는 반환)
실패   → release  (전액 반환)
취소   → release
중복   → reserve 를 아예 하지 않는다
```

- 잔액 검사는 `UPDATE … WHERE credit_balance >= %s` 로 한다. 읽고-확인하고-쓰면
  동시 요청 두 개가 같은 잔액을 보고 둘 다 통과한다(스레드 10개로 검증함).
- `credit_ledger` 에 `UNIQUE (job_id, entry_type)` 을 걸어 재시도가 두 번 차감하지
  못하게 한다.

### 2.6 presigned upload

원본 영상은 수백 MB 다. API 가 바이트를 중계하면 수평 확장이 막힌다.

- `LocalPresigner` — 자체 호스팅용. HMAC-SHA256 서명 안에 키·크기 상한·만료가
  묶여 있어서 티켓을 고쳐 다른 경로에 쓸 수 없다. 수신은 `PUT /v1/uploads/{id}`.
- `S3Presigner` — S3/R2/MinIO 용 SigV4 presigned PUT. boto3 없이 표준
  라이브러리로만 만들어 서명 규칙이 이 파일 안에서 읽히고 테스트된다.
  **주의: 크기 상한은 서명이 아니라 버킷 정책으로 걸어야 실효가 있다.**

크기 상한은 Content-Length 헤더가 아니라 실제로 흘러온 바이트로 판단하고,
넘으면 쓰다 말고 지운다.

---

## 3. 스키마 (`saas/migrations/0001_initial.sql`, 19 tables)

명세 필수 12종: `users` `workspaces` `workspace_members` `projects`
`source_assets` `transcripts` `clip_candidates` `render_jobs` `render_outputs`
`usage_events` `cost_events` `rights_confirmations`

추가 7종: `sessions` `project_revisions` `upload_tickets` `job_queue`
`job_progress_events` `credit_ledger` `schema_migrations`

규칙 셋:
1. 사용자 데이터가 들어가는 모든 표가 `workspace_id` 를 **직접** 갖는다.
2. 상태 문자열은 `CHECK` 로 고정한다.
3. 금액은 정수(크레딧 / 마이크로달러)로만 저장한다.

MASTER_V3 Phase 2 추가 요구 반영:
- **usage ledger / cost ledger** — `usage_events`, `cost_events`
- **refundable/reserved credits 상태** — `workspaces.credit_reserved` + `credit_ledger`
- **media asset provenance** — `source_assets.origin/source_url/uploaded_by/checksum_sha256`
- **job idempotency key** — `render_jobs.idempotency_key` + 부분 유니크 인덱스
- **project version/revision** — `projects.revision` + `project_revisions`

마이그레이션 실행기는 Alembic 을 쓰지 않는다. `pg_advisory_lock` 으로 동시 실행을
막고, 이미 적용된 파일의 체크섬이 바뀌면 거부한다.

---

## 4. 명세가 요구한 E2E — 현재까지의 증거

| 명세 항목 | 상태 | 증거 |
|---|---|---|
| User A project → upload → job → result | 통과 | `test_saas_api.py::test_user_a_project_upload_job_result` |
| User B → A project/file 접근 거부 | 통과 | `test_saas_api.py` 의 `test_user_b_cannot_*` 8건 (프로젝트·업로드·자산·작업·진행률·취소·산출물 다운로드·사용량) |
| 3 jobs concurrent queue | 통과 | `test_saas_api.py::test_three_jobs_queue_concurrently` (워커 3개 스레드) |
| browser close 후 worker 지속 | 통과 | 두 겹으로 확인했다. ① `test_job_completes_after_the_submitting_client_is_gone` (같은 프로세스). ② `scripts/e2e_phase2.py` — `uvicorn` 과 워커를 **각각 별도 OS 프로세스**로 띄우고 TCP HTTP 로 제출한 뒤 세션을 닫았고, 다른 PID 의 워커가 FFmpeg 렌더까지 끝냈다. API 를 재시작해도 결과가 남는 것까지 확인했다. |

**실엔진 증거 확보**: `scripts/e2e_phase2.py` 가 진짜 MP4 를 presigned 업로드해
FFmpeg 렌더까지 돌리고, 내려받은 산출물을 `ffprobe` 로 검사한다 (1080×1920 h264+aac
48kHz, 2편). 12단계 전부 통과. 결과는 `docs/PHASE2_GO_NO_GO.md` 에 있다.

단위·통합 테스트는 여전히 `tests/saas_fakes.py` 의 대역 파이프라인을 쓴다 — 빠르고
FFmpeg 이 필요 없어야 CI 에서 돌기 때문이다. 실엔진 검증은 위 스크립트가 맡는다.

---

## 5. 범위에서 뺀 것

명세: *"결제/YouTube upload/trend UI 는 아직 구현하지 마라."* → 구현하지 않았다.
MASTER_V3: *"결제 자체는 아직 구현하지 않는다."* → 크레딧 **원장 구조만** 만들었고
충전·과금·결제 연동은 없다.

`saas/console.html` 은 브랜드·카피·디자인 시스템이 **없는** 점검용 화면이다.
브라우저에서 격리와 큐를 눈으로 확인하기 위한 것이고, Phase 3 의 웹 셸이 대체한다.

---

## 6. 남은 일 (다음 담당자용)

1. ~~실엔진 E2E 미실행.~~ **완료** — `scripts/e2e_phase2.py`. FFmpeg 은 이 환경에
   설치했고(`apt-get update` 후 `ffmpeg` 설치), STT 는 예고한 대로 전사 캐시를
   미리 심어 우회한다. 따라서 **STT 정확도는 여전히 미검증**이다.
2. ~~Phase 2 GO/NO-GO 보고서 미작성.~~ **완료** — `docs/PHASE2_GO_NO_GO.md`.
3. **P6(타임아웃 미적용)** — Phase 1 부터 넘어온 항목. 계약에 정의만 돼 있고
   워커가 강제하지 않는다. 큐 lease(기본 900초)가 사실상의 상한 역할을 하지만
   렌더를 중단시키지는 않는다.
4. **Redis 미사용.** 컨테이너에 설치·기동은 확인했으나 코드는 쓰지 않는다
   (2.1 참조). 캐시/rate limit 용도로 쓸지는 Phase 3 이후 결정.
5. **S3Presigner 실검증 없음.** 서명 생성 규칙은 단위 테스트로 고정했지만 실제
   S3/R2 버킷에 PUT 해본 적이 없다. 배포 전 필수.
6. **Phase 0 미결 2건 여전히 열려 있음** — private YouTube 업로드 실기 검증,
   YouTube 할당량 공식 재검증. Phase 8 진입 전 필수.

---

## 7. Phase 1 핸드오프 항목 처리 현황

| | 항목 | 상태 |
|---|---|---|
| P1 | InMemoryJobStore → PostgreSQL | 완료 (`saas/jobstore.py`) |
| P2 | 요청 스레드 동기 실행 → durable queue + worker | 완료 (`saas/queue.py`, `saas/worker.py`) |
| P3 | LocalStorage → S3/R2 | 부분 (`S3Presigner` 만. 읽기/쓰기 Storage 구현은 미완) |
| P4 | auth/workspace 격리 미적용 | 완료 (`saas/auth.py`, `saas/tenancy.py`) |
| P5 | 진행률 구간이 단계 이름에 결합 | 미해결 (Phase 1 상태 그대로) |
| P6 | 타임아웃 정의만 있고 강제 안 함 | 미해결 |
| P7 | cost_events 가 형식만 | 부분 (적재는 하지만 단가는 0. Phase 7 에서 붙인다) |

---

## 8. 엔진 변경 (최소)

`autoshorts/service.py` 에 **인자 두 개만** 추가했다. 기존 호출부의 동작은 바뀌지 않는다.

- `submit(..., dedupe: bool = True)` — 워커는 `dedupe=False` 로 부른다. 이미
  저장소에 들어 있는 작업이 **자기 자신의 멱등성 검사**에 걸려 영원히 실행되지
  않는 문제를 막는다.
- `submit(..., token: CancellationToken | None = None)` — 제출한 프로세스와
  실행하는 프로세스가 다를 때 취소 신호를 주입한다. 이게 없으면 워커가 만든
  토큰과 service 내부 record 의 토큰이 달라 취소가 실제로 멈추지 못한다.

`pipeline.py` / `video_renderer.py` / `ai_analyzer.py` / `cli.py` / `app.py` /
`contracts.py` / `storage.py` / `providers.py` 는 **한 줄도 바꾸지 않았다.**
