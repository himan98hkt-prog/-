# 개발 지시서 v3 — 학생 맞춤형 AI 독창곡 · 콩쿨 악보 생성기 + 오디오→MIDI 연주 시각화 릴스 메이커

> 프로젝트 코드명: **ConcoursComposer**
> 작성일: 2026-08-31 (v3: 작곡 품질 전략 재점검 — 모티브 우선 공동작곡·비평 루프·콩쿨 모드·연주회 프로그램 추가) · 대상: Claude Code
> 이 파일을 저장소 루트의 `SPEC.md`로 두고, `CLAUDE.md`는 §12를 그대로 복사해 만든다. 각 마일스톤은 **완료 기준(Acceptance)** 을 모두 통과해야 다음으로 넘어간다.

---

## 0. 한 줄 요약

하나의 웹 애플리케이션에 두 축을 담는다.

- **A. 작곡 축** — 원장이 학생의 수준·손 크기·성향·콩쿨 부문을 입력하면, 축적된 참고 악보에서 추출한 스타일·난이도 데이터를 바탕으로 AI가 연주 가능한 독창곡을 MusicXML로 생성하고, 악보 표시 · 재생 · 마우스 편집 · 연주법 해설 · MP3/PDF/MusicXML 내보내기까지 처리한다.
- **B. 시각화·릴스 축** — 생성곡, 업로드 MIDI, 또는 **학생 연주 오디오/영상**(→ AI 채보로 MIDI 추출)을 입력받아 **Synthesia 스타일 낙하 노트 + 건반 연주 영상**을 렌더하고, 학원 브랜드·자막·하이라이트 구간이 들어간 **9:16 릴스/쇼츠 MP4**를 원클릭으로 만든다.

두 축은 같은 데이터(MIDI/MusicXML, 학생 프로필, 브랜드 자산)를 공유한다. 생성곡은 "악보 → 릴스", 학생 연주는 "영상 → MIDI → 릴스 → (선택) 악보 초안"으로 흐른다.

---

## 1. 배경과 목표

### 1.1 문제
- 콩쿨 시즌마다 학생마다 맞는 곡을 찾는 데 시간이 많이 든다. 기성곡은 난이도·길이·손 크기·학생의 강점에 정확히 맞지 않는다.
- 원장이 직접 작곡·편곡하면 악보·음원·연주법 정리까지 곡당 며칠이 걸린다.
- 학원 마케팅용 릴스(학생 연주 영상, 신곡 소개)를 만들려면 촬영 → 편집앱 → 자막 → 업로드까지 수작업이 반복된다. 낙하 노트 영상(Synthesia류)은 MIDI가 있어야 하는데, 학생 연주는 오디오뿐이라 만들지 못했다.

### 1.2 목표 (성공 지표)
| 지표 | 목표 |
|---|---|
| 요청 → 1차 악보 생성 시간 | 90초 이내 (32마디 기준) |
| 생성곡의 "수정 없이 바로 쓸 수 있는 비율" | 원장 평가 60% 이상 (v1), 80% (v2) |
| 난이도 제약 위반율 | 0% (검증기 강제) |
| 참고 코퍼스 대비 표절 유사도 | 8마디 이상 동일 멜로디 n-gram 0건 |
| 재생 지연 | 재생 버튼 → 첫 소리 500ms 이내 |
| 오디오→MIDI 채보 정확도 (피아노 독주, 스마트폰 녹음) | 노트 onset F1 ≥ 0.85 (MAESTRO 기준 모델 성능 대비 현장 녹음 목표) |
| 릴스 제작 시간 | 60초 영상 기준 입력 → MP4 완성 3분 이내 (CPU), 자막·브랜드 포함 |
| 릴스 미리보기 | 브라우저에서 30fps 실시간 프리뷰 |

### 1.3 비목표 (v1에서 하지 않는 것)
- 오케스트라/앙상블. **v1은 피아노(2단 보표, 88건반)만.**
- 다중 악기 오디오(밴드·보컬 포함) 채보. 피아노 독주 녹음만.
- 상용 편집기 수준의 자유 조판 편집. 편집은 "음악적 수정"에 집중.
- 영상 편집기(컷 편집·전환 효과 라이브러리). 릴스는 **템플릿 기반 자동 생성**.
- SNS 직접 업로드 — 기존 릴스 업로더 프로그램에 완성 파일을 넘기는 **출력 폴더/웹훅 연동만** 제공.

### 1.4 작곡은 어떻게 이루어지는가 — 현실적 기대치와 품질 전략 (v3 핵심)

**작곡 주체**: 이 프로그램은 Anthropic Claude API를 호출한다. 채팅창의 Claude와 같은 모델 계열이며, 프로그램이라서 품질이 떨어지지는 않는다. 오히려 채팅에서는 불가능한 것을 한다 — (1) 학생 제약과 코퍼스 스타일 데이터를 매번 정확히 주입하고, (2) 결과를 코드로 검증해 틀린 곡을 자동 폐기하며, (3) 여러 안을 만들어 자동 채점 후 비평·수정 루프를 돌리고, (4) 원장의 선택과 피드백을 축적해 프롬프트를 개선한다. **품질을 결정하는 것은 모델이 아니라 이 파이프라인의 설계**다.

**솔직한 한계**: 언어모델이 한 번에 32마디를 써내면 "문법은 맞는데 밋밋하거나 앞뒤가 따로 노는" 곡이 나오기 쉽다. 이것이 유일한 진짜 위험이며, v3는 이를 막기 위해 작곡 방식을 **"한 번에 생성"에서 "작곡가가 일하는 순서"로 바꾼다**:
1. **모티브 우선** — 2~4마디 모티브 후보 3~5개를 먼저 만들고 들어본 뒤 원장이 고른다(또는 흥얼거린 멜로디를 녹음→채보해서 모티브로 씀). 좋은 곡은 좋은 모티브에서 나온다.
2. **설계 승인** — 형식·화성 계획·클라이맥스·학생 강점을 보여줄 구간을 원장이 확인·수정한 뒤에 채운다.
3. **모티브 전개 기법을 명시적으로 지시** — 반복·동형진행·전위·확대/축소·역행·조바꿈·텍스처 변화를 프레이즈마다 지정해 "동기 일관성"을 구조적으로 보장한다.
4. **비평 루프** — 생성된 곡을 별도 "비평가 Claude"가 작곡가 루브릭(§7.5)으로 채점하고 구체적 수정 지시를 내리면 작곡 Claude가 고친다(최대 2회). 규칙 기반 음악성 지표(§7.4)와 함께 문턱을 넘어야 원장에게 보인다.
5. **원장 최종 편곡** — 에디터의 구간 재생성·직접 편집. 크레딧은 "작곡 AI 초안 · OOO 편곡".

**콩쿨 입상·대상에 대해**: 입상은 곡 + 학생 연주 + 심사위원 취향의 결과이며 어떤 소프트웨어도 이를 보장할 수 없다. 이 시스템이 할 수 있는 것은 **입상 확률을 구조적으로 높이는 것**이다 — 부문 규정(제한 시간·암보·반복 허용)을 어기지 않게 하고, 학생의 강점이 드러나는 쇼케이스 구간을 설계하고, 심사위원이 듣는 첫 8마디·클라이맥스·마무리를 강하게 만들고, "모의 심사"(§6.13)로 약점을 미리 찾고, 실제 대회 결과를 기록해 다음 곡에 반영한다. **대회마다 창작곡·자유곡 허용 여부와 악보 제출 규정이 다르므로, 곡을 만들기 전에 반드시 규정을 확인하고 콩쿨 프로필(§6.13)에 입력한다.**

**연주회**: 학생별 맞춤곡을 여러 명 분량으로 만들고, 프로그램 순서·대비·총 러닝타임을 맞추고, 곡 해설이 담긴 프로그램북 PDF까지 만드는 "연주회 프로그램 빌더"(§6.14)를 포함한다.

---

## 2. 경쟁·유사 프로그램 정밀 분석과 우리의 포지션

### 2.1 작곡·악보 영역
| 제품 | 분류 | 강점 | 우리 목적에서의 한계 |
|---|---|---|---|
| **MuseScore Studio 4.x** (무료) | 악보 편집기 | 무료 최고 수준 편집·조판, Muse Sounds, MusicXML/MIDI/PDF/MP3, **CLI 변환기** | 작곡 기능 없음. 학생 맞춤 개념 없음 |
| **Flat.io** | 웹 악보 편집기 | 브라우저 편집, 협업, 교육 플랜, 임베드 SDK(유료) | 작곡 AI 없음, 임베드 종속 |
| **Dorico / Sibelius** | 전문 조판 | 출판급 | 고가, 자동화 제한. Finale는 2024년 단종 |
| **NotaGen** (오픈소스, IJCAI 2025) | AI 기보 생성 | 160만 장 ABC 사전학습 + 클래식 9천 곡 "시대-작곡가-편성" 조건부 미세조정, 출력이 악보 | 추론 GPU 40GB, 난이도·손 스팬 제어 불가, 편집·해설 없음 |
| **Remusic.ai, MuseScore AI 류** | AI 악보 SaaS | "난이도·음역 제한" 문구 | 제약 강제 불투명, 한국 콩쿨 기준·해설·자기 코퍼스 없음 |
| **AIVA / Suno / Udio** | AI 오디오 | 음원 품질 | 악보 없음/부정확 |

