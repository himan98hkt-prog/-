# Phase 0 — Productization Gate 보고서

작성일: 2026-09-16
브랜치: `feat/autoshorts-commercial-saas`
기준 커밋: `b3d8dca` (작업 전) → 아래 변경 반영

이 문서는 상용 SaaS 개발을 시작하기 전에 **기존 엔진의 사실관계와 기준선**을 고정한다.
추정이 아니라 이 저장소에서 실제로 실행해 얻은 수치만 기록하고, 측정하지 못한 것은
측정하지 못했다고 적는다.

---

## 1. 테스트 기준선

| 항목 | 값 |
|---|---|
| 작업 전 테스트 | **453 passed, 1 skipped** (수집 454) |
| 작업 후 테스트 | **548 passed, 1 skipped** |
| 추가 테스트 | 95건 (quota 20 · benchmark 65 · runner 10) |
| skip 1건 | `google-auth` 미설치 환경에서 자격증명 테스트 (`importorskip`) |
| lint | `ruff check` — 통과 (F/E9/I 규칙) |

로드맵이 언급한 "454개 수준"은 정확했다. 수집 기준 454, 실행 기준 453 passed + 1 skipped.

---

## 2. YouTube 할당량 — 낡은 가정 제거

### 무엇이 틀렸나

기존 `uploader.py` 는 다음을 **코드 상수로** 박아 두고 업로드를 사전 차단했다.

```python
UPLOAD_QUOTA_COST = 1600
DAILY_FREE_QUOTA = 10_000
DAILY_UPLOAD_LIMIT = DAILY_FREE_QUOTA // UPLOAD_QUOTA_COST   # = 6
```

`COMMERCIALIZATION_ROADMAP.md`(2026-09-14 조사)는 `videos.insert` 가 **별도의 Video
Uploads 버킷**에서 `1 call = 1 unit`, 기본 **하루 100건**으로 집계된다고 기록한다.
즉 `10,000 ÷ 1,600` 이라는 계산 자체가 성립하지 않는다.

### 어떻게 고쳤나

숫자를 바꾸는 것보다 **구조**가 중요하다. Google 은 정책을 예고 없이 바꾸고 프로젝트마다
한도가 다르므로, 클라이언트 추정치를 진실로 취급하면 언제든 조용히 틀린다.

- 새 모듈 `autoshorts/quota.py` — 할당량을 **설정 가능한 정책**으로 분리
- 환경변수로 재정의: `AUTOSHORTS_UPLOAD_DAILY_LIMIT`, `AUTOSHORTS_UPLOAD_COST_PER_CALL`,
  `AUTOSHORTS_UPLOAD_LOCAL_GUARD`, `AUTOSHORTS_SEARCH_DAILY_UNITS`, `AUTOSHORTS_QUOTA_VERIFIED`
- 사전 가드는 **느슨한 안내**로 강등, 최종 판정은 **API 응답**
- 할당량 초과 메시지가 추정치를 단정하지 않음:
  "API 가 응답했습니다 … 프로젝트마다 다를 수 있습니다"
- `README.md` · `시작하기.txt` 의 "하루 6건 / 1,600 유닛" 문구 갱신
- 회귀 테스트로 낡은 상수 부활 차단 (`TestNoStaleConstantsInSource`)

### ⚠️ 재검증이 필요하다

**이 환경에서는 공식 문서를 직접 확인하지 못했다.** `developers.google.com` 이 개발
환경의 egress 정책으로 차단된다(`EGRESS_BLOCKED`). 따라서 기본값 100건/1유닛은
**로드맵 문서의 조사 결과를 옮긴 것이며 1차 출처로 검증되지 않았다.** 코드는 이 상태를
`verified=False` 로 명시하고 사용자 안내에 "(미검증 기본값)" 을 붙인다.

**수동 확인 절차** (배포 전 필수)

