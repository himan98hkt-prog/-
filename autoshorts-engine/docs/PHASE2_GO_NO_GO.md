# Phase 2 — SaaS Foundation · GO/NO-GO 보고서

- 작성일: 2026-09-19
- 대상 커밋: `00d6b5a` 기준 + 이 브랜치의 E2E 하네스
- 설계·결정 근거는 `docs/PHASE2_SAAS_FOUNDATION.md` (ADR). 이 문서는 **판정**만 다룬다.

```
PHASE: 2 — SaaS Foundation
STATUS: GO
```

Phase 2 는 코드·스키마·테스트가 이미 병합돼 있었으나 **GO 판정에 필요한 두 가지가
비어 있었다** — 실엔진 E2E 증거, 그리고 이 보고서. 둘 다 채웠다.

---

## 1. 무엇이 비어 있었고 어떻게 채웠나

`PHASE2_SAAS_FOUNDATION.md` §6 이 남긴 1·2번 항목:

| | 이전 상태 | 지금 |
|---|---|---|
| 1 | 실엔진 E2E 미실행 — 별도 프로세스 + FFmpeg 렌더 + ffprobe 검증 스크립트 없음 | **완료** — `scripts/e2e_phase2.py`, 12단계 전부 통과 |
| 2 | GO/NO-GO 보고서 미작성 | **완료** — 이 문서 |

막고 있던 환경 제약 하나를 풀었다. FFmpeg 이 이 컨테이너에 없었고 `apt` 인덱스가
낡아 404 가 나던 것을 `apt-get update` 후 재설치해 **ffmpeg/ffprobe 6.1.1** 을
확보했다. 이전 담당자가 실엔진 E2E 를 못 한 주된 이유가 이것이었다.

---

## 2. 테스트 기준선 — 건너뛰던 137건이 실행됐다

`tests/conftest.py` 는 `AUTOSHORTS_TEST_DATABASE_URL` 이 없으면 SaaS 테스트를
건너뛴다. 그래서 그동안 **DB 테스트가 한 번도 돌지 않은 채** "통과" 로 보였다.
PostgreSQL 16 을 띄워 전부 실행했다.

| 조건 | 결과 |
|---|---|
| DB 없이 (종전 상태) | 703 passed · **137 skipped** |
| PostgreSQL 연결 | **855 passed · 0 skipped** |
| 이 브랜치 (E2E 헬퍼 테스트 11건 추가) | **866 passed · 0 skipped** |
| lint | `ruff check .` 통과 |

**137건이 전부 통과했다** — 격리·동시성·`SKIP LOCKED` 큐·원장·마이그레이션이 실제
PostgreSQL 에서 처음으로 검증됐다. 이것이 GO 의 가장 큰 근거다.

재현:

```bash
export AUTOSHORTS_TEST_DATABASE_URL="postgresql://postgres@/autoshorts_test?host=/tmp"
python -m pytest        # 866 passed
ruff check .
```

---

## 3. 실엔진 E2E — 12단계 전부 통과

```bash
export AUTOSHORTS_E2E_DSN="postgresql://postgres@/autoshorts_e2e?host=/tmp"
python scripts/e2e_phase2.py
```

| # | 단계 | 결과 | 소요 |
|---|---|---|---|
| 1 | 스키마 마이그레이션 | OK | 0.2s |
| 2 | 테스트 영상 생성 (1280×720 · 90초 · 84.8MB) | OK | 5.8s |
| 3 | API·워커를 **별도 프로세스**로 기동 | OK | 1.7s |
| 4 | 가입 → 워크스페이스 → 프로젝트 | OK | 0.2s |
| 5 | presigned URL 로 실제 MP4 업로드 | OK | 2.2s |
| 6 | 권리 미확인 상태에서 렌더가 막히는지 | OK | 0.4s |
| 7 | 전사 캐시 주입 (STT 불가 환경 우회) | OK | 0.0s |
| 8 | 작업 제출 후 HTTP 세션 종료 | OK | 0.1s |
| 9 | 별도 워커가 FFmpeg 렌더까지 완료 | OK | 18.8s |
| 10 | 산출물 다운로드 후 `ffprobe` 검증 | OK | 0.4s |
| 11 | 크레딧 예약 → 소진 정산 | OK | 0.0s |
| 12 | API 재시작 후 결과 유지 | OK | 0.9s |

