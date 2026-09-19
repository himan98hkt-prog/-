# Phase 0 — Productization Gate 보고서

- 작성일: 2026-09-19
- 기준 브랜치: `feat/autoshorts-phase0-productization-gate` (base: `feat/autoshorts-commercial-saas` `b3d8dca`)
- 대상: `autoshorts-engine/` (분석형 쇼츠 엔진)
- 적용 사양: `CLAUDE_CODE_MASTER_V3.md` Phase 0 + `DEVELOPMENT_PROMPTS.md` Prompt 0
  + `CLAUDE_CODE_EXECUTION_V2.md` Phase 0 추가 지시

> **범위 밖**: SaaS UI, DB/Auth/결제, Phase 4 이후 품질 엔진(multimodal/reframe 2.0),
> public 업로드. 어느 것도 이 Phase 에서 구현하지 않았다.
>
> **다른 프로젝트와 섞지 않았다**: `shorts-factory`(키워드→생성형 파이프라인)는
> 별개 저장소이며 이 작업에서 한 줄도 건드리지 않았다.

---

## 1. 테스트 기준선

| 시점 | 테스트 수 | 결과 |
|---|---|---|
| 작업 전 (`b3d8dca`) | **454** | 전부 통과 (1.7s) |
| 작업 후 | **539** | 전부 통과 (1.1s) |

Prompt 0 이 물은 "기존 454개 수준의 테스트가 현재 HEAD 에서 실제로 몇 개인지"에 대한
답은 **정확히 454개**다. 이번에 85개를 더했다 (`test_quota.py` 30, `test_benchmark.py` 55,
`test_automation.py` +1, 기존 테스트 일부는 하드코딩 제거로 수정).

실행:

```bash
cd autoshorts-engine
pip install pytest ruff
python -m pytest        # 539 passed
ruff check autoshorts tests
```

무거운 의존성(yt-dlp·faster-whisper·Gemini SDK) 없이 통과한다 — 지연 임포트 구조가
유지되고 있다.

---

## 2. YouTube 할당량 — 낡은 가정 제거

### 발견

`COMMERCIALIZATION_ROADMAP.md` §2 가 지적한 문제를 확인했고, **그 지적보다 한 단계 더
바뀐 상태**였다.

| | 기존 코드 가정 | 현재 정책 |
|---|---|---|
| `videos.insert` | 1,600 유닛, 공용 풀에서 차감 → 하루 6건 | **전용 버킷**, 호출당 1 유닛, 기본 **하루 100건** |
| `search.list` | 100 유닛, 공용 풀에서 차감 | **전용 버킷**, 호출당 1 유닛, 기본 **하루 100회** |
| 나머지 메서드 | 공용 10,000 유닛 | 공용 10,000 유닛 (변동 없음) |

변경 경위: 2025-12-04 `videos.insert` 비용 인하 → 2026-06-01 `videos.insert` 와
`search.list` 를 각각 전용 버킷으로 분리(granular quota).

실질적 영향: 업로드 상한이 **하루 6건 → 100건**. 그리고 검색과 업로드가 공용 풀을
잠식하지 않는다. 대신 **공용 유닛이 남아 있어도 검색 100회를 넘기면 403** 이 온다 —
이전 모델에는 없던 실패 양상이다.

### 검증의 한계 (중요)

이 환경의 egress proxy 가 `developers.google.com` 을 차단해 **1차 출처를 직접 열지
못했다.** 위 내용은 Google Revision History 를 인용한 복수의 2차 출처가 일치하는 것을
근거로 삼았다. 실제 운영 전에 사람이 아래를 직접 확인하고
`autoshorts/quota.py` 의 `POLICY_VERIFIED_ON` 을 갱신해야 한다.

- https://developers.google.com/youtube/v3/revision_history
- https://developers.google.com/youtube/v3/determine_quota_cost
- https://developers.google.com/youtube/v3/docs/videos/insert