1. https://developers.google.com/youtube/v3/determine_quota_cost 에서 `videos.insert` 비용 확인
2. https://developers.google.com/youtube/v3/docs/videos/insert 에서 업로드 버킷/한도 확인
3. Google Cloud Console → API 및 서비스 → YouTube Data API v3 → 할당량에서 **해당 프로젝트의 실제 한도** 확인
4. 값이 다르면 `.env` 에 `AUTOSHORTS_UPLOAD_DAILY_LIMIT` 설정
5. 확인 완료 후 `AUTOSHORTS_QUOTA_VERIFIED=1` 로 "(미검증)" 표시 제거

---

## 3. 측정된 기준선 (transcript-only)

### 측정 방법

- 도구: `autoshorts benchmark <manifest.json>` (신규)
- 샘플: espeak-ng 합성 한국어 내레이션(122초)을 스트림 복사로 이어붙인 10분/30분 소스
- 권리 상태: `owned` (직접 합성)
- gold moment: 수치·훅이 있는 문장 4개를 지정

### 성능

| 샘플 | 소스 길이 | 총 처리 | 초/소스분 | peak RSS | 출력 |
|---|---|---|---|---|---|
| 10분 | 610초 | 64.8초 | 6.37 | 271 MB | 9.4 MB (3편) |
| 30분 | 1,831초 | 67.2초 | 2.20 | 273 MB | 9.2 MB (3편) |

단계별 (30분 샘플): ingest 7.5초 · **transcribe 0초(미측정)** · analyze 0.17초 · render 59.5초

처리 시간의 **90% 이상이 렌더링**이다. 클립 수에 비례하므로 소스가 길어져도 총 시간은
크게 늘지 않는다(초/소스분이 6.37 → 2.20 으로 감소). peak RSS 는 소스 길이와 무관하게
~273MB 로 안정적이다.

### 품질

| 지표 | 10분 | 30분 | Beta 목표 |
|---|---|---|---|
| render success | 100% | 100% | ≥ 98% ✅ |
| mid-sentence cut | **33%** | 0% | ≤ 5% ❌ |
| duplicate overlap (시간) | 0% | 0% | — ✅ |
| **gold acceptance** | **0%** | **0%** | ≥ 80% ❌ |
| 문맥 의존 시작 | 0% | 0% | — ✅ |
| 평균 클립 길이 | 43.9초 | 43.9초 | 30~60초 ✅ |

---

## 4. 알려진 한계 (Phase 4~5 가 해결해야 할 것)

측정이 드러낸 문제를 **고치지 않고 기록만 한다.** Phase 0 범위가 아니다.

### A. 내용 수준 중복을 전혀 감지하지 못한다 — 심각

30분 샘플에서 선정된 클립 3개가 **제목·점수·내용이 모두 동일**했다.

```
1: 131.2~174.5s  점수 86.2  결론부터 말씀드리면, 대부분의 사람들이 첫
2: 985.8~1029.1s 점수 86.2  결론부터 말씀드리면, 대부분의 사람들이 첫
3: 1596.2~1639.5s 점수 86.2  결론부터 말씀드리면, 대부분의 사람들이 첫
```

시간축 중복 제거(`normalize_clips` 의 1초 규칙)는 통과한다 — 타임스탬프가 다르기 때문이다.
하지만 결과물은 **사실상 같은 쇼츠 3편**이다. 반복이 있는 소스(재방송, 하이라이트 모음,
같은 말을 여러 번 하는 강의)에서 그대로 재현된다.

→ Phase 4 candidate ranking 에 **내용 유사도 기반 dedup** 이 필요하다.

### B. 사람이 지정한 하이라이트를 하나도 잡지 못했다

`gold_acceptance = 0.0` (양쪽 샘플). 오프라인 휴리스틱은 발화 밀도·훅 표현·수치로만
점수를 매기므로, 사람이 "여기가 핵심" 이라고 본 구간과 체계적으로 어긋난다.

**단, 이 수치는 약한 증거다.** gold moment 를 엔진 작성자가 직접 지정했고 소스가 합성
반복 영상이다. 제대로 된 판단을 하려면 `COMPETITIVE_BENCHMARK_2026.md` 가 요구하는
**30~50편의 실제 영상 + 제3자 gold 라벨**이 필요하다. 지금 확정할 수 있는 것은
"측정 장치가 동작하고, 현재 기준선이 이 세트에서 0% 였다" 까지다.

