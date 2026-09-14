# Claude Code Master Plan v3 — AutoShorts Full SaaS + Competitive Quality

작성일: 2026-09-15

이 문서는 기존 v1/v2 문서를 폐기하지 않고 **상위 쇼츠 자동화 제품의 기능 비교 결과를 추가 반영한 최신 실행 순서**다.

## 0. Claude Code 시작 시 반드시 읽을 문서

Claude Code에서 아래 문서를 순서대로 읽는다.

1. `docs/COMMERCIALIZATION_ROADMAP.md`
2. `docs/DEVELOPMENT_PROMPTS.md`
3. `docs/PRODUCT_BLUEPRINT_V2.md`
4. `docs/CLAUDE_CODE_EXECUTION_V2.md`
5. `docs/COMPETITIVE_BENCHMARK_2026.md`
6. `docs/CLAUDE_CODE_MASTER_V3.md`

우선순위 충돌 시 **V3가 최신 실행 기준**이다. 단, 기존 문서의 안전장치와 검증 항목은 삭제하지 않고 합쳐서 적용한다.

---

# Master Guard v3

아래를 Claude Code 첫 메시지로 사용한다.

```text
당신은 AutoShorts 상용 SaaS의 Staff Engineer이자 Video AI 품질 책임자다.

작업 전 반드시 다음 문서를 읽어라.
- docs/COMMERCIALIZATION_ROADMAP.md
- docs/DEVELOPMENT_PROMPTS.md
- docs/PRODUCT_BLUEPRINT_V2.md
- docs/CLAUDE_CODE_EXECUTION_V2.md
- docs/COMPETITIVE_BENCHMARK_2026.md
- docs/CLAUDE_CODE_MASTER_V3.md

중요 원칙:
1. 기존 AutoShorts 엔진을 폐기하거나 새로 갈아엎지 않는다.
2. 기존 pipeline/transcriber/ai_analyzer/video_renderer/subtitles/trend_finder/uploader/tests를 최대한 재사용한다.
3. 경쟁 서비스의 UI/HTML/CSS/카피/브랜드를 복제하지 않는다.
4. 기능 수보다 실제 output quality를 우선한다.
5. 한 번에 한 Phase만 수행한다.
6. 현재 Phase가 GO가 아니면 다음 Phase를 시작하지 않는다.
7. public YouTube upload/실결제/대량 외부 API 작업은 사용자 명시 승인 없이 실행하지 않는다.
8. API key/OAuth token/payment secret을 코드/로그/commit에 남기지 않는다.
9. YouTube/외부 영상은 권리 확인 없이 재사용 가능하다고 가정하지 않는다.
10. 자동화 결과는 human-review 가능하게 설계한다.
11. failed render/provider outage/duplicate job이 사용자 credit을 소모하지 않게 설계한다.
12. 모든 기능은 unit/integration/E2E 또는 재현 가능한 수동 QA evidence를 남긴다.

각 Phase 시작 전:
- 현재 branch/HEAD/git status 확인
- 관련 기존 코드 audit
- 재사용 코드와 새 코드 목록 작성
- 10줄 이내 구현 계획 보고

각 Phase 완료 후 반드시 아래 형식으로 보고하고 멈춰라.

PHASE:
STATUS: GO | NO-GO
SUMMARY:
REUSED CODE:
NEW CODE:
CHANGED FILES:
TESTS:
QUALITY EVIDENCE:
E2E EVIDENCE:
SECURITY/PRIVACY:
COST/QUOTA IMPACT:
KNOWN RISKS:
MANUAL CHECKS:
NEXT PHASE ENTRY CONDITIONS:
COMMIT(S):

내가 명시적으로 다음 Phase를 지시하기 전에는 다음 단계로 진행하지 마라.
```

---

# 최종 Phase 순서

## Phase 0 — Productization Gate
기존 Prompt 0 그대로 수행 + 경쟁 벤치마크용 품질 측정 기반을 준비한다.

추가 요구:
- benchmark sample manifest 구조 정의
- render success/processing time/output quality 측정 형식 추가
- 현재 highlight/reframe/caption의 known baseline을 문서화

아직 multimodal/reframe 기능은 구현하지 않는다.

---

## Phase 1 — Engine Service Boundary
기존 Prompt 1 수행.

추가 contract:

```text
JobSpec
  content_mode: auto | podcast | lecture | gaming | sports | news | vlog
  rights_status: owned | licensed | creative_commons | unverified
  quality_profile: standard | high

JobResult
  stage_timings
  warnings
  quality_checks
  cost_events
```

향후 visual/audio signal provider가 연결될 interface를 만든다. 실제 고급 분석은 Phase 4에서 구현한다.

---

## Phase 2 — SaaS Foundation
기존 SaaS Foundation 수행.

추가 필수:
- usage ledger
- cost ledger
- refundable/reserved credits 상태 설계
- media asset provenance 필드
- job idempotency key
- project version/revision 기반 준비