### 조치 — 상수에서 정책 계층으로

숫자를 고치는 대신 **숫자가 코드에 박히지 않는 구조**로 옮겼다. 정책이 또 바뀔 것이기 때문이다.

신규 `autoshorts/quota.py`:

- `QuotaBucket` / `QuotaPolicy` — 버킷별 호출 비용과 일일 한도
- 환경변수 오버라이드 — `AUTOSHORTS_YT_UPLOAD_DAILY_CALLS`,
  `AUTOSHORTS_YT_SEARCH_DAILY_CALLS`, `AUTOSHORTS_YT_QUERIES_DAILY_UNITS`,
  `AUTOSHORTS_YT_UPLOAD_UNIT_COST`, `AUTOSHORTS_YT_SEARCH_UNIT_COST`
  (잘못된 값·0·음수는 무시하고 경고)
- `POLICY_VERIFIED_ON` / `POLICY_SOURCES` — 확인일과 근거를 코드가 들고 다닌다
- `describe_policy()` — `autoshorts quota` 로 현재 적용값 출력

**API 응답이 최종 진실**이라는 원칙을 코드와 문구에 모두 반영했다. 정책값은 사전 예산과
안내에만 쓰고, 한도 초과 판정은 `quotaExceeded` / `uploadLimitExceeded` 응답으로만 한다.
오류 메시지도 "API 응답 기준"임을 밝히도록 고쳤다.

재배선한 곳: `uploader.py`(상수는 deprecated alias 로 남겨 하위 호환),
`trend_finder.py`(`API_COSTS` → `policy.cost_for()`), `automation.py`(업로드 한도),
`cli.py`·`app.py`(사용자 안내 문구), `README.md`·`시작하기.txt`·`.env.example`.

**테스트에 박혀 있던 가정도 함께 제거했다.** `test_automation.py` 는 "오늘 6건 올렸으면
막힌다"를 하드코딩하고 있어 정책 변경만으로 깨졌다 — 정책에서 한도를 읽도록 고쳤고,
정책을 좁게 주면 그대로 따르는지 검증하는 테스트를 추가했다.

---

## 3. 기준선 측정 도구

### `autoshorts benchmark`

신규 `autoshorts/benchmark.py` + CLI 서브커맨드.

```bash
autoshorts benchmark benchmarks/manifest.json --report out/bench.json --markdown out/bench.md
autoshorts benchmark benchmarks/manifest.json --only 10,30
```

측정 항목 — Prompt 0 #8 과 MASTER_V3 Phase 0 추가 요구를 함께 충족한다.

| 항목 | 방법 |
|---|---|
| 전체 처리시간 | 실행 전후 monotonic 시계 |
| **스테이지별** 소요시간 | `StageTimer` 가 기존 `on_progress` 콜백의 스테이지 전환을 관찰 |
| peak memory | `getrusage(SELF/CHILDREN)` 최대값 — FFmpeg 등 자식 포함 |
| output size / 개수 | 산출 파일 stat |
| 원본 1분당 처리시간 | 전사 duration 기준 |
| render 성공률 | 산출물이 1개 이상 생겼는지 |
| 문장 중간 절단률 | 클립 경계가 단어 내부이거나 문장을 끝맺지 않은 비율 |
| 클립 중복률 | 클립끼리 겹친 시간 / 전체 클립 시간 |
| gold moment 적중률 | manifest 의 정답 구간을 50% 이상 덮은 비율 |

**파이프라인은 고치지 않았다.** 스테이지 시간은 콜백 관찰로 얻으므로 Phase 1 의
`JobResult.stage_timings` 계약을 미리 구현하지 않았다.

한 편이 실패해도 세트 전체가 끝까지 돌고, 실패는 보고서에 기록된다. 전편 성공이 아니면
종료 코드 `1` 이라 CI 에 그대로 걸 수 있다.

### benchmark sample manifest 구조