### 확인된 사실

**프로세스 분리** — `api pid=2659`, `worker pid=2662`, 스크립트 `pid=2626`.
세 개가 서로 다른 PID 다. `TestClient` 도 `Worker.run_once()` 직접 호출도 쓰지
않았다. 실제 TCP HTTP 로만 통신했다.

**워커 독립성** — 작업을 제출한 `httpx.Client` 를 `with` 블록에서 빠져나와 완전히
닫은 뒤, **새 세션**으로 폴링했다. 렌더는 다른 프로세스의 워커가 끝냈다.
브라우저를 닫아도 작업이 계속된다는 명세 항목이 이로써 닫혔다.

**영속성** — API 프로세스를 `SIGTERM` 으로 죽이고 같은 포트에 새로 띄운 뒤에도
`GET /v1/jobs/{id}` 가 `succeeded` 를 돌려줬다. 상태가 프로세스 메모리가 아니라
PostgreSQL 에 있다.

**산출물 규격** — 2편 모두 `ffprobe` 로 확인:

```
1080x1920 · h264 · aac 48000Hz
```

16:9 원본(1280×720)이 9:16 으로 리프레이밍됐고, 단계 기록은
`ingest → transcribe → analyze → render` 로 남았다.

**권리 게이트** — `rights_status=unverified` 자산으로 제출한 작업은 렌더되지 않고
`needs_approval` 에서 멈췄다. `owned` 로 확인한 뒤에야 렌더가 진행됐다.
단위 테스트가 아니라 실제 HTTP 로 확인한 것이다.

---

## 4. 크레딧 보호 — Master Guard 11 실증

원장 전문(실행 결과):

| job | entry_type | amount | balance_after | reserved_after | reason |
|---|---|---|---|---|---|
| — | grant | 1800 | 1800 | 0 | 가입 기본 크레딧 |
| `job_4ff7…` | reserve | −300 | 1500 | 300 | 작업 예약 |
| `job_4ff7…` | release | **+300** | **1800** | **0** | 권리 승인 대기 |
| `job_dab7…` | reserve | −40 | 1760 | 40 | 작업 예약 |
| `job_dab7…` | commit | −30 | **1770** | **0** | 클립 2개, 30.5초 |

읽는 법:

- 권리 게이트로 멈춘 작업은 **예약 300 을 전액 반환**했다. 렌더하지 않은 작업이
  크레딧을 먹지 않는다 — *"failed jobs never consume final credits"* 충족.
- 실제 작업은 40 을 예약하고 **실사용 30 만 소진**, 잔여 10 은 반환됐다
  (잔고 1770 = 1800 − 30, `reserved_after = 0`). **묶인 예약이 남지 않는다.**
- `credit_ledger_job_entry_idx` 가 `(job_id, entry_type)` 유니크라 같은 작업에
  같은 종류가 두 번 기록되지 않는다 — 중복 차감 방지가 스키마 수준에 있다.

---

## 5. 명세 E2E 대조

| 명세 항목 | 상태 | 증거 |
|---|---|---|
| User A project → upload → job → result | 통과 | `test_saas_api.py` + 실엔진 E2E 4~10단계 |
| User B → A 자산 접근 거부 | 통과 | `test_user_b_cannot_*` 8건 (실 DB 에서 실행됨) |
| 3 jobs concurrent queue | 통과 | `test_three_jobs_queue_concurrently` (실 DB, `SKIP LOCKED`) |
| browser close 후 worker 지속 | **통과** | 실엔진 E2E 8~9단계 — 별도 OS 프로세스 |
| 실엔진 렌더 산출물 | **통과** | 실엔진 E2E 10단계 — `ffprobe` 1080×1920 |

---

## 6. 하지 않은 것

명세가 금지했거나 뒤 Phase 로 미룬 것. 이 Phase 에서 손대지 않았다.

- **결제 연동 없음.** 크레딧 원장 구조만 있고 충전·과금·PG 연동은 없다 (Phase 9).
- **YouTube 업로드 실행 없음.** private 실기 검증은 Phase 0 미결로 남아 있다 (Phase 8).
- **trend UI 없음.**
- `saas/console.html` 은 브랜드·디자인이 없는 **점검용** 화면이다. Phase 3 웹 셸이 대체한다.

