# 벤치마크 세트

기능이 늘었는지가 아니라 **결과물이 좋아졌는지**를 재기 위한 기준선입니다.
Phase 0 에서는 측정 도구와 manifest 구조만 준비했습니다. 실제 영상은 권리 확인이
끝난 것으로 직접 채워야 합니다.

## 쓰는 법

```bash
# 전체 측정
autoshorts benchmark benchmarks/manifest.json --report out/bench.json --markdown out/bench.md

# 길이 구간만 골라서 (10분짜리부터 확인할 때)
autoshorts benchmark benchmarks/manifest.json --only 10
autoshorts benchmark benchmarks/manifest.json --only 10,30
```

영상 한 편이라도 산출물이 없으면 종료 코드가 `1` 입니다 — CI 에서 그대로 쓸 수 있습니다.

## manifest 구조

`manifest.example.json` 이 실제 예시입니다. 필드 의미:

| 필드 | 필수 | 뜻 |
|---|---|---|
| `id` | O | 영상 식별자. 보고서의 행 이름이 됩니다. 중복 금지 |
| `source` | O | YouTube URL 또는 로컬 파일 경로 |
| `duration_bucket` | 권장 | 길이 구간(분). `10` / `30` / `60` — `--only` 로 고를 때 씁니다 |
| `content_mode` | 권장 | `auto` `podcast` `lecture` `gaming` `sports` `news` `vlog` |
| `rights_status` | 권장 | `owned` `licensed` `creative_commons` `unverified` |
| `gold_moments` | 권장 | 사람이 지정한 정답 구간. 영상마다 3~5개 |
| `notes` | | 나중에 결과를 해석할 때 필요한 특징 (화자 수, 화면 공유, 흔들림 등) |

`autoshorts benchmark` 는 실행 전에 manifest 를 검사하고 문제를 경고로 출력합니다
(알 수 없는 `content_mode`, 뒤집힌 구간, 중복 `id` 등). 경고가 있어도 측정은 계속합니다.

## 목표 구성 (`COMPETITIVE_BENCHMARK_2026.md` §6)

최소 30~50편. 분포:

| 종류 | 편수 |
|---|---|
| podcast / interview | 10 |
| lecture / education | 8 |
| gaming / stream | 8 |
| sports / high-motion | 6 |
| news / commentary | 5 |
| vlog / product demo | 5 |

각 영상에 사람이 gold moment 를 3~5개 지정합니다. 이것이 없으면 적중률
(`gold_acceptance`)이 측정되지 않고 `—` 로 남습니다.

## 지금 재는 것 / 아직 못 재는 것

**Phase 0 에서 재는 것**

- 처리시간 (전체, 스테이지별 — `ingest` / `transcribe` / `analyze` / `render`)
- 원본 1분당 처리시간
- peak memory (FFmpeg 등 자식 프로세스 포함)
- 산출물 개수·총 바이트
- render 성공률
- 문장 중간 절단률 — 클립 경계가 단어 내부이거나 문장을 끝맺지 않은 비율
- 클립 간 중복률
- gold moment 적중률 (정답 구간이 있을 때만)

**아직 못 재는 것** (도구가 없어서가 아니라 기능이 없어서)

- reframe 실패율 / face crop violation / framing jitter — 얼굴·활성화자 검출이
  없습니다(Phase 5)
- standalone 이해도 — 사람 평가 또는 narrative 엔진이 필요합니다(Phase 4)
- subtitle edit rate — 편집기가 없습니다(Phase 5)
- cost / source minute — 원가 원장이 없습니다(Phase 2)

위 항목은 해당 Phase 에서 이 도구에 지표를 더해 가며 채웁니다. Phase 0 의 목표는
**측정 자리를 만들고 지금 값을 고정**하는 것입니다.

## 주의

- `rights_status` 가 `unverified` 인 영상의 결과물은 **공개용으로 쓰지 않습니다.**
  Phase 0 은 분류만 하고 권리 판정은 하지 않습니다.
- `creative_commons` 를 "법적으로 안전하다"는 뜻으로 읽지 않습니다. 라이선스 근거와
  확인 시각을 따로 남겨야 합니다(Phase 7).
- 측정 결과는 **기기와 설정에 따라 달라집니다.** 보고서에 환경(`platform`, `python`,
  `processor`, 측정 시각)이 함께 기록되니, 비교할 때 같은 기기인지 확인하세요.
