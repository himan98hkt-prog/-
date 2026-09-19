# Phase 1 — Engine Service Boundary

작성일: 2026-09-16
브랜치: `feat/autoshorts-commercial-saas`
선행: Phase 0 (`84977cb`)

CLI/Gradio 전용이던 엔진을 **SaaS worker 가 호출할 수 있는 경계** 뒤에 놓는다.

---

## 1. 핵심 결정: 파이프라인을 감싼다, 바꾸지 않는다

`run_pipeline` 은 **한 줄도 바뀌지 않았다.** `git status` 로 확인 가능하다 —
`pipeline.py` · `video_renderer.py` · `ai_analyzer.py` · `cli.py` · `app.py` 모두 무변경.

```
JobSpec ──▶ EngineService ──▶ Settings ──▶ run_pipeline (기존)
                  │                              │
                  │◀──── ProgressEvent ◀─────────┘
                  ▼
             JobResult
```

**왜 이렇게 했나.** 파이프라인은 454건의 테스트로 보호되는 동작하는 코드다. 서버가
필요로 하는 것(취소·멱등성·오류 분류·권리 게이트)은 **파이프라인의 관심사가 아니다.**
안으로 밀어 넣으면 CLI 사용자가 쓰지도 않을 개념이 엔진에 스며든다.

대가: 진행률 구간(`_STAGE_RANGES`)이 파이프라인의 단계 이름에 의존한다. 단계가 바뀌면
서비스도 같이 고쳐야 한다. 이 결합은 받아들였다 — 대안(파이프라인에 계약을 주입)이
훨씬 침습적이기 때문이다.

---

## 2. 계약 (`contracts.py`)

전부 JSON 직렬화 가능. 큐·DB·HTTP 어디를 통과해도 같은 모양이다.

| 타입 | 역할 |
|---|---|
| `JobSpec` | 작업 명세. source·workspace·project·옵션·권리·품질 프로파일 |
| `JobResult` | 결과. status·outputs·stage_timings·warnings·quality_checks·cost_events |
| `ProgressEvent` | job_id·stage·percent·message·timestamp |

### V3 가 추가 요구한 필드

- `content_mode` — `auto \| podcast \| lecture \| gaming \| sports \| news \| vlog`
  (Phase 4 가 mode별 signal weight 에 사용)
- `rights_status` — `owned \| licensed \| creative_commons \| unverified`
- `quality_profile` — `standard \| high` (현재는 crf/preset/whisper 모델에 반영)
- `JobResult.stage_timings` / `warnings` / `quality_checks` / `cost_events`

### 비밀값을 계약에 담지 않는다

`ProviderSettings` 는 키를 **이름으로만** 참조한다(`credentials_ref`). JobSpec 은 DB·큐·
로그를 지나다니므로 여기에 키가 들어가면 전부 샌다. `model_overrides` 에 API 키처럼
보이는 문자열이 오면 생성 시점에 거부한다.

---

## 3. 권리 게이트

`rights_status = unverified` 이고 승인자가 없으면 **렌더 전에 멈춘다.**

```
submit() → requires_rights_approval? → JobStatus.NEEDS_APPROVAL (렌더 안 함)
                                              │
                                    approve_rights(job_id, approver)
                                              ▼
                                        재개 → SUCCEEDED
```

`NEEDS_APPROVAL` 은 **실패가 아니다**(`is_terminal == False`). 사람의 결정이 남아
의도적으로 멈춘 상태이며 승인 후 재개된다. 승인자 식별자는 반드시 기록된다.

Phase 0 의 벤치마크 러너도 같은 규칙을 따른다 — `unverified` 소스는 벤치마크에서도
처리하지 않는다.

---

## 4. 멱등성

### 작업 수준

`idempotency_key` = 결과에 영향을 주는 필드의 SHA-256(앞 32자).
`job_id`·`created_at` 처럼 매번 달라지는 값은 **제외**한다. `rights_status` 도 제외한다 —
권리 승인은 결과물을 바꾸지 않기 때문이다.

