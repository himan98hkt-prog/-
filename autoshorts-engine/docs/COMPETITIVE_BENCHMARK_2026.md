# 2026 쇼츠 자동화 상위 제품 기능 비교 및 AutoShorts Gap 분석

작성일: 2026-09-15
목적: 상위 AI 클리핑/쇼츠 자동화 제품의 강점을 기능 단위로 분해하고, AutoShorts 상용 SaaS에 반영할 기능 우선순위를 확정한다.

> 주의: 경쟁 서비스의 UI/카피/코드를 복제하지 않는다. 공개된 기능 패턴과 사용자 불만을 제품 요구사항으로만 활용한다.

## 1. 비교 대상

- OpusClip
- Klap
- Vizard
- quso.ai
- Submagic
- Captions
- Riverside Magic Clips
- 2short.ai
- Munch 계열의 trend-aware repurposing 접근

공식 참고:
- https://media.opus.pro/
- https://klap.app/tools/ai-clip-generator
- https://klap.app/tools/youtube-clip-maker
- https://vizard.ai/tools/clip-maker
- https://vizard.ai/pricing
- https://quso.ai/features
- https://submagic.co/features/auto-video-editor
- https://captions.ai/features/edit-with-ai
- https://captions.ai/
- https://riverside.fm/magic-clips
- https://2short.ai/
- https://www.munchstudio.com/resources/step-by-step/how-to-scale-short-form-video-growth-with-munch-ai-ad-creator-strategy

## 2. 상위 제품 핵심 기능 비교

| 기능 | OpusClip | Klap | Vizard | quso.ai | Submagic | Captions | Riverside | 2short.ai | AutoShorts 현재/계획 |
|---|---|---|---|---|---|---|---|---|---|
| 자동 하이라이트 추출 | 강함 | 강함 | 강함 | 강함 | Magic Clips | 지원 | Magic Clips | 지원 | 현재 있음 |
| Virality/Rank Score | 있음 | 있음 | 있음 | 있음 | 제한적 | 제한적 | 마케팅 표현 중심 | 제한적 | 현재 기본 score, 고도화 필요 |
| Prompt/Copilot 기반 클립 지시 | 있음 | 일부 | Agent/AI 편집 계열 | AI manager 계열 | 일부 | 강함 | 제한적 | 미약 | 없음 |
| Transcript 기반 편집 | 일부 | 강함 | 지원 | 일부 | 지원 | 강함 | 강함 | 기본 편집 | 없음 |
| Active speaker / face reframe | 강함 | 강함 | 강함 | 강함 | 자동 reframe | 지원 | layout 기반 | 강함 | 현재 blur/crop 중심, 부족 |
| 다중 화자 처리 | 지원 | 지원 | 명시적 지원 | 지원 | 일부 | 지원 | 강함 | 제한적 | 부족 |
| Animated captions | 있음 | 있음 | 있음 | 있음 | 강함 | 강함 | 있음 | 강함 | 기본 ASS, 스타일 고도화 필요 |
| Filler word / silence removal | 있음/계열 | 제한적 | 지원 | 있음 | 강함 | 강함 | 강함 | 제한적 | 없음 |
| Audio cleanup / denoise / level | 일부 | 제한적 | 일부 | 일부 | clean audio 기능 | 강함 | 강함 | 제한적 | 부족 |
| Auto B-roll | 있음 | 제한적 | 있음 | B-roll library | 강함 | 강함 | 제한적 | 없음 | 없음 |
| AI-generated B-roll | 있음 | 제한적 | 있음 | 일부 | 일부 | 강함 | 없음 | 없음 | 없음 |
| Auto zoom / transitions / SFX / music | 일부 | 제한적 | 일부 | 편집 기능 | 강함 | 강함 | 제한적 | 제한적 | 거의 없음 |
| Brand kit / reusable templates | 있음 | 있음 | 강함 | 강함 | 강함 | 스타일 중심 | preset | 있음 | 계획만 있음 |
| 4K export | 일부 상위 플랜/최근 기능 | 확인 필요 | 있음 | 플랜별 | 제품군별 | 지원 범위 존재 | source/workflow 의존 | 1080p 명시 | 현재 1080p 기본 |
| Multi-aspect output | 있음 | 있음 | 있음 | 있음 | 있음 | 있음 | 있음 | 있음 | 구조상 가능, UX 부족 |
| Schedule / auto-publish | 있음 | 있음 | 있음 | 강함 | 제한적 | 공유 기능 | 제한적 | 공식 페이지상 약함 | YouTube private-first 계획 |
| Multi-platform calendar | 있음 | 있음 | 있음 | 강함 | 제한적 | 제한적 | 제한적 | 없음 | 없음 |
| Team workspace / comments | 있음 | 제한적 | 강함 | 있음 | team 솔루션 | team/creator workflow | 협업 | 제한적 | Workspace 계획 |
| API / automation / integrations | 일부 | 제한적 | API 있음 | 소셜 자동화 | 제한적 | 제한적 | ecosystem | 없음 | 없음 |
| Premiere/XML/advanced handoff | XML 지원 | 없음 | 일부 export | 없음 | 없음 | timeline/manual | separate tracks | 없음 | 없음 |
| Translation / subtitles multilingual | 있음/계열 | 지원 | 130+ 언어 | 50~100+ | 100+ | 100+ + dubbing | 100+ transcript | 다국어 | STT 언어 지원, 제품 UX 부족 |
| Eye contact correction | 없음 | 없음 | 일부 AI editor | 없음 | 지원 | 강함 | 없음 | 없음 | 없음 |
| AI avatars / text-to-video | 비핵심 | 없음 | Agent 확장 | 생성 기능 | 비핵심 | 강함 | 없음 | 아이디어/스크립트 | 없음 |
| Trend/keyword intelligence | 약함 | 약함 | post suggestion | analytics/planner | 약함 | 약함 | 약함 | 약함 | **우리 핵심 차별화** |
| Reusable/licensed source discovery | 없음 | 없음 | 없음 | 없음 | 없음 | 없음 | 없음 | 없음 | **우리 고유 차별화 가능** |
| Feedback loop from actual channel data | 제한적 | 제한적 | analytics | 강함 | 제한적 | 제한적 | 제한적 | 약함 | **우리 장기 핵심** |