결제 자체는 아직 구현하지 않는다.

---

## Phase 3 — Full Product Shell + Core Create UX
기존 Full Website/Core UX 요구를 합쳐 구현한다.

이 단계에서 필요한 페이지:
- marketing home
- trending preview
- reusable preview
- pricing placeholder
- private placeholder
- login/signup
- dashboard
- projects
- project create
- processing
- highlight candidates
- review/edit
- result/download

편집기는 아직 full timeline이 아니다.

필수 UX:
- clip preview
- start/end
- title
- caption text
- crop/blur
- regenerate
- human approval state

---

# Phase 4 — Competitive Quality Engine (P0, 최우선 신규 단계)

상위 도구와 경쟁하려면 이 단계가 가장 중요하다.

Claude Code 프롬프트:

```text
Phase 3가 GO인 경우에만 수행한다.

목표:
기존 transcript 중심 highlight selection을 multimodal + narrative-aware 품질 엔진으로 확장한다.
기존 ai_analyzer.py를 폐기하지 말고 candidate generation/ranking pipeline으로 확장한다.

필수 구현:

1. Candidate Signal Interface
- transcript semantic signal
- audio energy/peak/silence signal
- scene-change signal
- motion activity signal
- face presence/activity signal
- optional OCR/on-screen text signal interface

2. Narrative Quality
- standalone understandability
- hook strength
- setup/payoff continuity
- question/answer continuity
- pronoun/context dependency penalty
- filler/ad/CTA penalty
- mid-sentence boundary prevention

3. Score Breakdown
단일 점수만 저장하지 말고:
- hook_score
- narrative_score
- visual_score
- audio_score
- standalone_score
- trend_fit_score(optional when context exists)
- confidence
- risk_flags
- why_selected

4. Content Modes
- podcast/interview
- lecture/education
- gaming/stream
- sports/high-motion
- news/commentary
- vlog/product

Mode별로 signal weight를 다르게 적용할 수 있게 구성한다.

5. Gold-set evaluation harness
30개 이상 sample manifest를 받을 수 있는 evaluation runner를 만든다.
metrics:
- top-N acceptance
- standalone comprehension
- mid-sentence cut rate
- duplicate overlap
- processing time

6. Fallback
visual/audio 분석 provider가 없거나 실패해도 기존 transcript pipeline으로 정상 fallback한다.

금지:
- LLM 응답을 그대로 clip으로 사용
- 새로운 대형 framework로 전체 pipeline 재작성
- 실제 public upload

완료 조건:
- 기존 tests regression 없음
- benchmark runner 존재
- transcript-only baseline과 multimodal candidate의 비교 보고서 생성 가능
- 모든 candidate의 score breakdown/why/risk를 API로 반환

결과는 docs/PHASE4_COMPETITIVE_QUALITY.md에 기록하고 멈춰라.
```

---

# Phase 5 — Smart Reframe 2.0 + Transcript Editor

```text
Phase 4 GO 후에만 수행한다.

목표:
현재 blur/center crop 수준을 active-speaker/saliency aware reframing으로 개선하고,
사용자가 transcript를 편집하면 영상 cut이 따라오는 editor를 제공한다.

Smart Reframe 필수:
- face detection abstraction
- active speaker estimation
- multi-speaker handling
- saliency/content zone tracking
- safe area
- smoothing/hysteresis
- crop jump 방지
- podcast split-screen preset
- gameplay + facecam preset
- center/blur fallback

Transcript Editor 필수:
- transcript search
- sentence click-to-seek
- text delete -> reversible cut edit
- keep/remove
- fine trim
- filler/silence marker
- undo/redo revision
- clip versions

QA:
- multi-speaker sample
- screen-share sample
- gaming facecam sample
- fast-motion sample
- no-face sample fallback

framing jitter와 face crop violation을 측정 가능하게 하라.

docs/PHASE5_REFRAME_TRANSCRIPT_EDITOR.md 작성 후 멈춰라.
```

---

# Phase 6 — Pro Auto Edit Layer

```text
Phase 5 GO 후 수행.

목표:
단순 컷+자막을 넘어 게시 가능한 polished short를 자동으로 만든다.

A. Pro Captions
- word animation
- keyword highlight
- presets
- custom font
- Korean/Japanese/English QA
- safe-zone
- caption-aware overlays

B. Speech Cleanup
- silence trim suggestions
- filler word suggestions
- repeated take detection
- denoise adapter
- loudness normalization
- speaker level normalization
- 모든 삭제는 preview/reversible

C. Auto B-roll
우선순위:
1 user-owned library
2 licensed stock
3 AI generated

- transcript grounded suggestion
- replace/regenerate
- rights/provenance metadata
- caption-aware placement

D. Auto Polish style presets
- zoom
- transition
- SFX
- music
- hook title overlay

과도한 random effect를 금지하고 style preset 기반으로 일관성 있게 적용한다.

E. Brand Kit
- logo/fonts/colors/caption style/intro/outro/watermark/default aspect/audio profile

docs/PHASE6_PRO_AUTO_EDIT.md 작성 후 멈춰라.
```