같은 키 + 같은 workspace 의 작업이 이미 있으면 **재실행하지 않고** 기존 결과를
`reused_from_job_id` 와 함께 돌려준다. 중복 클릭이나 큐 재전달이 credit 을 두 번
태우지 않게 하기 위해서다.

**단, 실패한 작업은 재사용하지 않는다.** 재사용하면 일시적 오류로 실패한 작업을
영영 재시도할 수 없게 된다.

### 단계 수준 (`STAGE_IDEMPOTENCY`)

| 단계 | 규약 | 근거 |
|---|---|---|
| ingest | `reusable` | 같은 소스 → 같은 파일. work_dir 해시로 캐시됨 |
| transcribe | `reusable` | `transcription.json` 이 있으면 재사용 (기존 동작) |
| analyze | `recompute` | LLM 응답이 결정적이지 않다. 비용이 낮아 재계산이 낫다 |
| render | `reusable` | 같은 이름의 출력이 있으면 덮어쓰지 않는다 (기존 `_unique_path`) |

---

## 5. 취소

**강제 종료가 아니라 협조적 취소다.** `CancellationToken` 을 단계 경계에서 확인한다.

```python
def emit(stage, fraction, message):
    record.token.raise_if_cancelled(stage)   # ← 체크포인트
    ...
```

렌더링 도중 프로세스를 죽이면 반쯤 쓰인 MP4 가 남는다. 단계 경계에서 멈추면 산출물이
깨끗하다. 대가는 응답 지연 — 렌더 중 취소는 그 클립이 끝난 뒤에 반영된다.

아직 시작하지 않은 작업(`QUEUED`/`NEEDS_APPROVAL`)은 즉시 `CANCELLED` 로 확정한다.
이미 끝난 작업은 그대로 둔다.

---

## 6. 오류 분류

`ErrorCode` 를 **재시도 가능/불가능** 으로 나눈다. 이 구분이 없으면 worker 가 잘못된
입력을 무한히 재시도하며 credit 만 태운다.

| 재시도 불가 | 재시도 가능 |
|---|---|
| `invalid_input` · `source_not_found` · `unsupported_format` · `rights_not_confirmed` · `no_speech_detected` · `no_candidates` · `cancelled` · `internal_error` | `provider_unavailable` · `provider_rate_limited` · `timeout` · `render_failed` · `storage_error` |

모르는 예외는 보수적으로 `internal_error`(재시도 불가)로 둔다. 원인을 모르는 채
재시도하는 것보다 멈추고 사람이 보는 편이 낫다.

---

## 7. Storage 추상화

Phase 1 은 `LocalStorage` 만 쓴다. 파이프라인은 여전히 로컬 경로로 동작한다(FFmpeg 가
그래야 한다). Storage 는 **"끝난 산출물을 어디에 두고 어떤 주소로 부를 것인가"** 만
담당한다.

키는 `{workspace_id}/{project_id}/{파일명}` 으로 워크스페이스별로 갈린다.
루트를 벗어나는 키(`../`)는 거부한다 — 키가 사용자 입력에서 올 수 있다.

Phase 2 에서 `S3Storage` 를 추가할 때 `Storage` 인터페이스만 구현하면 된다.

---

## 8. Provider 어댑터

| 인터페이스 | 기본 구현 | 위임 대상 |
|---|---|---|
| `TranscriptionProvider` | `FasterWhisperProvider` | `transcriber.transcribe` |
| `HighlightProvider` | `GeminiHighlightProvider` | `ai_analyzer.analyze` |
| `RenderProvider` | `FFmpegRenderProvider` | `video_renderer.render_clips` |
| `SignalProvider` | **없음 (Phase 4)** | — |

