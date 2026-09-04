# 세션 엔진 — 이 Claude Code 세션이 직접 작곡한다

`GOLDEN_ENGINE=session`. API 키 없이, 이 세션의 Claude 가 작곡가·비평가를 맡는다.

```bash
python scripts/session_golden.py --ids g01 g02 g03 --measures 24
python scripts/session_golden.py --ids g05 --measures 32 --no-wait   # 기다리지 않고 다음 프롬프트만
```

## 어떻게 도는가

엔진이 각 단계의 프롬프트를 파일로 내놓고 응답 파일을 기다린다. 사람(또는 이 세션의
Claude)이 프롬프트를 읽고 JSON 을 써 주면 파이프라인이 이어진다.

```
runs/golden/<요청id>/
  motif_prompt.md          motif_response.json      ← 모티브 후보 3~5개
  motif_choice.json                                 ← 어느 후보를 잠글지 (없으면 첫 번째)
  plan_prompt.md           plan_response.json       ← 설계도
  phrase_01_04_prompt.md   phrase_01_04_response.json
  phrase_05_08_prompt.md   phrase_05_08_response.json
  ...
  critic_prompt.md         critic_response.json     ← 루브릭 10항목 + 수정 지시
  phrase_09_12_fix_prompt.md  ...                   ← 다듬기 패스가 필요할 때만
```

프롬프트 파일에는 네 가지가 들어 있다 — 시스템 지시(`generation/prompts/*.md`),
고정 컨텍스트(학생 제약·콩쿨 규정·코퍼스 요약), 이번 요청, **출력 JSON 스키마**.
스키마를 벗어난 응답은 `<단계>_error.txt` 에 무엇이 틀렸는지 남기고 거부된다.

## 무엇이 코드로 남는가

**전부다.** 세션 모드라고 검사를 건너뛰지 않는다.

- §7.6 검증기 — 마디 길이·기보 가능한 음길이·손 스팬·음역·손 교차·제한 시간·종지·
  임시표 비율·표절 n-gram·콩쿨 규정. 프레이즈마다 즉시 검증하고, 실패하면 사유를
  지시로 되먹여 최대 3회 다시 요청한다.
- §7.4 음악성 지표 8종, §7.5 비평 루브릭, 다듬기 패스, 난이도 계산 모두 그대로.

즉 이 모드로 만든 곡은 실제 API 로 만든 곡과 **똑같은 관문**을 통과한다.

## 산출물

곡마다 `runs/golden/<id>/` 에 남는다.

| 파일 | 내용 |
|---|---|
| `score.musicxml` | 악보 (MuseScore·Finale·Sibelius 에서 열린다) |
| `score.mid` | 재생·편집용 MIDI (오른손/왼손 트랙 분리) |
| `motif_preview.mid` | 고른 모티브만 따로 듣기 |
| `measures.json` | 내부 표현 (편집·재생성의 입력) |
| `plan.json` · `plan_check.json` | 설계도와 규칙 검사 결과 |
| `validation.json` | 하드 규칙·소프트 경고 전부 |
| `quality.json` | 음악성 지표 + 비평 점수 + 수정 지시 |
| `cost.json` | 호출 수·토큰 수·**API 전환 시 예상 비용** |
| `summary.json` | 위 전부의 요약 한 줄 |

전체 요약표는 `runs/golden/SUMMARY.md`.

## 비용 계산

세션 모드는 실제 지출이 0 이지만 **토큰은 실제로 센다**(문자 수 기반 근사, 1토큰 ≈ 2.2자).
`cost.json` 의 `projection` 이 "이 곡을 실제 API 로 만들었다면 얼마였을지" 를 두 가지로 낸다.

- `cost_usd_no_cache` — 매번 전체 프롬프트를 새로 보내는 경우
- `cost_usd_with_cache` — 고정 컨텍스트가 캐시되는 경우(실제 운영값에 가깝다)

실제 전환 시에는 `messages.count_tokens` 로 재측정하면 정확해진다.

## 운영 엔진과의 관계

`ClaudeComposerEngine`(API 호출)은 그대로 있다. 세 엔진이 같은 `ComposerEngine`
Protocol 을 구현하므로 파이프라인은 어느 쪽인지 모른다.

| 엔진 | 언제 |
|---|---|
| `ClaudeComposerEngine` | 운영. `.env` 에 `ANTHROPIC_API_KEY` 가 있으면 자동 선택 |
| `SessionComposerEngine` | 이 세션이 직접 작곡할 때 |
| `StubComposerEngine` | 테스트·CI·오프라인 데모 |

**API 키는 프로젝트 `.env` 파일에서만 읽는다.** 시스템 환경변수는 쓰지 않는다 —
셸에 키가 떠 있으면 자식 프로세스·로그로 새기 쉽고 어느 키로 돌았는지 추적이 안 된다.