`benchmarks/manifest.example.json` + `benchmarks/README.md`.
스키마 버전(`version: 1`), `id` / `source` / `duration_bucket` / `content_mode` /
`rights_status` / `gold_moments` / `notes`. 실행 전에 검사해 문제를 경고로 출력한다
(알 수 없는 모드, 뒤집힌 구간, 중복 id, 버전 불일치).

`content_mode` 어휘는 MASTER_V3 Phase 1 `JobSpec.content_mode` 와 일치시켰고,
그 일치를 테스트로 고정했다.

**실제 영상은 채워지지 않았다.** 목표 구성(30~50편, podcast 10 / lecture 8 / gaming 8 /
sports 6 / news 5 / vlog 5)과 gold moment 지정은 사람이 권리 확인과 함께 해야 한다.

---

## 4. 현재 품질의 known baseline / known limitations

MASTER_V3 Phase 0 이 요구한 "현재 highlight/reframe/caption 의 known baseline 문서화".

### 4-1. Highlight — 경계가 문장을 자른다 (가장 큰 문제)

`benchmarks/probe_boundary_baseline.py` 로 **재현 가능하게** 측정했다
(합성 전사, 영상·API 키 불필요).

```
전사 구성                         길이    클립     문장중간절단률
세그먼트 = 문장 (이상적)              10분   5.0            0.0%
세그먼트 = 문장 (이상적)              30분   5.0            0.0%
세그먼트 = 문장 (이상적)              60분   5.0            0.0%
문장 무시, 4단어씩                  30분   5.0           76.0%
문장 무시, 8단어씩                  30분   5.0           82.0%
문장 무시, 12단어씩                 30분   5.0           70.0%
```

**원인 (코드 확인):** `ai_analyzer.snap_to_segments()` 는 클립 경계를 2.5초 안의
가까운 **세그먼트** 경계로 당긴다. 그런데 Whisper 세그먼트는 문장 단위가 아니라 침묵과
길이로 끊긴다. 따라서 세그먼트에 정확히 붙여도 **문장은 그대로 잘린다.** 세그먼트가
우연히 문장과 일치할 때만 0% 가 된다.

Beta 목표는 **5% 이하**(`COMPETITIVE_BENCHMARK_2026.md` §6). 현재 구조로는 도달하지
못한다. Phase 4 의 "mid-sentence boundary prevention" 이 필요하다 —
세그먼트가 아니라 **종결부호·문장 단위**로 스냅해야 한다.

> 위 숫자는 합성 전사 값이므로 실영상 성적으로 인용하면 안 된다. 확정된 것은
> **메커니즘**(세그먼트 스냅은 문장을 지키지 못한다)이고, 실제 비율은 실영상
> 벤치마크로 확정해야 한다.

기타 highlight 한계:

- 신호가 **전사 텍스트뿐**이다. 화면·소리·장면전환·얼굴을 보지 않는다(Phase 4).
- 훅 판정이 **한국어/영어 신호어 목록**(`_HOOK_WORDS` 38개)에 의존한다. 목록에 없는
  표현은 점수를 못 받고, 다른 언어는 사실상 무작위다.
- 점수가 **단일 스칼라**다. hook / narrative / visual / audio / standalone 분해가
  없어 왜 뽑혔는지 설명할 수 없다(Phase 4 요구사항).
- `content_mode` 별 가중치가 없다 — 팟캐스트와 게임 영상을 같은 기준으로 고른다.
- 광고/CTA 감점이 `_FILLER_WORDS` 7개 단어 매칭 수준이다.
- Gemini 실패 시 휴리스틱으로 떨어지는데, **품질 차이가 사용자에게 표시되지 않는다**
  (`used_offline_analysis` 는 결과에 있지만 UI 가 알리지 않는다).
- 중복 제거는 동작한다 — 위 측정에서 중복률이 전 구성 **0.0%** 였다.

### 4-2. Reframe — 활성 화자를 모른다

`ffmpeg_tools.build_reframe_filter()` 는 두 모드만 있다.