### C. 문장 중간 절단이 목표를 크게 넘는다

10분 샘플 33% (목표 ≤5%). `ai_analyzer.snap_to_segments` 의 허용치(2.5초) 안에 발화
경계가 없으면 그대로 자른다. Phase 4 의 narrative boundary engine 대상이다.

### D. 리프레이밍은 화면 내용을 보지 않는다

현재 `video_renderer.py` 는 blur 배경 또는 **고정 중앙 크롭**뿐이다. 얼굴·화자·중요
영역을 추적하지 않으므로 화자가 화면 가장자리에 있으면 잘린다. 벤치마크에
`reframe failure` / `face crop violation` 지표를 넣지 못한 이유도 이것이다 —
측정할 대상 기능이 아직 없다. Phase 5 범위.

### E. 자막은 고정 스타일이다

`subtitles.py` 는 단어별 강조가 되지만 키워드 강조·애니메이션 프리셋·안전영역 인식이
없다. Phase 6 범위.

### F. 이 환경에서 측정하지 못한 것

| 항목 | 이유 |
|---|---|
| **transcribe 단계 소요** | `huggingface.co` 차단으로 Whisper 모델을 받을 수 없음. 전사본을 캐시로 주입해 우회했고 해당 구간은 0초로 기록됨 |
| **STT 정확도** | 위와 동일 + 소스가 합성 음성이라 애초에 유효한 평가 불가 |
| **실제 YouTube 업로드** | `youtube.com` 차단. 요청 조립·오류 분류·할당량 가드까지만 가짜 service 로 검증 |
| **60분 소스** | 10/30분에서 초/소스분이 이미 감소 추세라 추가 정보가 적고, 디스크·시간 대비 이득이 낮다고 판단. 도구는 길이 제한이 없으므로 실기 환경에서 실행 가능 |
| **Windows 스모크** | 리눅스 컨테이너. `scheduler.py` 의 schtasks 경로는 단위 테스트(dry-run 문자열)로만 검증됨 |

---

## 5. private 업로드 실기 검증 절차 (수동)

**이 절차는 자동 실행하지 않는다.** 실제 업로드는 외부 부작용이므로 사람이 수행한다.

### 사전 점검 (업로드 없음)

```bash
python scripts/smoke_upload.py output/output_01_제목.mp4
```

인증 자산·라이브러리·할당량 정책·요청 본문 규격·쇼츠 적격성을 확인한다.
**이 스크립트는 어떤 업로드도 하지 않는다.**

### 실기 절차

1. Google Cloud Console 에서 '데스크톱 앱' OAuth 클라이언트 생성 → `~/.autoshorts/client_secret.json`
2. `autoshorts login` — 브라우저 인증 (최초 1회)
3. 30초 내외 테스트 클립 1편을 준비
4. `autoshorts upload <파일> --privacy private`
5. YouTube Studio 에서 확인할 것:
   - 업로드 성공, 공개 범위가 **비공개**
   - 쇼츠로 인식되는가 (9:16, 3분 이내)
   - 자막이 화면 안에 들어오는가
   - 제목/설명이 의도대로인가
6. `autoshorts upload <파일> --privacy private --publish-in 1h` 로 예약 공개 확인
7. 확인 후 **테스트 영상 삭제**

### 기록할 것

| 항목 | 값 |
|---|---|
| 업로드 소요 시간 | |
| 응답 video_id | |
| 실제 적용된 privacyStatus | |
| 쇼츠 인식 여부 | |
| 오류 발생 시 응답 원문 | |

> ⚠️ 2020-07-28 이후 생성된 **미검증 API 프로젝트**는 업로드가 private 로 제한될 수 있다.
> public/scheduled publish 를 상용 기능으로 약속하기 전에 API compliance audit 가 필요하다.
> Beta 는 **private upload + 사람 검토** 로 간다.

---

## 6. 소스 권리 확인이 필요한 지점

`rights_status` 어휘를 `owned | licensed | creative_commons | unverified` 로 고정하고
벤치마크 스키마에 먼저 반영했다(Phase 1 JobSpec 과 같은 어휘).