## 3. 가장 중요한 시장 신호

공식 기능표보다 더 중요한 것은 실제 사용자들이 반복해서 불평하는 부분이다.

최근 사용자 반응에서 반복되는 문제:

1. AI가 transcript만 보고 잘못된 구간을 고른다.
2. 좋은 visual moment를 놓친다.
3. clip 시작/끝이 문장 중간에서 잘리거나 맥락이 부족하다.
4. 두 명 이상 등장하면 auto-reframe이 튄다.
5. 자동 자막은 생성되지만 결국 수동 수정이 필요하다.
6. failed render나 나쁜 AI draft에도 credit이 소모된다.
7. export 품질이 원본보다 크게 떨어지는 경우가 있다.
8. 모든 것을 자동화한다고 광고하지만 실제로는 human review가 필요하다.

따라서 AutoShorts는 "완전자동" 자체보다 **높은 초안 품질 + 수정하기 쉬움 + 설명 가능한 추천 + 실패 비용 보호**를 우선한다.

## 4. AutoShorts에서 현재 가장 부족한 기능

### P0 — 유료 베타 전에 반드시 필요한 품질 기능

#### A. Multimodal Highlight Intelligence

현재 하이라이트 판단이 transcript/LLM 중심이므로 다음 signal을 결합한다.

- transcript semantics
- audio energy / laughter / applause / silence
- scene changes
- motion intensity
- face/speaker activity
- OCR/on-screen text
- visual novelty
- emotional/audio peaks
- topic completeness

최종 clip score는 한 숫자만 저장하지 않는다.

예:

```text
HighlightScore
  narrative = 0..100
  hook = 0..100
  visual = 0..100
  audio = 0..100
  standalone = 0..100
  trend_fit = 0..100
  channel_fit = 0..100
  confidence = 0..1
```

#### B. Narrative Boundary Engine

- 문장 중간 시작/종료 방지
- 질문 → 답변 구조 보존
- setup → payoff 보존
- 대명사/맥락 의존 구간 감점
- 너무 긴 침묵/광고/CTA 제외
- 후보마다 `why_selected`와 `risk_flags` 제공

#### C. Smart Reframe 2.0

현재 blur/center crop을 넘어선다.

- face detection
- active speaker estimation
- multi-speaker layout
- saliency tracking
- screen-share/content zone detection
- safe-area aware crop
- hysteresis/smoothing으로 화면 점프 방지
- podcast split-screen preset
- gaming: gameplay + facecam layout

#### D. Transcript Editor

영상 timeline을 처음부터 만들기보다 transcript를 편집하면 영상이 같이 바뀌게 한다.

- 문장 클릭 → 해당 시간 seek
- text delete → segment cut
- keep/remove highlight
- start/end fine trim
- search transcript
- filler/silence markers
- undo/redo

#### E. Export Quality Guard

- 최소 1080p 품질 유지
- source fps/bitrate 정보를 보존한 preset
- export validation(ffprobe)
- audio/video sync 검사
- zero-byte/깨진 파일 차단
- 지원 가능한 경우 4K tier 준비
- quality regression test sample set

### P1 — 경쟁 상위권 품질을 만드는 편집 기능

#### F. Pro Captions

- word-by-word animation
- keyword highlight
- sentence/word grouping
- emoji/graphic presets
- safe-zone
- caption-aware B-roll positioning
- custom fonts
- brand presets
- Korean/Japanese/English typography QA

#### G. Speech Cleanup

- filler words
- silence trimming
- repeated take detection
- pacing control
- denoise
- loudness normalization
- speaker level normalization

모든 제거는 destructive auto-apply보다 preview/reversible edit로 설계한다.

#### H. Auto B-roll / Media Layer

우선순위:
1. user-owned media library
2. licensed stock provider
3. AI-generated image/video

기능:
- transcript keyword 기반 insertion suggestion
- 2~5초 B-roll cutaway
- caption-aware placement
- regenerate/replace
- rights/source metadata 저장