- `crop`: **화면 정중앙**을 9:16 으로 잘라낸다
- `blur`(기본): 배경은 확대+가우시안 블러, 전경은 원본 비율로 가운데 배치

한계:

- **얼굴·화자 검출이 없다.** 화자가 화면 좌우에 있으면 `crop` 은 사람을 잘라내고,
  `blur` 는 원본을 그대로 줄여 넣어 인물이 작아진다.
- 다중 화자 대응 없음 — split-screen 프리셋 없음.
- saliency/콘텐츠 영역 추적 없음, 시간축 스무딩/히스테리시스 없음(추적이 없으니 지터도
  없지만, 장면에 맞춰 따라가지도 않는다).
- 게임+페이스캠, 화면공유 같은 레이아웃 인식 없음.
- safe area 개념이 자막 여백(`margin_v=320`)에만 있고 영상 프레이밍에는 없다.

→ reframe 실패율 / face crop violation / framing jitter 는 **측정 자체가 불가능**하다
(검출기가 없어서). Phase 5 에서 검출기와 함께 지표를 추가해야 한다.

### 4-3. Caption — 스타일 고정, 폰트 의존

`subtitles.py` 는 ASS 를 만들어 libass 로 번인한다. 단어별 강조가 동작한다.

기본값: `NanumGothic Bold` 78px, 줄당 14자, cue 당 6단어, cue 최대 2.4초,
하단 여백 320px(1920 기준), 활성 단어 노란색 강조.

한계:

- **폰트가 시스템에 있어야 한다.** 없으면 한글이 □ 로 나온다. 번들 폰트가 없고,
  렌더 전에 글리프를 검사하지 않는다(`doctor` 가 사후 점검만).
- 단어 애니메이션·키워드 강조 프리셋·커스텀 폰트 업로드 없음(Phase 6).
- 줄바꿈이 **글자 수 기준**이다. 실제 렌더 폭을 재지 않으므로 긴 단어나 다른 폰트에서
  넘칠 수 있다.
- CJK/영문 혼용 시 폭 계산이 근사값이다(`_visible_length`).
- 자막 편집 UI 가 없다 — subtitle edit rate 측정 불가(Phase 5).
- safe zone 이 하단 여백 상수 하나다. 플랫폼별 UI 겹침 프리셋이 없다.

### 4-4. 아직 못 재는 지표와 그 이유

| 지표 | 왜 못 재나 | 해결 Phase |
|---|---|---|
| standalone 이해도 | 사람 평가 또는 narrative 엔진 필요 | 4 |
| reframe 실패율 / face crop violation / jitter | 얼굴·화자 검출 없음 | 5 |
| subtitle edit rate | 편집기 없음 | 5 |
| cost / source minute | 원가 원장 없음 | 2 / 9 |
| top-N acceptance (실측) | gold set 영상 미확보 | 0 이후 사람 작업 |

---

## 5. 실기 검증 절차 (자동 실행하지 않음)

`docs/PRIVATE_UPLOAD_SMOKE.md` — private 업로드 수동 체크리스트.

- A 인증 경로 5항목 (토큰 없음/손상, client_secret 없음, 로그인, **키 마스킹**)
- B dry-run 3항목 (실제로 올리지 않고 요청 조립 확인)
- C 실제 private 업로드 6항목
- D 실패 경로 4항목 (할당량 초과, 400, 중단, 네트워크 끊김)
- E Linux/Windows
- 기록 양식 + 공개 발행 전 조건 체크리스트

**이 절차는 실행되지 않았다.** 실제 OAuth 토큰과 YouTube 계정이 필요하고 계정 상태를
바꾸므로 사람이 해야 한다. 지시받은 대로 자동 실행하지 않았다.

---

## 6. 최소 품질 gate

lint/type check 가 아예 없었다. 기존 코드를 대규모로 뜯지 않는 선에서 좁게 도입했다.