### 코드에서 이미 반영된 것

- `BenchmarkSample.rights_status` — 기본값 `unverified`
- `BenchmarkSample.needs_rights_confirmation`
- `benchmark_runner.run_sample` — `unverified` 소스는 **처리하지 않고 건너뛴다**
  (테스트로 고정: `test_skips_unverified_rights`)

### Phase 1 이후 필요한 것

| 지점 | 요구사항 |
|---|---|
| JobSpec | `rights_status` 필수 필드, 기본값은 `unverified` |
| 렌더 진입 | `unverified` 면 approval gate 통과 없이는 production render 금지 |
| 업로드 진입 | `unverified` 면 업로드 차단 |
| `trend_finder` 결과 | 탐색 결과는 **권리 확인된 소스가 아니다**. UI 가 이를 명시해야 함 |
| DB | `rights_confirmations` 테이블 — 확인자·확인 시각·근거 URL·라이선스 종류 |
| UI | 프로젝트 생성 시 권리 상태를 **사용자가 명시적으로 선택**, 기본값 없음 |

### 표현 규칙

- Creative Commons 를 "법적 안전 보장" 으로 표시하지 않는다.
- 라이선스 근거(`source URL`, `checked_at`, `attribution`)를 저장한다.
- "이 영상은 재사용 가능합니다" 같은 단정을 제품이 대신하지 않는다.

---

## 7. 최소 품질 게이트

기존 구조를 바꾸지 않는 선에서 회귀만 막는다.

```toml
[tool.ruff.lint]
select = ["F", "E9", "I"]   # 논리 오류 · 구문 오류 · import 정렬
```

- `ruff check autoshorts/ tests/ scripts/` — 현재 통과
- 엄격한 타입 검사(mypy/pyright)는 **Phase 1** 에서 JobSpec/JobResult contract 와 함께
  도입하는 것이 비용 대비 효과가 크다. 지금 전면 도입하면 기존 코드 대규모 수정이 필요해
  Phase 0 의 "대규모 리팩터링 금지" 와 충돌한다.
- CI(`.github/workflows/autoshorts.yml`)에 lint 단계 추가를 Phase 1 에서 제안한다.

---

## 8. Phase 1 로 넘기는 위험과 기술 부채

| # | 항목 | 심각도 | 근거 |
|---|---|---|---|
| R1 | 내용 수준 중복 미감지 | **높음** | 30분 샘플에서 동일 내용 3편 생성 (§4-A) |
| R2 | gold acceptance 0% | **높음** | 측정됨. 단 gold set 자체가 부실 (§4-B) |
| R3 | mid-sentence cut 33% | 높음 | 목표 ≤5% (§4-C) |
| R4 | 리프레이밍이 화면을 보지 않음 | 높음 | 기능 부재 (§4-D) |
| R5 | 할당량 기본값 미검증 | 중간 | egress 차단 (§2) |
| R6 | 실제 업로드 미검증 | 중간 | egress 차단 (§4-F) |
| R7 | STT 품질/시간 미측정 | 중간 | 모델 저장소 차단 (§4-F) |
| R8 | 실제 gold set 부재 | 중간 | 30~50편 + 제3자 라벨 필요 |
| R9 | Windows 실기 미검증 | 낮음 | dry-run 문자열만 검증 |
| R10 | 저장소에 무관한 앱 공존 | 낮음 | 루트에 학원 관리노트. 상용화 전 분리 권장 |

---

## 9. 재현 방법

```bash
# 테스트
python -m pytest                    # 548 passed, 1 skipped
ruff check autoshorts/ tests/ scripts/

# 벤치마크 (매니페스트 검증만)
autoshorts benchmark manifest.json --validate-only

# 벤치마크 실행
autoshorts benchmark manifest.json --report-dir results \
  --max-clips 3 --preset ultrafast --crf 28

# 업로드 사전 점검 (업로드 없음)
python scripts/smoke_upload.py output/output_01_제목.mp4
```

매니페스트 스키마는 `autoshorts/benchmark.py` 의 `SampleManifest` / `BenchmarkSample` /
`GoldMoment` 를 따른다.