---

## 7. 남은 위험 — Phase 3 로 넘긴다

| # | 항목 | 심각도 | 비고 |
|---|---|---|---|
| R1 | **STT 미검증** | 중간 | huggingface.co 차단으로 `faster-whisper` 를 받을 수 없다. E2E 는 전사 캐시로 우회했다. 전사 품질·소요시간은 여전히 미측정 (Phase 0 R7 과 동일) |
| R2 | **S3/R2 실검증 없음** | 중간 | `S3Presigner` 서명 규칙은 단위 테스트로 고정했으나 실제 버킷에 PUT 해본 적 없다. `LocalStorage` 만 실검증됨. 배포 전 필수 |
| R3 | **타임아웃 미강제 (P6)** | 중간 | 계약에 정의만 있고 워커가 렌더를 중단시키지 않는다. 큐 lease(900초)가 사실상의 상한 |
| R4 | **진행률 구간이 단계 이름에 결합 (P5)** | 낮음 | Phase 1 에서 넘어온 항목 |
| R5 | **cost_events 단가 0 (P7)** | 낮음 | 적재는 되지만 원가가 0. Phase 7 에서 단가를 붙인다 |
| R6 | **Redis 미사용** | 낮음 | 설치·기동은 되지만 코드가 쓰지 않는다. 캐시/rate limit 용도는 Phase 3 이후 결정 |
| R7 | **Phase 0 미결 2건 여전히 열림** | 중간 | private YouTube 업로드 실기, 할당량 공식 재검증. **Phase 8 진입 전 필수** |
| R8 | **E2E 가 CI 에 없음** | 낮음 | PostgreSQL·FFmpeg·자식 프로세스가 필요해 CI 에서 돌리지 않는다. 판정 헬퍼만 단위 테스트로 고정(11건). 실행은 수동 |

R1·R2 는 **배포 전** 해소해야 한다. R3~R6 은 기능 확장 시점에 자연히 처리된다.

---

## 8. 판정

```
STATUS: GO
```

근거:

1. 명세가 요구한 E2E 5개 항목 **전부 통과** — 마지막 "부분" 항목까지 닫혔다
2. 실엔진으로 1080×1920 h264+aac 산출물을 **실제로 뽑아 ffprobe 로 확인**했다
3. 그동안 건너뛰던 DB 테스트 137건이 **실제 PostgreSQL 에서 전부 통과**했다
4. 크레딧 보호(Master Guard 11)가 원장 전문으로 실증됐다
5. 권리 게이트가 실제 HTTP 경로에서 동작한다
6. `ruff` 통과, 866 tests 통과, 기존 테스트 regression 없음

남은 위험 R1~R8 중 Phase 3 진입을 막는 것은 없다. R1·R2 는 배포 전, R7 은 Phase 8
진입 전 조건으로 기록한다.

---

## 9. Phase 3 진입 조건

`CLAUDE_CODE_MASTER_V3.md` Phase 3 는 마케팅 홈·대시보드·프로젝트 생성·처리 화면·
하이라이트 후보·검토/편집·결과 다운로드를 요구한다. 그 전에 확인할 것:

- [x] Phase 2 GO — 이 문서
- [x] 멀티테넌트 API 가 실제 HTTP 로 동작 (E2E 4~10단계)
- [x] 작업 상태·진행률·산출물을 API 로 읽을 수 있음 (Phase 3 UI 가 붙을 표면)
- [x] 권리 상태가 API 에 노출됨 (Phase 3 가 **필수 선택**으로 받아야 함)
- [ ] Phase 3 착수는 **사용자 지시 대기** — MASTER_V3 는 한 번에 한 Phase 만 허용

Phase 3 가 사용해야 할 표면: `POST /v1/auth/signup` · `POST /v1/workspaces/{id}/projects`
· `POST /v1/projects/{id}/uploads` · `POST /v1/assets/{id}/rights`
· `POST /v1/projects/{id}/jobs` · `GET /v1/jobs/{id}` · `GET /v1/jobs/{id}/progress`
· `GET /v1/outputs/{id}/download`