`SignalProvider` 는 **자리만 잡아 뒀다.** audio energy·scene change·face presence·motion
같은 신호를 구간별로 돌려주는 인터페이스이며 구현은 Phase 4 범위다.

**fallback 규약**: `registry.signal_providers()` 는 `available == True` 인 provider 만
돌려준다. 하나도 없으면 빈 목록이고, highlight 선정은 기존 transcript-only 경로로
정상 동작한다. Phase 4 가 이 규약을 깨지 않아야 한다.

---

## 9. HTTP API

| 메서드 | 경로 | 설명 |
|---|---|---|
| `POST` | `/jobs` | 작업 제출 (202). 멱등 재사용·권리 게이트 적용 |
| `GET` | `/jobs/{job_id}` | 조회 (404 가능) |
| `POST` | `/jobs/{job_id}/cancel` | 취소 |
| `POST` | `/jobs/{job_id}/approve-rights` | 권리 승인 후 재개 (`approver` 필수) |
| `GET` | `/jobs` | 목록 (workspace 필터) |
| `GET` | `/health` | 상태 |

FastAPI 는 **선택 의존성**이다. 미설치 환경에서도 패키지 임포트와 테스트가 동작한다.

**Phase 1 범위의 한계 (의도적)**
- 인증 없음 — Phase 2
- 작업이 **요청 스레드에서 동기 실행** — Phase 2 의 worker/queue 로 교체
- 저장소가 in-memory — `JobStore` 인터페이스만 만족하면 PostgreSQL 로 교체 가능

---

## 10. 검증

| 항목 | 결과 |
|---|---|
| 전체 테스트 | **654 passed, 1 skipped** (Phase 0 대비 +106) |
| 신규 테스트 | 계약 49 · 서비스 41 · API 16 |
| lint | `ruff check` 통과 |
| CLI 무회귀 | 13개 서브커맨드 `--help` 전부 정상 |
| Gradio 무회귀 | `build_interface()` 정상 |
| 기존 엔진 파일 | **무변경** (pipeline/renderer/analyzer/cli/app) |

### 실제 엔진으로 종단 확인

가짜가 아닌 실제 파이프라인을 서비스 경계로 통과시켰다(10분 소스).

```
status      : succeeded
outputs     : 2  (131.2~174.5s / 260.7~304.5s, 3.2MB / 3.3MB)
stage timing: ingest 2.62s · transcribe 0.0s(캐시) · analyze 0.09s · render 40.57s
progress    : 9건, 마지막 (render, 100.0)
quality     : clip_length_in_range ✓ · clip_count_meets_minimum ✓ · vertical_output ✓
cost        : render 87.22 output_seconds · storage 6,503,276 bytes
warnings    : offline_highlight_analysis
재제출      : reused_from=job_b5a15382 (재실행 없음)
```

---

## 11. Phase 2 로 넘기는 것

| # | 항목 | 비고 |
|---|---|---|
| P1 | `InMemoryJobStore` → PostgreSQL | `JobStore` 인터페이스 구현만 하면 됨 |
| P2 | 동기 실행 → durable queue + worker | 현재 요청 스레드에서 실행 |
| P3 | `LocalStorage` → S3/R2 | `Storage` 인터페이스 구현 |
| P4 | 인증·workspace 격리 | 현재 `workspace_id` 는 문자열일 뿐 강제되지 않음 |
| P5 | 진행률 구간이 파이프라인 단계명에 결합 | §1 의 의식적 트레이드오프 |
| P6 | 타임아웃 미구현 | `ErrorCode.TIMEOUT` 은 정의돼 있으나 강제 타임아웃 없음. worker 도입 시 추가 |
| P7 | `cost_events` 는 형식만 | 실제 단가·credit 차감은 Phase 9 |

Phase 0 의 미결 항목(private 업로드 실기 검증, 할당량 공식 재검증)은 **여전히 열려 있다.**
Phase 8(publish) 진입 전에 반드시 닫아야 한다.