---

# Phase 7 — Trend + Reusable Source + Growth Intelligence

기존 Trend/Reusable/Growth 계획을 수행한다.

추가 요구:
- Trend Score와 Clip Score를 혼동하지 않는다.
- trend snapshot history로 velocity/acceleration 계산
- competition/channel fit 분리 저장
- Creative Commons는 '법적 안전 보장'이라고 표시하지 않는다.
- license evidence/checked_at/source URL/attribution를 저장한다.
- 추천 소스 -> project creation 연결

우리 제품의 핵심 차별화 단계다.

---

# Phase 8 — YouTube Private-first + Publish Foundation

기존 private-first Web OAuth를 수행한다.

추가:
- publish draft
- approval gate
- idempotent upload
- lost-response reconciliation
- duplicate click 방지
- credit reservation은 upload 성공/실패와 분리

이 단계에서는 YouTube를 우선한다.

---

# Phase 9 — Billing + Credit Protection + Unit Economics

```text
목표:
요금제/사용량/원가뿐 아니라 경쟁 제품에서 불만이 많은 실패 credit 문제를 해결한다.

상태 모델 예:
reserved -> consumed
reserved -> refunded

반드시:
- failed render = 자동 rollback
- provider outage = rollback
- duplicate job = 중복 차감 없음
- user cancel 정책 명확화
- usage/cost ledger immutable event 형태 권장
- workspace/project별 원가
- monthly processing minutes/credits
- plan limits
- webhook idempotency

UI에 차감 사유/환급 사유를 설명 가능하게 한다.

docs/PHASE9_BILLING_CREDITS.md 작성.
```

---

# Phase 10 — Closed Beta Release Gate

이 단계에서 10~30명 beta가 가능해야 한다.

필수 품질 gate:
- render success >= 98% on supported benchmark set
- mid-sentence cut <= 5% 목표
- severe talking-head reframe failure <= 5% 목표
- standalone understandable candidate >= 80% 목표
- failed jobs credit loss = 0

위 수치는 실제 benchmark 결과에 따라 합리적으로 조정할 수 있으나, 조정 이유를 문서화한다.

기존 security/privacy/fault test gate도 모두 수행한다.

---

# Phase 11 — Team / Agency / Pro Workflow

```text
Beta core가 검증된 후 수행.

기능:
- workspace roles
- client brand kits
- project sharing
- review comments
- approval workflow
- multiple social/channel accounts
- API
- webhook
- cloud drive import adapters
- export manifest
- Premiere XML/EDL feasibility spike

먼저 API contract를 안정화하고 integrations를 붙인다.
```

---

# Phase 12 — Multi-platform Calendar & Distribution

YouTube private-first가 안정된 후에만 확대한다.

- YouTube
- Instagram
- TikTok
- LinkedIn

플랫폼별 auth/publishing 정책을 adapter로 분리한다.
각 플랫폼에 동일 metadata를 억지로 쓰지 않고 preset을 갖는다.

---

# Phase 13 — Globalization

후순위:
- subtitle translation
- multilingual metadata
- dubbing
- voice selection
- lip-sync translation

먼저 subtitle translation부터, dubbing/lip sync는 이후 별도 gate로 한다.

---

# Phase 14 — Analytics Feedback Loop

기존 계획 수행.

중요:
AI에게 단순 성공/실패 라벨만 주지 않는다.

분석 dimension:
- topic
- hook type
- clip length
- caption preset
- visual density
- B-roll rate
- publish time
- trend score
- channel fit
- watch/retention signals

추천은 근거를 표시한다.

---

# Phase 15 — Optional Creator Expansion

Core business가 검증된 뒤 검토:
- eye-contact correction
- AI avatars
- teleprompter
- text-to-video
- AI presenter

이 단계는 경쟁사의 기능을 따라가기 위한 것이 아니라 실제 사용자 요청과 revenue impact가 있을 때만 시작한다.

---

# 현재 즉시 실행할 프롬프트

현재 Phase 0 결과가 아직 사용자에게 검토되지 않았다면 Claude Code에는 아래만 입력한다.

```text
Master Guard v3를 적용하라.
위 6개 문서를 모두 읽어라.
현재는 Phase 0만 수행하라.
COMPETITIVE_BENCHMARK_2026.md의 기능들은 backlog/quality requirement로만 반영하고,
Phase 4 이후의 기능 구현을 지금 시작하지 마라.

Phase 0에서는 기존 엔진 baseline을 측정 가능한 상태로 만들고,
현재 highlight/reframe/caption 품질의 known limitations를 기록하라.

완료 후 Master Guard v3 보고 형식으로 결과를 출력하고 멈춰라.
```

Phase 0가 이미 GO 검토를 받은 경우에만 해당 다음 Phase 프롬프트를 실행한다.