`pyproject.toml [tool.ruff.lint]`: `select = ["F", "E9"]`

- `F` (pyflakes) — 미사용/미정의 이름, 잘못된 f-string, 중복 정의 등 **실제 버그**
- `E9` — 구문 오류

켜지 않은 것과 이유: `E501`(줄 길이) 27건, `E741`(모호한 변수명) 3건,
`E731`(람다 대입) 1건 — 전부 동작과 무관한 스타일이고, 지금 고치면 diff 가 커져
리뷰가 어려워진다. 해당 파일을 손볼 때 함께 정리한 뒤 켜는 것을 권한다.

**gate 를 통과시키기 위해 실제로 고친 것**: 미사용 import 10건
(9건은 기존 코드, 1건은 이번 작업에서 생긴 매달린 import). 전부 통과 상태다.
CI(`.github/workflows/autoshorts.yml`)에 `ruff check` 단계를 추가했다.

type check(mypy)는 **넣지 않았다.** 타입 힌트가 부분적이라 지금 켜면 수백 건이 나오고,
그걸 맞추는 일은 Phase 0 범위를 넘는다. Phase 1 의 서비스 경계를 만들 때 그 경계부터
`strict` 로 시작하는 것을 권한다.

---

## 7. 권리 확인 지점

`docs/SOURCE_RIGHTS.md` — 코드/UI 요구사항으로 정리.

가장 위험한 흐름을 명시했다: `trend_finder` → 제작 → 업로드가 한 줄로 이어져
**남의 인기 영상을 그대로 자르도록 유도**하며, 사람이 판단할 자리가 강제되지 않는다.

- 권리를 물어야 하는 4개 지점 (입력 / 다운로드 / 검토 / 발행)
- `owned` `licensed` `creative_commons` `unverified` — 기본값은 `unverified`
- **Creative Commons 를 "법적 안전"으로 표시하지 않는다** (MASTER_V3 Phase 7 지시)
- CC 발행에 필요한 보관 필드 6개 (`license_evidence`, `checked_at`, `attribution_text` …)
- Phase 별 할 일 분배

벤치마크 manifest 에 `rights_status` 분류를 넣어, 측정 단계부터 권리 상태가 따라다닌다.

---

## 8. 보안 / 개인정보

- 이번 변경에 credential 은 없다. 새 환경변수 5개는 **모두 정수 한도값**이고 비밀이 아니다.
- `.env.example` 에 실제 키를 넣지 않았다.
- 할당량 오류 메시지에서 키가 노출되지 않는지 확인했다
  (`trend_finder._get` 은 URL 대신 엔드포인트만 로그).
- 키 마스킹 실기 확인은 수동 체크리스트 A5 로 넘겼다.

## 9. 비용 / 할당량 영향

- 이번 작업은 **외부 API 를 한 번도 호출하지 않았다.** 모든 테스트가 가짜 transport/service 를 쓴다.
- 업로드 상한 인식이 하루 6건 → 100건으로 올라가, 같은 코드가 이전보다 **많이** 올릴 수
  있게 됐다. 정책 오버라이드로 보수적으로 낮출 수 있는 통로를 함께 만들었다.
- 벤치마크를 실영상으로 돌리면 Gemini 호출과 다운로드 트래픽이 발생한다. 오프라인
  휴리스틱만으로도 돌아가므로 무과금 측정이 가능하다.

---

## 10. 남은 위험 / Phase 1 에 넘기는 기술 부채