### 2.2 채보·시각화·릴스 영역 (v2 추가)
| 제품 | 분류 | 강점 | 한계 |
|---|---|---|---|
| **Synthesia** (앱) | 낙하 노트 학습 앱 | 낙하 노트 UX의 원조, MIDI 키보드 연동 | 영상 내보내기 목적 아님, 오디오 입력 불가, 브랜딩 불가 |
| **SeeMusic / PianoVFX / Embers** | MIDI 연주 시각화 영상 제작 | 화려한 파티클·조명 효과, 유튜브 피아노 채널 표준 | 데스크톱 전용, MIDI 필수(오디오 채보 없음), 릴스 자막·템플릿·학생 데이터 없음, 유료 |
| **MIDIVisualizer, Piano From Above** (오픈소스) | MIDI 시각화 | 무료, 렌더 품질 준수 | 오디오 채보 없음, 자동화·브랜딩·세로 포맷 미흡 |
| **Songscription / Klangio / Ivory / La Touche Musicale** | AI 오디오→악보/MIDI | 피아노 채보 정확도 높음, MusicXML/MIDI 내보내기, 피아노롤 | 채보 SaaS. 시각화 영상·릴스 없음. 유료·클라우드 |
| **ByteDance piano_transcription** (오픈소스) | 피아노 채보 모델 | onset/offset/velocity/**페달**까지 고해상도 채보, MAESTRO 학습, Apache 라이선스, CPU 동작 | 피아노 독주 전용(우리 조건과 일치), 설치·모델 관리 필요 |
| **Spotify basic-pitch** (오픈소스) | 범용 채보 | 경량·빠름, 다악기 | 피아노 폴리포니 정확도는 ByteDance 모델보다 낮음 → **폴백 엔진** |
| **CapCut / VLLO 등 릴스 편집앱** | 범용 영상 편집 | 자막·템플릿 | 낙하 노트·건반 연동 불가, 반복 작업 |

**기술 라이브러리 현황 (2026-08)**: OSMD(MusicXML 렌더, 편집기는 아님) · music21 · MuseScore 4 CLI · pianoplayer · Audiveris(OMR) · Tone.js + Salamander 샘플 · **piano_transcription_inference**(채보) · **basic-pitch**(폴백) · **ffmpeg**(인코딩·오디오 믹스) · **Playwright headless Chromium**(결정적 프레임 캡처) 또는 **Remotion**(React 기반 영상 렌더, 소규모 사업자 무료).

### 2.3 우리의 포지션 (차별점 9가지)
1. **학생 프로필 기반 제약 강제** — 손 스팬·음역·템포·조성 난이도를 생성 전·후 검증기로 0% 위반.
2. **자기 코퍼스 축적(RAG)** — 올린 콩쿨 명곡·교재를 스타일 프로필로 저장, 요청마다 검색해 조건 주입.
3. **한국 콩쿨 부문 기준 내장** — 부문별 제한 시간·난이도·심사 포인트.
4. **악보 + 소리 + 해설이 한 화면**, 해설 클릭 → 마디 점프.
5. **음악적 편집** — 드래그 구간 선택 → 삭제/이조/AI 구간 재생성.
6. **표절 방지·저작권 안전** — n-gram 유사도 검사, 저작권곡 재생산 금지 정책 코드화.
7. **출력 완결성** — 표지 PDF, 운지, 연습 템포 MP3, 손 분리 MP3.
8. **오디오만 있어도 낙하 노트 영상** — 스마트폰으로 찍은 학생 연주 영상/음원 → AI 채보 → Synthesia 스타일 영상. 경쟁 시각화 툴은 전부 MIDI를 요구한다.
9. **학원용 릴스 자동 생성** — 학생명·학년·콩쿨 성적 자막, 학원 로고·컬러 브랜드 킷, 하이라이트 구간 자동 추천, 9:16 세로 템플릿, 원클릭 MP4. 생성곡 홍보 릴스("이 곡은 AI와 원장이 OO학생을 위해 만든 곡")도 같은 파이프라인.

---

## 3. 사용자와 핵심 시나리오

### 3.1 사용자
- **원장(주 사용자)**: 음악 전공자, 마우스 중심 조작 선호.
- **강사**: 곡 배정·연습 지도, 학생 연주 촬영·릴스 제작.
- (v2) **학생/학부모**: 연습용 링크·본인 릴스 열람.

### 3.2 시나리오 A — 콩쿨곡 생성 (E2E)
1. `참고 악보 라이브러리`에 부르크뮐러 25, 클레멘티 소나티네, 콩쿨 지정곡 MusicXML/PDF 업로드 → 스타일 프로필 생성.
2. `학생 프로필`: "김OO, 초3, 손 스팬 7도, 빠른 곡 강점, 서정 약점, 2026 OO콩쿨 초등 저학년부(2분 30초)".
3. `생성 요청`: "밝고 활기찬 알레그로, '아라베스크' 느낌 참고, 중간 서정적 대비, 마지막 화려하게. A장조 또는 D장조."
4. 90초 내 악보 생성 → 좌 악보, 우 해설, 하단 재생.
5. 17~20마디 드래그 선택 → "왼손 더 쉽게" → 구간 재생성 → 채택. 24마디 한 음 삭제·이조 → 저장.
6. `내보내기`: PDF, MP3(원/연습 템포), MusicXML, 해설 PDF.
7. **`릴스 만들기`** 버튼 → 생성곡 MIDI로 낙하 노트 영상 + "OO학생을 위한 콩쿨 신곡" 템플릿 → MP4.

### 3.3 시나리오 B — 학생 연주 영상 → 릴스 (E2E)
1. 강사가 스마트폰으로 찍은 학생 연주 mp4(2분 30초) 업로드, 학생 선택, (있으면) 연주한 곡의 악보/생성곡 연결.
2. 시스템: 오디오 추출 → 피아노 채보(MIDI, 페달 포함) → (곡이 연결돼 있으면) 악보 MIDI와 정렬해 오검출 보정 → 템포·박자 추정.
3. `릴스 스튜디오` 열림: 위 프리뷰(30fps), 아래 타임라인. **하이라이트 자동 추천 3구간**(음 밀도·다이내믹·클라이맥스 위치 기반, 각 20~45초) 표시.
4. 템플릿 선택: `클래식 블랙`(낙하 노트 + 건반만) / `연주 영상 오버레이`(원본 영상 위 반투명 건반·노트) / `분할`(위 영상, 아래 낙하 노트) / `악보 동기`(악보 커서 + 건반).
5. 자막 자동 채움: "김OO · 초3 · 2026 OO콩쿨 대상 🏆", 곡명, 학원 로고(브랜드 킷). 훅 텍스트(첫 2초) 편집.
6. `렌더` → 1080×1920 30fps MP4 + 커버 이미지 + 캡션 텍스트(해시태그 포함) → 릴스 업로더 출력 폴더로 복사(웹훅).

### 3.4 시나리오 C — 오디오에서 악보 초안
- 시나리오 B의 채보 MIDI → 양자화 → MusicXML 초안(`needs_review`) → 작곡 축 에디터에서 검수 → 코퍼스 등록 또는 학생용 악보로 사용.

---

## 4. 시스템 아키텍처

```
┌────────────────────── Browser (Next.js 15 / React / TypeScript) ──────────────────────┐
│ Library │ Students │ Request Form │ ScoreEditor(OSMD+EditLayer) │ Player(Tone.js)        │
│ Guide   │ Transcribe UI │ ReelStudio(Visualizer Canvas/WebGL + Timeline + Caption)       │
└──────────────┬────────────────────────────────────────────────────────────────────────┘
               │ REST(JSON) + SSE(진행률)
┌──────────────▼──────────────── API Server (Python 3.12 / FastAPI) ─────────────────────┐
│ ingest/ analysis/(music21) generation/(Claude) validate/ edit/ export/ fingering/ guide/ │
│ transcription/(piano_transcription, basic-pitch, alignment, quantize)                   │
│ reels/(highlight, template, caption LLM, render orchestration)                          │
│ Worker: Celery + Redis  (OMR, 생성, 채보, MP3, 영상 렌더)                                │
└──────────────┬────────────────────────────────────────────────────────────────────────┘
               │
┌──────────────▼───────────┐ ┌──────────────────────────┐ ┌────────────────────────────┐
│ PostgreSQL 16 + pgvector  │ │ Object storage(/data, S3) │ │ 외부: Anthropic API         │
│                          │ │ 원본·MIDI·MP4·프레임      │ │ (선택) GPU 채보/NotaGen 서버 │
└──────────────────────────┘ └──────────────────────────┘ └────────────────────────────┘
┌─────────────── Render Worker (Node) ────────────────┐
│ Playwright headless Chromium → lib/visualizer 결정적 │
│ 렌더(render(t)) → PNG 프레임 파이프 → ffmpeg(mp4+오디오) │
└─────────────────────────────────────────────────────┘
```

**배포**: `docker-compose up` (web, api, worker-py, worker-render, db, redis). 학원 PC 또는 소형 VM. GPU는 선택(없으면 CPU 채보: 2분 30초 곡 ≈ 2~4분).

**핵심 원칙**
- **Single Source of Truth**: 작곡 축은 MusicXML(버전 관리), 시각화 축은 **NoteEvents JSON**(`{onset, offset, pitch, velocity, hand?, pedal[]}`; MIDI/MusicXML/채보 결과를 모두 이 형식으로 정규화).
- **AI는 구조화 JSON만 출력**, MusicXML 변환은 music21이 결정적으로.
- **시각화 렌더러는 결정적 함수 `render(state, t)`** — 브라우저 프리뷰(rAF)와 서버 렌더(고정 dt 프레임 캡처)가 **같은 코드**를 쓴다. 프리뷰와 결과물이 다르면 버그.
- 모든 생성물은 검증기를 통과해야 저장.

---

## 5. 기술 스택 (확정)

| 영역 | 선택 | 이유 |
|---|---|---|
| 프론트 | Next.js 15, TypeScript, Tailwind, Zustand | |
| 악보 렌더 | opensheetmusicdisplay 1.9.x | MusicXML 네이티브, BSD, GraphicalNote↔SourceNote 매핑 |
| 재생 | Tone.js Sampler + Salamander Grand Piano 샘플(CC-BY) | |
| 시각화 렌더 | **Canvas 2D**(기본) — 노트 3천 개/화면까지 60fps 충분. 파티클·글로우 효과는 오프스크린 캔버스 캐시. WebGL(PixiJS)은 v2 옵션 | 서버 헤드리스 캡처와 동일 코드 보장이 쉬움 |
| 영상 렌더 | **Playwright(Chromium headless)** 고정 dt 캡처 → **ffmpeg** (libx264, yuv420p, AAC) | 의존성 최소. Remotion은 대안으로 명시(§13) |
| 백엔드 | FastAPI, Pydantic v2, SQLAlchemy 2, Alembic | |
| 음악 처리 | music21 ≥ 9, pianoplayer, mido, pretty_midi, librosa | |
| **채보** | **piano_transcription_inference**(ByteDance, PyTorch, onset/offset/velocity/pedal) 기본 · **basic-pitch** 폴백(경량) | 피아노 독주 정확도 최고 수준, CPU 가능 |
| 오디오 전처리 | ffmpeg(영상→wav 16k mono), noisereduce(선택), pyloudnorm(라우드니스 정규화) | 스마트폰 녹음 대응 |
| 정렬 | 자체 DTW(chroma/onset 기반, librosa) — 악보 MIDI ↔ 채보 MIDI | 오검출 보정·연습 피드백(v2) |
| 변환 | MuseScore 4 CLI, ffmpeg, FluidSynth(폴백) | |
| OMR | Audiveris 5.x | |
| DB/큐 | PostgreSQL 16 + pgvector, Celery + Redis | |
| LLM | Anthropic Claude API — `COMPOSER_MODEL`(최상위 모델) / `WRITER_MODEL`(중간 모델), env로 관리(§7.2), Structured Outputs | 모티브·Plan·Realize·비평·모의 심사 / 해설·캡션·프로그램 노트 |
| 테스트 | pytest, vitest, Playwright E2E, 렌더 스냅샷 테스트(프레임 PNG 픽셀 diff) | |

---

## 6. 기능 명세

### 6.1 참고 악보 라이브러리 (Corpus)
입력: `.musicxml/.xml/.mxl`, `.mid`, `.pdf/.png/.jpg`(OMR), `.mscz`, **(v2) 채보 결과 MusicXML 초안**.
메타: 제목, 작곡가, 시대, 출처, **저작권 상태**(`public_domain/copyrighted/own`), 부문 태그, 자체 난이도(1~10).
파이프라인: 정규화 → music21 StyleProfile(§7.1) → 임베딩·특징 벡터(pgvector) → 멜로디 n-gram 인덱스.
저작권 정책(코드 강제): `copyrighted` 곡은 통계·특징만 저장, 음표열은 프롬프트에 절대 미포함. 생성물은 코퍼스 n-gram(8마디) 일치 0건이어야 저장.

### 6.2 학생 프로필
```
Student { id, name, birth_year, grade, years_of_study, hand_span{max_interval},
  level 1..10, repertoire_done[], strengths[], weaknesses[], tempo_comfort_max_bpm,
  reading_level, notes,
  media_consent: {reels_public: bool, show_full_name: bool}   // v2: 릴스 공개 동의
}
```
→ 하드 제약(스팬·음역·템포) + 소프트 선호. `media_consent`가 false면 릴스 렌더 시 이름 자동 마스킹("김O○") 및 공개 템플릿 사용 불가.

### 6.3 생성 요청 (Composition Request)
학생, 부문·제한 시간, 목표 난이도, 분위기, 형식(AB/ABA/론도/소나티네풍/변주곡), 조성·박자·템포·마디 수(자동 계산), 참고 스타일(선택 또는 자동 검색), 텍스처 옵션(왼손 반주 유형 등), 필수 요소 자유 텍스트, 생성 개수 1~3.
출력: Composition 1~3개, 각 MusicXML v1 + 검증 리포트 + 해설 + 운지본 + 미리듣기 MIDI.

### 6.4 악보 뷰어·에디터
레이아웃: 좌 70% 악보(OSMD), 우 30% 탭(해설·검증·버전·수정 채팅), 하단 재생 컨트롤(템포 40~120%, 루프, 메트로놈, 손 분리). 우측 상단 **`릴스 만들기`** 버튼(현재 버전 MIDI로 §6.12 진입).

렌더/매핑: MusicXML `<note id>` ↔ OSMD GraphicalNote 매핑 테이블.
선택: 클릭 / Shift+클릭 / **드래그 러버밴드**(SVG 오버레이, bbox 교차) / 마디 번호 클릭. 정규화 `{noteIds[], measureRange, staff}`.

편집(로컬 즉시): 삭제(→쉼표, 마디 길이 보존), 이조(↑↓ 반음, Shift 옥타브, 드래그), 길이(숫자키), 삽입(쉼표 클릭→음), 다이내믹/아티큘레이션 팔레트, 마디 삽입/삭제/복제, Undo/Redo(Command 패턴). 편집 → ScoreModel → MusicXML 재직렬화 → OSMD 재렌더 → 매핑 재구축.

AI 구간 수정(서버): 선택 구간 + 자연어/프리셋(`더 쉽게·더 어렵게·왼손 반주 교체·리듬 변형·반복 제거·마무리 강화`) → 앞뒤 4마디 문맥으로 구간만 재생성 → 검증 → 새 버전, A/B 미리듣기.

### 6.5 재생 엔진
Tone.js Sampler(3 velocity 레이어, ≤5MB 초기 로드). ScoreModel → NoteEvents(다이내믹→velocity, 스타카토, 페달 sustain, rit. 템포 커브). OSMD 커서 동기, 루프, 손 분리, 카운트인. MP3는 서버(MuseScore CLI → ffmpeg, FluidSynth 폴백), 연습 70% 템포 동시 생성.

### 6.6 연주법 해설
Claude → 마디 앵커 JSON(`overview, sections[], fingering_notes[], practice_plan[4주], competition_tips[], memorization_map`). 카드 클릭 → 마디 하이라이트·커서 이동. 해설 PDF.

### 6.7 운지
pianoplayer 자동 운지(손 크기 파라미터) → `<fingering>`. 표시 토글, 개별 수정.

### 6.8 내보내기 (작곡 축)
MusicXML/MXL, PDF(표지: 곡명·학생명·학원 로고·크레딧), MIDI, MP3(원/연습/RH/LH), 해설 PDF, ZIP. 파일명 `{학생명}_{곡명}_{부문}_{v버전}_{YYYYMMDD}.ext`.

### 6.9 버전·이력
Composition → ScoreVersion[] (생성/편집/구간재생성마다 +1, diff 요약). 열기·복원·비교 재생.

---

### 6.10 오디오 → MIDI 채보 (Transcription) — v2 신규

**입력**: `.mp3/.wav/.m4a/.aac`, `.mp4/.mov`(영상은 ffmpeg로 오디오 추출, 영상 트랙은 릴스 오버레이용으로 보관). 최대 10분. 학생 선택(선택), 연결 곡(선택: Composition 버전 또는 코퍼스 곡).

**파이프라인** (Celery, 상태 `queued → preprocessing → transcribing → aligning → quantizing → ready | failed`):
1. **전처리**: ffmpeg → 16kHz mono wav(모델 요구 샘플레이트로 리샘플), pyloudnorm −23 LUFS 정규화, 앞뒤 무음 트림(threshold −45dB), 선택적 noisereduce(스마트폰 녹음 잡음). 원본 오디오는 릴스 사운드트랙용으로 별도 보관(정규화만 적용).
2. **채보**: `piano_transcription_inference`(device=cuda|cpu 자동) → `notes[{onset, offset, pitch, velocity}]`, `pedal[{onset, offset}]`. 실패/타임아웃(길이×3배) 시 basic-pitch 폴백(페달 없음, `engine='basic-pitch'` 표시).
3. **후처리**: 30ms 미만 노트 제거, 겹치는 동일 pitch 병합, velocity 스케일 정규화(학생 녹음 레벨 편차 보정), 손 분리 휴리스틱(피치 클러스터 + 시간 근접, 중앙 C 기준 동적 경계) → `hand: 'L'|'R'`.
4. **정렬(연결 곡이 있을 때)**: 악보 MIDI ↔ 채보 MIDI DTW(chroma 12차원 + onset envelope). 결과: 각 악보 노트에 대한 `matched/missed/extra`, 시간 워프 맵. 채보 노트의 pitch 오검출을 악보 기준으로 보정(±1 반음 & 시간 60ms 이내 → 악보 pitch 채택, 로그 남김). **연습 피드백**(정확도 %, 놓친 음 마디 목록)은 v2 화면에 노출, v1은 JSON만 저장.
5. **템포·박자 추정**(연결 곡 없을 때): librosa beat track → BPM, 박자는 onset 강세 패턴으로 2/4·3/4·4/4·6/8 후보 점수 → 원장 확인 UI에서 확정.
6. **양자화 → MusicXML 초안**: 16분음표 그리드(셋잇단 감지 시 12분할), 손 분리 결과로 2단 보표, music21로 MusicXML(`needs_review`). 연결 곡이 있으면 이 단계는 생략(악보는 이미 있음).

**출력**: `Transcription { note_events.json, midi_path, pedal, tempo_map, hand_split, alignment?, musicxml_draft?, engine, confidence_stats }`.

**UI (`/transcribe`)**: 업로드·진행률 → 결과 화면: 위 파형 + 피아노롤(채보 노트, 신뢰도 낮은 노트 주황색), 아래 재생(원본 오디오 / 채보 MIDI 합성 / 둘 다 겹쳐서). 노트 클릭 삭제·피치 드래그·onset 드래그 최소 편집(피아노롤 편집은 악보 편집보다 단순하므로 v1 포함). `릴스 만들기` / `악보 초안 열기` / `코퍼스에 등록` 버튼.

### 6.11 연주 시각화 렌더러 (Synthesia 스타일) — v2 신규

**입력**: NoteEvents JSON(생성곡 MusicXML→MIDI, 업로드 MIDI, 채보 결과 중 하나) + 오디오 트랙(합성 MP3 또는 원본 녹음) + VisualConfig.

**VisualConfig (템플릿이 기본값 제공, 사용자 오버라이드)**
```
{
  canvas: {w:1080, h:1920, fps:30},            // 9:16 기본, 16:9·1:1 프리셋
  keyboard: {range:[21,108] | 'auto-fit', height_ratio:0.18, style:'realistic'|'flat', show_labels:false},
  notes: {lead_time_sec:2.5, color_rh:'#F5C542', color_lh:'#3FA7F5', by:'hand'|'pitch_class'|'single',
          shape:'rounded', min_height_px:6, glow:true, hit_flash:true, particles:'light'|'none'|'rich'},
  pedal: {show_bar:true},
  background: {type:'solid'|'gradient'|'image'|'video', value, blur:0..20, darken:0..1},
  overlay: {logo:{asset_id, pos:'top-right', size:0.12}, watermark_opacity:0.6},
  captions: [ {t_start, t_end, text, style:'hook'|'title'|'subtitle'|'lower-third', anim:'fade'|'pop'} ],
  score_sync: {enabled:false, musicxml_version_id}   // '악보 동기' 템플릿용: 상단 OSMD 커서
}
```

**렌더러 설계 (`web/lib/visualizer/`)**
- `buildTimeline(noteEvents, config)` → 사전 계산된 노트 사각형 배열(픽셀 x, 폭, 시작/끝 시각), 페달 구간, 키보드 지오메트리(흰건반/검은건반 x·폭, 'auto-fit'은 사용된 최저~최고음 ±2 반음 옥타브 정렬).
- `render(ctx, timeline, config, t)` — **순수 함수**. t초 시점 프레임을 그린다: 배경 → 낙하 노트(y = keyboardTop − (onset − t)/lead_time × fallArea, 건반에 닿으면 히트 플래시·건반 눌림 색) → 건반 → 페달 바 → 자막(애니메이션은 t 기반 보간) → 로고. 난수 사용 금지(파티클은 노트 id 기반 시드).
- 프리뷰: `requestAnimationFrame`, 오디오 `currentTime`을 t로 사용(오디오가 마스터 클록). 30fps 미만이면 particles 자동 'none'.
- 서버 렌더(`render-worker/`): Playwright headless Chromium이 같은 번들을 로드 → `for frame in 0..N: render(t=frame/fps); canvas.toBlob(png)` → stdout 파이프 → `ffmpeg -f image2pipe -framerate 30 -i - -i audio.wav -c:v libx264 -pix_fmt yuv420p -crf 18 -c:a aac -shortest out.mp4`. 60초·30fps·1080×1920 기준 목표 ≤ 90초(CPU 4코어).
- 스냅샷 테스트: 고정 입력에 대해 t=0, 5, 10초 프레임 PNG를 골든과 픽셀 diff ≤ 0.5%.

**'연주 영상 오버레이' 템플릿**: 원본 mp4를 배경(`background.type='video'`)으로, 채보 정렬된 노트를 위에 그림. 오디오는 원본. 영상 프레임은 ffmpeg로 fps 맞춰 PNG 추출 후 Chromium `<video>` 대신 `<img>` 시퀀스로 t 정합(결정성 보장).

**'악보 동기' 템플릿**: 상단 40%에 OSMD 렌더(작은 스케일) + 커서, 하단 60% 낙하 노트+건반. 커서 위치는 MusicXML 노트 id ↔ NoteEvents 매핑으로 t마다 계산.

### 6.12 릴스 메이커 (ReelStudio) — v2 신규

**입력 소스** (셋 중 하나): ① Composition 버전(생성곡) ② Transcription(학생 연주) ③ 업로드 MIDI(+오디오).

**릴스 프로젝트**
```
ReelProject { id, source:{type, ref_id}, student_id?, template_id, visual_config, 
  clip:{t_start, t_end}, captions[], brand_kit_id, aspect:'9:16'|'1:1'|'16:9',
  caption_text (SNS 본문), hashtags[], status, renders[] }
```

**하이라이트 자동 추천** (`reels/highlight.py`): 곡 전체를 5초 윈도우로 스캔해 점수 = 0.4·음밀도 + 0.3·velocity 평균 + 0.2·음역 폭 + 0.1·클라이맥스 근접(형식 분석의 클라이맥스 마디 또는 velocity 피크). 프레이즈 경계(악보가 있으면 마디/섹션 경계, 없으면 onset 공백 ≥ 0.6s)에 스냅해 20·30·45초 후보 각 1개 + "처음 30초" + "마지막 30초" 제시. 사용자가 타임라인 핸들로 조정.

**템플릿 (v1 5종, `reels/templates/*.json`)**: `클래식 블랙`, `학원 브랜드`(브랜드 컬러 그라데이션 + 로고), `연주 영상 오버레이`, `분할(영상/노트)`, `악보 동기`. 각 템플릿 = VisualConfig 기본값 + 자막 슬롯 정의(hook 0~2초, title 2~5초, lower-third 전체, outro 마지막 3초 "OO음악학원 · 상담 문의").

**자막 자동 채움**: 학생명(동의 설정에 따라 마스킹)·학년·곡명·작곡가(생성곡은 "AI × OOO 원장 작곡")·콩쿨명·성적(입력 시). **훅 문구·SNS 캡션·해시태그는 Claude가 3안 생성**(프롬프트 `reels/prompts/caption.md`: 학원 톤, 30자 이내 훅, 이모지 1개 이내, 해시태그 8~12개 한국어+영어 혼합). 원장이 선택·수정.

**브랜드 킷**: 로고(PNG/SVG), 메인·보조 컬러, 폰트(내장 한국어 폰트 2종: Pretendard, Noto Serif KR), 학원명, 아웃트로 문구. 하나 이상 저장, 기본 지정.

**오디오**: 소스 오디오(합성/원본) + 선택 BGM 없음(v1은 연주 소리만; 저작권 리스크 회피). 페이드 인/아웃 0.5s, −14 LUFS 정규화(플랫폼 권장), 클립 경계에서 페달 잔향 0.8s 포함.

**렌더 출력**: `mp4`(H.264, 1080×1920 30fps, ≤ 60MB), 커버 `jpg`(hook 프레임), `caption.txt`(본문+해시태그), `meta.json`. 파일명 `{학생명 or 곡명}_{템플릿}_{YYYYMMDD}_{n}.mp4`.

**릴스 업로더 연동**: 완료 시 `REELS_OUTPUT_DIR`(env)에 mp4+caption.txt 복사, `REELS_WEBHOOK_URL`(env, 선택)로 POST `{path, caption, hashtags, student_id}`. 업로드 자체는 이 시스템 범위 밖.

**UI (`/reels`, `/reels/[id]`)**: 좌 프리뷰(폰 프레임 목업, 재생/일시정지/스크럽), 우 패널 탭(템플릿 · 클립&하이라이트 · 자막 · 브랜드 · 내보내기). 하단 타임라인(파형 + 노트 밀도 히트맵 + 하이라이트 후보 + 자막 블록 드래그). 렌더 큐 상태와 완료 목록.

### 6.13 콩쿨 모드 (Competition Mode) — v3 신규

**콩쿨 프로필** (`competition_profiles`): 대회명·주최·연도·부문·제한 시간(초)·**창작곡/자유곡 허용 여부**·악보 제출 규정(인쇄본 부수, 표지 규정, 작곡가 표기)·암보 필수 여부·반복 연주 허용·심사 기준 텍스트(요강 붙여넣기)·심사 성향 메모(원장 경험: "이 대회는 화려한 곡 선호", "테크닉보다 음악성"). 생성 요청에서 콩쿨 프로필을 선택하면 하드 제약과 Plan 프롬프트에 자동 반영. `original_allowed=false`면 생성 차단·경고.

**쇼케이스 설계**: Plan 단계에서 학생 `strengths`를 반드시 드러내는 구간(예: 빠른 스케일 패시지, 표현력 있는 칸타빌레)을 `showcase_measures`로 지정하고, `weaknesses`는 노출을 최소화(예: 옥타브 약하면 옥타브 금지). 첫 8마디 "심사위원 첫인상 규칙"(명확한 모티브·확실한 조성·다이내믹 대비)과 마지막 4마디 "마무리 규칙"(리듬적 확신·종지 명확)을 검증기 소프트 규칙으로 추가.

**모의 심사** (`judge/`): 서로 다른 성향의 심사위원 페르소나 3명(테크닉 중시·음악성 중시·구조/형식 중시)이 각각 루브릭(정확성·표현·구조·난이도 적절성·인상)으로 10점 척도 채점 + 코멘트 + "곡에서 고칠 점" / "연습에서 보완할 점"을 분리해 제시. 입력은 MusicXML 분석 결과와 악보의 텍스트 표현. 결과는 해설 패널 옆 "심사" 탭에 표시. (학생 연주 채보가 있으면 v2에서 연주 정확도까지 포함해 채점.)

**결과 기록·학습** (`competition_results`): 대회 후 결과(대상/최우수/우수/장려/미입상)·심사평 입력 → 곡의 StyleProfile·난이도·쇼케이스 유형과 결과의 상관을 대시보드로 표시, 상위 결과 곡의 Plan 특성을 이후 Plan 프롬프트의 "학원 실전 데이터" 섹션에 자동 요약 주입.

### 6.14 연주회 프로그램 빌더 (Recital Builder) — v3 신규

**입력**: 연주회명·날짜·총 러닝타임 목표·참가 학생 목록(각 학생에 기존 곡 배정 또는 "새 곡 생성" 체크)·순서 규칙(학년 오름차순 / 난이도 오름차순 / 분위기 교차).
**동작**: 학생별 생성 요청을 일괄 실행(큐), 프로그램 전체의 **대비 검사**(연속 곡의 조성·템포·분위기 중복 경고), 총 러닝타임 계산(곡 + 등퇴장 45초), 순서 자동 제안 + 드래그 조정.
**출력**: 프로그램북 PDF(표지·순서·학생명·곡명·곡 해설 3줄(Claude 생성)·학원 브랜드), 학생별 악보·MP3 ZIP, 전체 곡 릴스 티저(§6.12 "학원 브랜드" 템플릿으로 각 30초 일괄 렌더).

---

## 7. AI 작곡 파이프라인 (작곡 축) — v3 전면 개정: "공동 작곡" 워크플로

### 7.1 StyleProfile
`key, mode, meter, tempo, measures, duration_est, form[], harmonic_rhythm, chord_progression_roman[], modulations[], rh{range, max_interval, density, scale_run_ratio, ornaments}, lh{texture, range, max_span}, rhythm_vocab, motif{head_intervals, head_rhythm}, dynamics_range, articulation, difficulty_score, difficulty_features`.
(채보 결과와 생성물에도 동일 분석을 적용 — 하이라이트 추천·코퍼스 등록·음악성 지표(§7.4)에서 재사용.)

### 7.2 모델 배정 (env로 교체 가능, 시작 시 docs.claude.com 모델 페이지에서 최신 문자열 확인)
| 단계 | 모델 | 이유 |
|---|---|---|
| 모티브 생성·Plan·Realize·비평·모의 심사 | `COMPOSER_MODEL` = 최상위 모델(예: `claude-opus-5`) | 음악적 판단이 필요한 곳. 비용보다 품질 |
| 해설·제목·릴스 캡션·프로그램 노트 | `WRITER_MODEL` = 중간 모델(예: `claude-sonnet-5`) | 텍스트 품질 충분, 저비용 |
| 스키마 보정·재시도 | 위와 동일, temperature 낮춤 | |
모든 호출은 Structured Outputs(JSON Schema)로 강제. 요청당 비용 상한 `MAX_COST_PER_COMPOSITION`(env) 초과 시 중단·알림.

### 7.3 작곡 단계 (사람이 개입하는 지점을 ★로 표시)

**Stage 0 — 스타일 컨텍스트 조립** (코드)
학생 제약(하드) + 선호(소프트) + 콩쿨 프로필 + 검색된 참고 StyleProfile 3~5개 + 학원 실전 데이터 요약 + (public_domain/own 곡의 8마디 이하 발췌 최대 3개) → `ComposerContext`. 저작권곡 음표열 제외 규칙은 코드로 강제.

**Stage 1 — 모티브 후보 생성 ★**
`MotifCandidate{ id, measures(2~4), rh_events, lh_events(단순 반주), key, meter, tempo, character_label, why_it_works }` × 3~5개. 각 후보는 즉시 음원 합성(Tone.js 미리듣기) + 4마디 미니 악보. 원장이 하나를 고르거나 "이 느낌으로 3개 더", 또는 **직접 입력**(피아노롤 4마디 그리기 / 흥얼거림 녹음 → §6.10 채보 → 모티브)한다. 선택된 모티브는 `motif_locked=true`로 이후 모든 단계의 불변 입력.

**Stage 2 — Plan (설계) ★**
입력: ComposerContext + 잠긴 모티브. 출력 `CompositionPlan`:
```
{ title_candidates[], key, meter, tempo, total_measures, duration_est,
  form: [{label:"A", measures:[1,8], phrases:[{measures:[1,4], motif_treatment:"statement", texture_rh, texture_lh, dynamic},
                                                {measures:[5,8], motif_treatment:"sequence_up_2nd", ...}]}, ...],
  harmony: [{measure, roman, bass_note?}],          // 마디별
  climax: {measure, how:"highest_register + ff + fuller_texture"},
  showcase_measures: [{range, strength_used}],
  contrast_section: {label:"B", how:"minor_relative + legato_cantabile"},
  modulations[], ending:{type:"perfect_cadence_with_flourish", measures:[29,32]},
  dynamics_curve: [{measure, dyn}], pedal_plan, difficulty_target }
```
`motif_treatment` 열거형: `statement, repeat, sequence_up_2nd, sequence_down_3rd, inversion, retrograde, augmentation, diminution, fragment_head, fragment_tail, transpose_to_dominant, mode_change, texture_swap(LH melody), octave_shift, rhythmic_variation`.
Plan은 원장에게 **형식 다이어그램 + 마디별 화성 + 모티브 처리 표**로 보이고, 원장이 승인/수정(예: "B 부분을 8마디로 늘리고 조바꿈은 빼")한다. 기본 설정은 자동 승인(원장이 끌 수 있음).
규칙 검사: 제한 시간, 종지, 대비 존재, showcase가 학생 강점과 일치, 클라이맥스 위치가 60~80% 지점.

**Stage 3 — Realize (프레이즈 단위 실현)**
섹션이 아니라 **프레이즈(4마디) 단위**로 순차 생성. 각 호출 입력: 잠긴 모티브, 해당 프레이즈 plan(처리 기법·화성·텍스처·다이내믹), 직전 8마디 실제 음표, 다음 프레이즈의 첫 화성(연결용). 출력 `PhraseRealization{measures[{number, rh[{voice, events[{dur, pitches[], tie, artic, slur}]}], lh[...], dynamics, text, pedal}]}`. 순차 생성이므로 병렬보다 느리지만(32마디 ≈ 8호출) 연결성이 훨씬 좋다. 병렬은 섹션 경계에서만 허용.
프레이즈마다 즉시 검증(§7.6 하드 규칙) → 실패 시 재시도 2회 → 그래도 실패면 사유와 함께 원장에게 표시.

**Stage 4 — Assemble** (music21, 결정적) → MusicXML 3.1(모든 `<note id>`) → 임시 버전.

**Stage 5 — 자동 음악성 채점 + 비평 루프**
(a) 규칙 기반 음악성 지표(§7.4) 계산.
(b) **비평가 호출**: 악보를 텍스트 표현(마디별 음표·화성·다이내믹)으로 변환해 `critic.md` 프롬프트로 루브릭 채점(§7.5) + `revision_requests[{measures, issue, instruction}]`.
(c) 종합 점수 < 문턱(기본 7.0/10)이면 `revision_requests`를 Stage 3의 구간 재생성으로 실행(해당 프레이즈만) → 재채점. 최대 2회. 비평가와 작곡가는 **서로 다른 프롬프트·별도 호출**(자기 채점 편향 방지).
(d) 표절 n-gram 검사, 최종 검증 → 저장. 채점 결과와 비평 코멘트는 "품질 리포트" 탭에 표시.

**Stage 6 — 후처리**: 운지(pianoplayer), 해설(Guide), 제목 확정, 미리듣기 MP3, (콩쿨 모드) 모의 심사.

**Stage 7 — 원장 편곡 ★**: 에디터에서 구간 재생성·직접 편집. 3안 생성 시 A/B/C 비교 청취. 👍/👎 + 사유 저장.

### 7.4 규칙 기반 음악성 지표 (analysis/musicality.py, 0~1 정규화)
| 지표 | 계산 | 목표 |
|---|---|---|
| 모티브 일관성 | 잠긴 모티브 head(음정열·리듬)의 변형 포함 등장률(전위·이조·리듬변형 허용 매칭) | 프레이즈의 ≥ 70%에 등장 |
| 반복/변화 균형 | 마디 단위 자기 유사도 행렬에서 정확 반복 비율 vs 변형 비율 | 정확 반복 20~45% |
| 선율 윤곽 | 상행/하행/도약 비율, 최고음이 클라이맥스 마디 ±2 안에 있는지 | 도약(≥4도) 15~35% |
| 화성 리듬 일관성 | Plan 화성과 실제 음표의 일치율(음표의 코드톤 비율) | ≥ 85% |
| 프레이즈 균형 | 4/8마디 단위 프레이즈 끝에 긴 음 또는 쉼표(호흡) 존재 | ≥ 80% |
| 다이내믹 곡선 | Plan 곡선과 실제 표기 상관 | ≥ 0.7 |
| 텍스처 대비 | 섹션 간 LH 텍스처·음역 변화 존재 | B섹션에서 ≥ 1개 변화 |
| 연주 편의 | 손 이동 거리·연속 도약·스팬(난이도 검증기와 공유) | 학생 레벨 한도 |
가중합 `musicality_score`. 초기 가중치 하드코딩, M8에서 원장 평가 데이터로 보정.

### 7.5 비평가 루브릭 (prompts/critic.md, 각 10점)
1. 모티브의 기억성과 전개(단순 반복이 아닌 "발전"이 있는가)
2. 형식의 명료성(섹션 구분이 귀로 들리는가)
3. 화성 진행의 자연스러움과 종지의 확신
4. 성부 진행(병행 5·8도 남발, 어색한 도약, 왼손 반주와 멜로디 충돌)
5. 프레이즈 호흡과 균형
6. 클라이맥스의 설득력과 마무리
7. 난이도 적절성·학생 강점 노출("이 학생이 돋보이는가")
8. 콩쿨 효과(첫 8마디 인상, 청중 관점의 재미)
9. 기보 정합(연주자가 읽기 좋은가: 임시표·이명동음·성부 배치)
10. 독창성(참고 스타일을 닮되 특정 곡을 베낀 느낌이 없는가)
출력: 항목 점수, 총점, 강점 2개, `revision_requests[]`(마디 범위 + 구체적 지시. 예: "13~16 왼손 알베르티가 멜로디와 같은 음역에서 충돌 — 한 옥타브 아래로", "25~28 클라이맥스가 ff인데 텍스처가 얇음 — 오른손 옥타브 또는 3도 겹침").

### 7.6 검증기 (하드 규칙 — 실패 시 저장 불가)
마디 길이 합계 = 박자표 · 음역 · 손 스팬 ≤ 학생 스팬 · 손 교차 · 난이도 목표 ±1 · 연주시간 ≤ 제한×0.95 · 종지 · 임시표 비율 · 동일 마디 4회 연속 금지 · 표절 n-gram(8마디) 0건 · 콩쿨 프로필 규정(반복 금지 등) · music21 재파싱·OSMD 헤드리스 렌더 성공.
**소프트 규칙**(경고만): 첫 8마디 규칙, 마무리 규칙, 클라이맥스 위치, 병행 5·8도.

### 7.7 난이도 점수(1~10)
밀도·스팬·동시음·조표·임시표·템포·리듬 복잡도·왼손 텍스처·장식음·손 이동·다성부 가중합. 부문 매핑: 유치 1~2 · 초등저 2~4 · 초등고 4~6 · 중등 6~8. M8에서 원장 라벨로 회귀 보정.

### 7.8 RAG · 프롬프트 관리 · 엔진 B
- 검색: 요청 텍스트+레벨+부문 → pgvector 상위 10 → 난이도 ±2 필터 → 상위 5 StyleProfile. 원장 지정 곡 항상 포함. 저작권곡은 통계만.
- 프롬프트 파일: `generation/prompts/{motif,plan,realize_phrase,regenerate_region,critic,judge,guide,title}.md`, 버전 태그. 골든 요청 20건 회귀 테스트(`tests/golden/`): 각 요청에 대해 검증 통과율·musicality_score·비평 총점을 기록해 프롬프트 변경 시 회귀 비교(`make golden`).
- 엔진 B(`SymbolicEngine` Protocol): NotaGen 등 심볼릭 모델을 Stage 1 모티브 후보 다양성 보강용으로 우선 연결(전체 곡 생성보다 리스크가 낮음). M9.

### 7.9 "이상한 곡" 방지 요약 (개발자가 지켜야 할 것)
1. 모티브를 먼저 잠그고 모든 단계가 그것을 참조한다.
2. 마디 단위 자유 생성 금지 — 프레이즈 단위 + 모티브 처리 기법 명시.
3. 작곡가와 비평가는 별도 호출·별도 프롬프트.
4. 하드 규칙은 코드가, 음악성은 지표+비평가가, 최종 판단은 원장이.
5. 3안 생성 후 최고 점수안을 기본 표시, 나머지는 비교 청취.
6. 골든 세트 회귀 없이 프롬프트를 바꾸지 않는다.

---

## 8. 데이터 모델 (PostgreSQL)

```
students(..., media_consent jsonb)
corpus_scores(..., source_transcription_id?)            -- 채보에서 등록된 경우 링크
corpus_ngrams(...)
composition_requests / compositions / score_versions / guides / exports   -- v1 동일
jobs(id, kind, status, progress, payload, error, ...)

-- v2 신규
media_assets(id, kind enum(audio,video,image,logo,font), path, duration_sec, width, height, student_id?, created_at)
transcriptions(id, media_asset_id, student_id?, linked_version_id?, linked_corpus_id?, engine, status,
               note_events_path, midi_path, tempo_bpm, meter, hand_split_method,
               alignment jsonb?, musicxml_draft_path?, confidence_stats jsonb, created_at)
brand_kits(id, name, logo_asset_id, primary_color, secondary_color, font_heading, font_body, academy_name, outro_text, is_default)
reel_templates(id, name, base_config jsonb, caption_slots jsonb, is_builtin)
reel_projects(id, source_type enum(composition,transcription,midi), source_ref_id, student_id?, template_id, brand_kit_id,
              visual_config jsonb, clip jsonb, captions jsonb, caption_text, hashtags text[], status, created_at, updated_at)
reel_renders(id, project_id, mp4_path, cover_path, caption_txt_path, meta jsonb, render_seconds, delivered_to_uploader bool, created_at)

-- v3 신규
motif_candidates(id, request_id, idx, events jsonb, key, meter, tempo, character_label, rationale, source enum(ai,drawn,transcribed), selected bool, created_at)
composition_plans(id, composition_id, plan jsonb, approved_by_teacher bool, teacher_edits jsonb, created_at)
quality_reports(id, score_version_id, musicality jsonb, critic jsonb, revision_round int, passed bool, created_at)
competition_profiles(id, name, organizer, year, division, time_limit_sec, original_allowed bool, score_submission_rules text, memorization_required bool, repeats_allowed bool, criteria_text, judge_notes, created_at)
judge_reports(id, score_version_id, competition_profile_id?, panel jsonb, created_at)
competition_results(id, composition_id, student_id, competition_profile_id, result enum(grand,first,second,third,honorable,none), judge_comments, performed_version_id, created_at)
recital_programs(id, name, date, target_duration_sec, order_rule, brand_kit_id, status, created_at)
recital_items(id, program_id, position, student_id, composition_id?, generation_request_id?, program_note, duration_sec)
teacher_feedback(id, score_version_id, thumbs enum(up,down), reason_tags text[], comment, created_at)
```

---

## 9. API 명세 (요약)

```
-- v1 동일: /api/corpus, /api/students, /api/compositions, /api/versions, /api/exports, /api/jobs

POST   /api/media/upload                       multipart(audio|video|image) → media_asset
POST   /api/transcriptions                     {media_asset_id, student_id?, linked_version_id?} → job_id
GET    /api/transcriptions/{id}                결과 + note_events URL
PATCH  /api/transcriptions/{id}/notes          {ops:[delete|move|pitch]} 피아노롤 편집 저장
POST   /api/transcriptions/{id}/quantize       → musicxml_draft (job)
POST   /api/transcriptions/{id}/to-corpus      → corpus_score(needs_review)

CRUD   /api/brand-kits
GET    /api/reel-templates
POST   /api/reels                              {source_type, source_ref_id, template_id, student_id?} → project (하이라이트 후보 포함)
GET/PATCH /api/reels/{id}                      visual_config, clip, captions, hashtags 수정
POST   /api/reels/{id}/captions/suggest        → Claude 훅·캡션·해시태그 3안
POST   /api/reels/{id}/render                  → job_id (SSE 진행률: 프레임/총프레임)
GET    /api/reels/{id}/renders                 완료 목록 + 다운로드 URL
POST   /api/reels/{id}/renders/{rid}/deliver   → 업로더 출력 폴더/웹훅 전달

-- v3 신규 (작곡 공동 워크플로)
POST   /api/requests/{id}/motifs               → job: 모티브 후보 3~5개 (+ 미리듣기 MIDI)
POST   /api/requests/{id}/motifs/more          {feedback} → 추가 후보
POST   /api/requests/{id}/motifs/custom        {events | transcription_id} → 원장 입력 모티브
POST   /api/requests/{id}/motifs/{mid}/select
POST   /api/requests/{id}/plan                 → job: CompositionPlan
PATCH  /api/plans/{id}                         원장 수정 · POST /api/plans/{id}/approve
POST   /api/plans/{id}/realize                 → job: Realize→Assemble→채점→비평 루프→저장 (SSE: 프레이즈/라운드 진행)
GET    /api/versions/{id}/quality              musicality + critic 리포트
POST   /api/versions/{id}/judge                {competition_profile_id?} → 모의 심사 3인
POST   /api/versions/{id}/feedback             {thumbs, reason_tags, comment}
CRUD   /api/competition-profiles · POST /api/compositions/{id}/results
CRUD   /api/recitals · POST /api/recitals/{id}/generate-all · POST /api/recitals/{id}/program-book · POST /api/recitals/{id}/teasers
```

---

## 10. 저장소 구조

```
concours-composer/
├─ CLAUDE.md · SPEC.md · docker-compose.yml   # web, api, worker-py, worker-render, db, redis
├─ web/
│  ├─ app/(library|students|compose|compose/[id]/(motif|plan)|editor/[id]|exports|transcribe|reels|reels/[id]|competitions|recitals|recitals/[id])/
│  ├─ components/compose/  MotifPicker.tsx(4마디 미니악보+재생), PlanReview.tsx(형식 다이어그램·화성표), QualityReport.tsx, JudgePanel.tsx
│  ├─ components/score/   ScoreView, SelectionOverlay, EditToolbar, Player, GuidePanel
│  ├─ components/pianoroll/ PianoRoll.tsx, NoteEditOverlay.tsx
│  ├─ components/reels/   ReelPreview.tsx, Timeline.tsx, CaptionEditor.tsx, TemplatePicker.tsx, BrandKitForm.tsx
│  ├─ lib/score/          scoreModel, musicxmlParser, musicxmlSerializer, osmdMapping, commands/
│  ├─ lib/player/         scheduler, sampler, dynamics
│  ├─ lib/visualizer/     timeline.ts, render.ts(순수 함수), keyboard.ts, captions.ts, particles.ts, types.ts
│  └─ tests/ (vitest + 스냅샷 프레임)
├─ render-worker/         # Node: Playwright headless 캡처 → ffmpeg. lib/visualizer 번들 공유(monorepo workspace)
│  ├─ src/renderReel.ts, src/framePipe.ts, Dockerfile(chromium+ffmpeg)
├─ server/
│  ├─ app/ main.py, api/, models/, schemas/
│  ├─ app/ingest/ analysis/(+musicality.py) generation/(motif.py, plan.py, realize_phrase.py, critic.py, assemble.py, engines/, prompts/)
│  │        validate/ edit/ fingering/ guide/ export/ judge/(panel.py, prompts/judge.md) recital/(program.py, book.py)
│  ├─ app/transcription/  preprocess.py, engines/(bytedance.py, basicpitch.py), postprocess.py, hand_split.py,
│  │                       align.py(DTW), tempo.py, quantize.py
│  ├─ app/reels/          highlight.py, templates/*.json, captions.py, project.py, deliver.py, prompts/caption.md
│  ├─ worker/ celery_app.py, tasks.py (render 태스크는 render-worker에 HTTP로 위임)
│  ├─ tests/ (unit, golden/, transcription fixtures: 30초 샘플 wav 5개 + 정답 MIDI)
│  └─ Dockerfile          # python + torch(cpu) + musescore4 + audiveris + ffmpeg + fluidsynth
├─ assets/ soundfont/ samples/salamander/ fonts/(Pretendard, NotoSerifKR) cover_template.html brand_default/
└─ scripts/ seed_corpus.py, download_models.py(채보 체크포인트 zenodo), bench_transcription.py
```

---

## 11. 마일스톤과 완료 기준

### M0 — 골격 (1주)
docker-compose 6개 서비스 기동, `make check-tools`: mscore / audiveris / ffmpeg / music21 / **torch + 채보 체크포인트 다운로드** / **playwright chromium** 검증. 프론트 빈 페이지.

### M1 — 뷰어 + 재생 (2주)
MusicXML 업로드 → OSMD → Tone.js 재생, 커서 동기, 템포, 손 분리, 루프.
Acceptance: 부르크뮐러 25곡 렌더·재생 오류 0, 첫 소리 500ms, 다이내믹·스타카토·페달 반영.

### M2 — 코퍼스 수집·분석 (2주)
업로드 파이프라인, StyleProfile, 난이도, n-gram, pgvector 검색, 라이브러리 UI, OMR 검수.
Acceptance: 30곡 시드 후 난이도 Spearman ρ ≥ 0.7, 검색 4/5 일치, OMR 60초.

### M3a — 모티브·설계 공동작곡 (2주) — v3 개정
학생 프로필, 요청 폼, 콩쿨 프로필, Stage 0~2(컨텍스트·모티브 후보·Plan), MotifPicker/PlanReview UI, 원장 입력 모티브(피아노롤 4마디 / 채보 연동은 M6 후 활성).
Acceptance: 골든 20건에서 모티브 후보 5개 생성 ≤ 20초, 각 후보 미리듣기 즉시 재생, 원장이 "쓸 만한 모티브가 하나 이상 있다"고 답한 비율 ≥ 80%; Plan 규칙 검사 통과율 100%; Plan 수정→재검사 왕복 동작.

### M3b — 실현·비평 루프 (3주) — v3 개정
Stage 3~5(프레이즈 순차 Realize, Assemble, 검증기, 음악성 지표, 비평가 루프), 품질 리포트 UI, 3안 비교, 표절 검사, SSE.
Acceptance: 골든 20건×3회 = 60회에서 하드 검증 통과 ≥ 95%, 비평 총점 ≥ 7.0 도달률 ≥ 80%(2라운드 내), 평균 소요 ≤ 150초, 모티브 일관성 지표 ≥ 0.7 달성률 ≥ 90%, 원장 블라인드 평가(5점 척도) 평균 ≥ 3.8, "앞뒤가 따로 논다" 평가 ≤ 10%.

### M4 — 에디터 (3주)
선택·삭제·이조·길이·삽입·팔레트·마디 조작·Undo/Redo·버전·AI 구간 재생성·A/B.
Acceptance: Playwright E2E "17~20마디 드래그→삭제→Undo→왼손 더 쉽게→저장" 통과, 편집 후 재검증 100%, 100마디 재렌더 ≤ 1.0초.

### M5 — 해설·운지·내보내기·모의 심사 (2주)
Guide 연동, pianoplayer, PDF/MP3 4종/MIDI/MXL/ZIP, 콩쿨 모드 모의 심사 3인 패널, 결과 기록.
Acceptance: 해설 마디 참조 100% 유효, PDF 누락 0, MP3 4종 ≤ 60초, 심사 리포트의 revision 제안 마디가 실제 범위 내 100%, 콩쿨 규정 위반 곡이 "제출 가능"으로 표시되지 않음(테스트).

### M6 — 오디오→MIDI 채보 (2주) — v2 신규
전처리, ByteDance 엔진 + basic-pitch 폴백, 후처리·손 분리, 정렬(DTW), 템포·박자 추정, 양자화→MusicXML 초안, 피아노롤 UI·최소 편집, 코퍼스 등록.
Acceptance: 테스트 픽스처 5개(스마트폰 녹음 30초, 정답 MIDI) onset F1 ≥ 0.85(50ms 허용), 페달 검출 ≥ 0.8; 연결 곡 정렬 시 pitch 보정 후 F1 +0.05 이상; 2분 30초 곡 CPU 채보 ≤ 4분; 양자화 초안이 music21 재파싱·OSMD 렌더 성공.

### M7 — 시각화 렌더러 + 릴스 메이커 (3주) — v2 신규
`lib/visualizer` 순수 렌더러, 브라우저 프리뷰, render-worker(Playwright→ffmpeg), 템플릿 5종, 하이라이트 추천, 자막·브랜드 킷, Claude 캡션 3안, 배송(출력 폴더/웹훅), 에디터·채보 화면의 `릴스 만들기` 진입.
Acceptance: 60초·1080×1920·30fps 렌더 ≤ 90초(4코어 CPU), 프리뷰 30fps 유지(노트 2천 개 곡), 프레임 스냅샷 diff ≤ 0.5%, 오디오-노트 싱크 오차 ≤ 1프레임(33ms, 자동 측정: 히트 플래시 프레임 vs onset), 생성곡·채보·업로드 MIDI 3개 소스 모두 E2E 통과, `media_consent=false` 학생은 이름 마스킹 확인 테스트.

### M8 — 연주회 빌더 + 품질 고도화 (3주) — v3 개정
연주회 프로그램 빌더(일괄 생성·대비 검사·순서·프로그램북 PDF·티저 일괄 렌더), 난이도·음악성 가중치 보정(원장 평가 데이터), 프롬프트 튜닝(👍/👎 + 콩쿨 결과 학습 주입), 실패 대시보드, 채보 벤치마크, 렌더 성능, 백업/복원.
Acceptance: 학생 10명 연주회 일괄 생성 → 프로그램북 PDF까지 30분 이내(무인), 대비 경고가 연속 동일 조성/템포를 100% 잡음; 원장 평가 ≥ 4.0, "수정 없이 사용" ≥ 60%, 릴스 "수정 없이 게시" ≥ 70%.

### M9 (선택)
NotaGen 엔진 B · 학생용 연습 링크(연주 정확도 피드백, 채보 정렬 결과 활용) · GPU 채보 서버 분리 · WebGL 파티클 · Tauri 데스크톱 패키징 · 릴스 업로더와 양방향 상태 동기.

---

## 12. CLAUDE.md (저장소 루트에 그대로 사용)

```markdown
# ConcoursComposer — 작업 규칙

## 제품
학생 맞춤형 AI 콩쿨 독창곡 생성기 + 오디오→MIDI 연주 시각화(Synthesia 스타일) 릴스 메이커.
스펙은 SPEC.md, 현재 마일스톤은 docs/STATUS.md. 피아노(2단 보표)만 지원.
작곡 축 SoT = 서버 MusicXML 버전. 시각화 축 SoT = NoteEvents JSON.

## 절대 규칙
1. LLM이 MusicXML XML 문자열을 직접 생성하게 하지 않는다. LLM → JSON → music21 → MusicXML.
2. 검증기를 통과하지 않은 악보는 저장하지 않는다.
3. copyright_status=copyrighted 코퍼스의 음표열은 어떤 프롬프트에도 넣지 않는다(tests/test_copyright_guard.py).
4. 모든 <note>에 안정적인 id 속성을 유지한다.
5. 시각화 렌더러 lib/visualizer/render.ts 는 순수 함수(입력: state, t). Math.random·Date.now·rAF 시간 참조 금지.
   프리뷰와 서버 렌더는 반드시 같은 번들을 사용한다. 스냅샷 테스트가 통과해야 머지.
6. 채보 엔진 호출은 타임아웃(오디오 길이×3)·폴백(basic-pitch)·엔진명 기록이 필수.
7. 릴스 렌더 전 students.media_consent 검사. 동의 없으면 이름 마스킹 + 공개 템플릿 차단.
8. 새 기능은 마일스톤 Acceptance 테스트를 먼저 작성/갱신한 뒤 구현한다.
9. 작곡은 반드시 모티브 잠금 → Plan → 프레이즈 단위 Realize → 비평 루프 순서. 32마디를 한 호출로 생성하는 코드는 금지.
10. 작곡가(realize)와 비평가(critic)는 별도 프롬프트·별도 호출. 비평 문턱 미달 곡은 원장에게 "초안(미통과)"으로만 표시.
11. 프롬프트 변경은 `make golden` 회귀(검증 통과율·musicality·비평 총점) 비교 결과를 PR에 첨부한다.
12. 모델 문자열은 env(COMPOSER_MODEL, WRITER_MODEL)로만 참조. 코드에 하드코딩 금지. 시작 시 docs.claude.com 모델 목록으로 유효성 확인.

## 작곡 품질 기준(요약)
SPEC.md §7.4 음악성 지표, §7.5 비평 루브릭, §7.6 검증기, §7.9 이상한 곡 방지 6원칙을 항상 적용.

## 스택
web: Next.js 15 + TS + Tailwind + Zustand + opensheetmusicdisplay + tone + Canvas2D
render-worker: Node + Playwright(chromium) + ffmpeg (lib/visualizer 워크스페이스 공유)
server: Python 3.12 + FastAPI + SQLAlchemy 2 + music21 + Celery + pgvector + torch(cpu) + piano_transcription_inference + basic-pitch + librosa
tools: MuseScore 4 CLI(xvfb-run), Audiveris, ffmpeg, fluidsynth, pianoplayer

## 명령
make up / make down / make test / make e2e / make demo-mN / make seed / make download-models / make bench-transcription
server: uv run pytest ; web: pnpm test ; e2e: pnpm playwright test ; render: pnpm --filter render-worker test

## 코드 규칙
- Python: ruff + mypy strict, Pydantic v2 스키마는 schemas/ 에만.
- TS: strict, 악보 편집은 Command 패턴, 직접 DOM 조작은 SelectionOverlay/NoteEditOverlay 안에서만.
- 프롬프트는 server/app/generation/prompts/*.md, server/app/reels/prompts/*.md 로만 관리.
- 긴 작업(>5s)은 Celery 태스크 + jobs 테이블 + SSE. 렌더는 render-worker HTTP 위임.
- 한국어 UI 문구는 web/messages/ko.json. 릴스 템플릿은 server/app/reels/templates/*.json.

## 작업 방식
- 한 번에 하나의 마일스톤 항목만. docs/STATUS.md 체크리스트 갱신 → 구현 → Acceptance 결과 기록.
- 외부 도구(mscore, audiveris, ffmpeg, chromium) 호출은 타임아웃·에러 캡처·로그 필수.
- 음악 이론 규칙·채보 후처리 휴리스틱의 근거는 server/app/analysis/README.md, server/app/transcription/README.md 에 적는다.
```

---

## 13. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| LLM 생성곡이 밋밋하거나 앞뒤가 따로 놈 (**최대 리스크**) | 모티브 우선 잠금, 프레이즈 단위 순차 실현 + 모티브 처리 기법 명시, 별도 비평가 루프, 음악성 지표 문턱, 3안 비교, 골든 회귀, 원장 편곡 단계. 그래도 부족하면 M9 심볼릭 엔진을 모티브 다양성에 투입 |
| "입상 보장" 기대 | 시스템은 확률을 높일 뿐임을 UI 문구·문서에 명시. 콩쿨 프로필로 규정 위반 방지, 모의 심사·결과 학습으로 개선 |
| 대회가 창작곡을 불허하거나 악보 제출 규정이 있음 | competition_profiles.original_allowed=false면 해당 프로필로 생성 차단·경고. 제출용 PDF 규정(작곡가 표기 등) 템플릿화 |
| OMR 정확도 | needs_review 강제, 검수 UI, MusicXML 원본 확보 권장 |
| OSMD 편집 한계 | 편집은 ScoreModel, OSMD는 렌더만 |
| **스마트폰 녹음 채보 오류**(잔향·잡음·업라이트 피아노 음색) | 라우드니스 정규화·noisereduce·연결 곡 DTW 보정, 신뢰도 낮은 노트 시각 표시, 피아노롤 최소 편집, 픽스처 벤치마크 유지 |
| **CPU 채보 속도** | 길이 제한 10분, 진행률 표시, GPU 서버 분리(M9), basic-pitch 폴백 |
| **프리뷰 ≠ 렌더 결과** | 순수 함수 렌더러 + 동일 번들 + 스냅샷 테스트(절대 규칙 5) |
| **렌더 시간** | 프레임 PNG 파이프(디스크 미경유), 파티클 오프스크린 캐시, 해상도 프리셋(720p 초안 렌더 → 최종 1080p). 대안: Remotion(소규모 사업자 무료) 도입 시 render-worker만 교체 |
| **오디오-영상 싱크** | 오디오가 마스터 클록, 프레임 t = n/fps 정확 계산, ffmpeg `-shortest` + 시작 오프셋 검증 테스트 |
| **초상권·개인정보(학생 릴스)** | media_consent 필드, 이름 마스킹, 공개 템플릿 차단, 원본 영상 보존 기간 설정(env) |
| 저작권(연주곡) | 릴스 BGM 미지원(연주 소리만), 코퍼스 곡 연주 릴스는 저작권 상태 표시·경고 |
| MuseScore CLI 헤드리스 불안정 | xvfb-run + 재시도 + FluidSynth 폴백 |
| API 비용 | 섹션 병렬 생성, 요청당 비용 상한 env, 릴스 캡션은 저비용 모델 허용 |

---

## 14. 시작 지시 (Claude Code 첫 세션에 붙여넣기)

```
SPEC.md와 CLAUDE.md를 읽고 M0을 시작해줘.
1) 저장소 구조(§10)를 pnpm 워크스페이스(web, render-worker 공유)로 생성하고
   docker-compose(web, api, worker-py, worker-render, db+pgvector, redis)를 작성해.
2) server/Dockerfile에 MuseScore 4 AppImage(headless, xvfb), Audiveris, ffmpeg, fluidsynth,
   torch(cpu), piano_transcription_inference, basic-pitch, librosa를 설치하고
   render-worker/Dockerfile에 playwright chromium + ffmpeg를 설치해.
3) scripts/download_models.py로 채보 체크포인트를 받게 하고,
   `make check-tools`가 mscore/audiveris/ffmpeg/music21/torch+체크포인트/chromium 6개를 모두 검증하게 해.
4) docs/STATUS.md를 만들고 M0 체크리스트를 기록해.
5) .env.example에 ANTHROPIC_API_KEY, COMPOSER_MODEL, WRITER_MODEL, MAX_COST_PER_COMPOSITION,
   REELS_OUTPUT_DIR, REELS_WEBHOOK_URL을 넣고, server 시작 시 모델 문자열 유효성 검사를 추가해.
완료되면 `make up && make check-tools` 결과를 보여줘. M1은 내가 확인한 뒤 진행할게.
이후 마일스톤은 M1 → M2 → M3a → M3b → M4 → M5 → M6 → M7 → M8 순서로, 각 단계 시작 전에 STATUS.md를 갱신하고
Acceptance 테스트를 먼저 작성한 뒤 구현해. 작곡 파이프라인(M3a/M3b)은 SPEC.md §7.9의 6원칙을 코드 리뷰 체크리스트로 사용해.
```