#### I. Auto Polish

- zoom
- transitions
- sound effects
- background music
- punch-in
- pattern interrupt
- hook title overlay

중요: 한 번에 과도하게 넣지 않고 style preset 기반으로 일관되게 적용한다.

### P2 — 성장/운영/Agency 기능

#### J. Clip Copilot / Prompt Editing

예:
- "이 영상에서 비용 절감 이야기만 찾아줘"
- "30초 이하로 더 공격적으로 잘라줘"
- "웃긴 장면 중심으로 5개 만들어줘"
- "초보자도 이해되는 구간만"
- "이 클립을 15초 버전으로 다시 만들어줘"

Prompt는 실제 editing commands/selection constraints로 변환하고 실행 결과를 diff로 보여준다.

#### K. Brand Kit

- logo
- fonts
- colors
- caption preset
- intro/outro
- watermark
- hook-title preset
- default aspect ratio
- default audio profile

#### L. Multi-platform Publish & Calendar

YouTube private-first가 안정된 후:
- YouTube
- Instagram
- TikTok
- LinkedIn

플랫폼별 metadata/crop/export preset을 분리한다.

#### M. Team / Agency

- workspace members
- roles
- project sharing
- review comments
- approval
- brand kits per client
- channel accounts per workspace
- audit logs

#### N. Pro Workflow / API

- REST API
- webhook
- export manifest
- Premiere-friendly XML/EDL 연구
- Google Drive/Dropbox source connector
- Zapier/Make-friendly webhook payload

### P3 — 후순위 확장

- subtitle translation
- dubbing
- lip-sync translation
- eye-contact correction
- AI avatars
- teleprompter
- text-to-video

이 기능들은 강력하지만 Long→Short 핵심 품질이 검증되기 전에 만들지 않는다.

## 5. 우리가 경쟁 제품보다 차별화해야 할 기능

### 1) Trend-to-Create

일반 clipper는 "내 영상에서 clip 생성"이 중심이다.
우리 제품은 "무엇을 만들지"부터 돕는다.

- realtime-ish trending feed
- velocity/acceleration
- category/region filters
- competitor outliers
- Opportunity Score
- one-click Create Project

### 2) Rights-aware Reusable Library

- Creative Commons 표시
- user-owned source
- licensed source
- attribution generator
- source license snapshot
- rights confirmation gate

"재사용 가능"을 법적 보장처럼 표현하지 않고 evidence + user confirmation으로 설계한다.

### 3) Explainable Scores

Virality Score 한 숫자 대신 component breakdown을 보여준다.

```text
Hook 91
Narrative 84
Visual 77
Trend Fit 95
Channel Fit 88
Risk: context-dependent pronoun
```

### 4) Performance Feedback Loop

실제 publish 결과를 다시 학습 신호로 사용한다.

- views velocity
- watch time
- retention
- CTR(가능한 범위)
- engagement
- subscribers gained
- topic/length/hook/style correlation

### 5) Credit Protection

차별화 제안:
- failed render → credit 자동 rollback
- provider outage → credit rollback
- duplicate idempotent job → 중복 차감 금지
- 명확한 usage ledger

### 6) Human-in-the-loop by design

완전자동 공개가 아니라:

AI Draft → Explain → Preview → Edit → Approve → Publish

를 기본 workflow로 한다.

## 6. 내부 품질 벤치마크 세트

상위 제품과 경쟁하려면 기능 유무보다 output quality를 측정해야 한다.

최소 30~50개 테스트 영상을 만든다.

콘텐츠 분포:
- 10 podcast/interview
- 8 lecture/education
- 8 gaming/stream
- 6 sports/high-motion
- 5 news/commentary
- 5 vlog/product demo

각 영상마다 사람이 gold moment를 3~5개 지정한다.

추적 지표:
- Top-N candidate acceptance rate
- standalone comprehension rate
- mid-sentence cut rate
- duplicate/overlap rate
- subtitle edit rate
- reframe failure rate
- face crop violation
- framing jitter count
- render success rate
- processing time / source minute
- output/source quality delta
- cost / source minute

초기 Beta target 예시:
- render success >= 98% on supported inputs
- mid-sentence cut <= 5%
- severe reframe failure <= 5% on talking-head set
- candidate standalone-understandable >= 80%
- failed jobs never consume final credits

수치는 초기 데이터로 재조정하되, 측정 자체를 생략하지 않는다.

## 7. 개발 우선순위 결론

상위 제품을 모두 따라 만드는 것이 목표가 아니다.

우선순위는:

1. **Clip quality** — multimodal + narrative
2. **Reframe quality** — active speaker/saliency/multi-speaker
3. **Editability** — transcript editor + Copilot
4. **Presentation quality** — captions/audio/B-roll/polish
5. **Our moat** — trend + reusable source + explainable opportunity
6. **Distribution** — private-first publish → calendar
7. **Business** — billing/team/API
8. **Advanced AI** — dubbing/avatar/eye contact later

이 우선순위를 `CLAUDE_CODE_MASTER_V3.md`의 단계별 실행 기준으로 사용한다.