| # | 위험 | 심각도 | 근거 / 대응 |
|---|---|---|---|
| R1 | 문장 중간 절단 — 세그먼트 스냅으로는 Beta 목표(5%) 불가 | **높음** | §4-1. Phase 4 필수 |
| R2 | 활성 화자 미인식 reframe — talking-head 에서 인물 잘림 | **높음** | §4-2. Phase 5 필수 |
| R3 | 할당량 정책 1차 출처 미확인 (proxy 차단) | 중간 | §2. 사람이 확인 후 `POLICY_VERIFIED_ON` 갱신 |
| R4 | private 업로드 실기 미검증 | 중간 | §5. 체크리스트 실행 필요 |
| R5 | 실영상 벤치마크 세트 미확보 (30~50편 + gold moment) | 중간 | §3. 권리 확인과 함께 사람 작업 |
| R6 | `quota_used` 가 **버킷이 다른 유닛을 합산**한다 | 중간 | 전용 버킷 분리 후 총합은 의미가 약하다. Phase 1 에서 버킷별 집계로 |
| R7 | 30/60분 실측치 없음 — 이 컨테이너에 FFmpeg 없음 | 중간 | 도구는 준비됨. 실행 환경에서 측정 필요 |
| R8 | 중단/네트워크 끊김 시 idempotency 없음 | 중간 | §5 D3·D4. Phase 8 |
| R9 | 오프라인 휴리스틱 품질 저하가 사용자에게 안 보임 | 낮음 | Phase 3 UI 에서 표시 |
| R10 | 자막 폰트 시스템 의존 (없으면 □) | 낮음 | Phase 6 에서 번들/사전검사 |
| R11 | 타입 체크 없음 | 낮음 | Phase 1 경계부터 도입 |

---

## 11. Go gate 대조

`COMMERCIALIZATION_ROADMAP.md` §6 Phase 0 Go gate:

| 기준 | 상태 | 비고 |
|---|---|---|
| 기존 테스트 green | ✅ | 539 passed (기준선 454 → regression 없음) |
| quota 정책 검증 및 수정 완료 | ⚠️ | 코드/문서/테스트 수정 완료. **1차 출처 확인은 proxy 차단으로 미완** |
| private 업로드 실제 성공 | ❌ | 체크리스트 작성 완료, **실행은 사람 몫** (자동 실행 금지 지시 준수) |
| 30분 원본에서 실패 없이 결과 생성 | ❌ | 측정 도구 준비 완료, **FFmpeg 없는 환경이라 실측 불가** |
| 실패 시 재현 가능한 로그 확보 | ✅ | 벤치마크가 실패를 보고서에 기록, probe 는 재현 가능 |
| benchmark 도구 존재 | ✅ | `autoshorts benchmark` + manifest + probe |
| private-upload smoke checklist 존재 | ✅ | `docs/PRIVATE_UPLOAD_SMOKE.md` |
| Phase 1 위험 목록 명확 | ✅ | §10, R1~R11 |

---

## 12. 결론

**STATUS: NO-GO (조건부)** — 코드 작업은 끝났지만 Go gate 3개가 **사람의 실기 작업**을
기다린다. 자동화할 수 없거나, 하지 말라고 지시받은 항목들이다.

Phase 1 로 넘어가기 전에 사람이 해야 할 일:

1. **할당량 1차 출처 확인** — 위 3개 Google 문서를 열어 숫자를 맞추고
   `autoshorts/quota.py` 의 `POLICY_VERIFIED_ON` 갱신 (§2)
2. **private 업로드 실기 1건** — `docs/PRIVATE_UPLOAD_SMOKE.md` A~D 수행 (§5)
3. **FFmpeg 있는 환경에서 10/30/60분 실측** — `autoshorts benchmark --only 10,30,60` (§3)
4. **벤치마크 세트 채우기** — 권리 확인된 영상과 gold moment (§3, §7)

이 4개가 끝나면 Go gate 전 항목이 충족되고 Phase 1 (Engine Service Boundary)
진입 조건이 성립한다.

단, **R1(문장 절단)과 R2(활성 화자 reframe)는 Phase 0 에서 고칠 수 없다.** 구조적
한계이며 각각 Phase 4·5 의 핵심 과제다. 이 두 가지가 해결되기 전에는
경쟁 제품과 **출력 품질로 겨룰 수 없다** — 기능 목록이 아니라 이 둘이 승부처다.
