# ConcoursComposer — 진행 상황

> CLAUDE.md 작업 방식: 마일스톤 항목을 하나씩. 시작 전 이 파일 갱신 → Acceptance 테스트 작성 → 구현 → 결과 기록.

현재 마일스톤: **M0·M1(렌더·재생)·M2·M3a·M3b·M5 코어 완료 · 세션 엔진으로 5곡 재작곡 완료**
테스트 159건 통과 · 골든 20건 회귀 통과 · ruff/mypy 클린 · 다음은 M4(마우스 에디터)
범위: B축(채보·시각화·릴스) 제외 — docs/SCOPE.md

## 범례
- [x] 완료(테스트로 확인) · [~] 부분 구현(실제 외부 의존성 필요) · [ ] 미착수

---

## M0 — 골격
- [x] pnpm 워크스페이스(web · render-worker 공유) 생성
- [x] docker-compose 6개 서비스(web, api, worker-py, worker-render, db+pgvector, redis)
- [x] server/Dockerfile: MuseScore 4 AppImage(xvfb) · Audiveris · ffmpeg · fluidsynth · torch(cpu) · piano_transcription_inference · basic-pitch · librosa
- [x] render-worker/Dockerfile: playwright chromium + ffmpeg
- [x] scripts/download_models.py — 채보 체크포인트(Zenodo)
- [x] `make check-tools` 6종 검증(mscore/audiveris/ffmpeg/music21/torch+체크포인트/chromium)
- [x] .env.example (ANTHROPIC_API_KEY, COMPOSER_MODEL, WRITER_MODEL, MAX_COST_PER_COMPOSITION, REELS_OUTPUT_DIR, REELS_WEBHOOK_URL)
- [x] 서버 시작 시 모델 문자열 유효성 검사(`MODEL_VALIDATION=strict|warn|off`)
- [x] docs/STATUS.md

**Acceptance 결과**: `make check-tools` 는 개발 컨테이너(ffmpeg 없음)에서 FAIL/WARN 을 정확히 보고한다 —
검사기 자체는 동작. 전체 OK 는 `make up` 한 Docker 이미지에서 확인한다.
B축 제외에 따라 torch·chromium 검사는 선택 항목으로 남겨두었다(설치돼 있으면 확인만 한다).

---

## M1 — 뷰어 + 재생
- [x] 무빌드 원장 화면(`web/index.html`) — 요청·모티브·설계·품질·심사·MusicXML 내려받기
      (실제 브라우저에서 전 흐름 확인)
- [x] OSMD 악보 렌더 · 마디 단위 커서 동기
- [x] Tone.js Sampler 재생(살라만더 피아노) · 손 분리(양손/오른손/왼손) · 템포 조절
      CDN 이 막힌 환경에서는 브라우저 내장 오실레이터로 같은 스케줄을 연주한다
      (이 개발 컨테이너에서 폴백 경로까지 실제 브라우저로 확인)
- [ ] Next.js 15 전환 (web/README.md 에 컴포넌트 분해 계획)

## M2 — 코퍼스 수집·분석
- [x] StyleProfile 추출(§7.1) — music21 기반, 채보/생성물에도 동일 적용
- [x] 난이도 점수 1~10(§7.7)
- [x] 멜로디 n-gram 인덱스 + 표절 검사(8마디)
- [x] 저작권 가드(copyrighted 곡 음표열은 프롬프트 유입 차단)
- [x] StyleProfile 추출(§7.1) — 코퍼스·생성곡에 같은 분석
- [x] 코퍼스 업로드(MusicXML/MIDI) → 파싱 → 프로필 → 검색 인덱스
- [x] RAG 검색(§7.8): 상위 10 → 난이도 ±2 필터 → 상위 5, 원장 지정 곡 항상 포함
- [x] 코퍼스가 Stage 0 컨텍스트와 표절 검사에 실제로 주입된다
- [ ] pgvector 로 이관(현재 코사인 인메모리) · OMR 검수 UI

## M3a — 모티브·설계 공동작곡
- [x] ComposerContext 조립(Stage 0) — 하드/소프트 제약, 콩쿨 프로필, 코퍼스 발췌 규칙
- [x] Stage 1 모티브 후보 생성 + 원장 선택/직접 입력, `motif_locked`
- [x] Stage 2 CompositionPlan + Plan 규칙 검사(제한 시간·종지·대비·쇼케이스·클라이맥스 위치)
- [x] 모티브 선택 · 설계 승인 화면(web/index.html)
- [x] 모티브 미리듣기(§7.3 Stage 1 "들어본 뒤 고른다") — MIDI + 브라우저 재생
- [ ] 4마디 피아노롤 직접 입력(현재는 JSON 으로만 가능)

## M3b — 실현·비평 루프
- [x] Stage 3 프레이즈(4마디) 단위 순차 Realize — 32마디 1호출 금지 가드
- [x] Stage 4 Assemble(music21 결정적) → MusicXML 3.1, 모든 `<note id>`
- [x] Stage 5 음악성 지표(§7.4) + 비평 루프(최대 2라운드, 별도 프롬프트·별도 호출)
- [x] 검증기 하드 규칙(§7.6) — 실패 시 저장 불가
- [x] 오프라인 결정적 스텁 엔진(테스트·데모용, API 키 없이 파이프라인 전체 실행)
- [x] 3안 생성 + 종합점수 최고안 자동 선택(§7.9 원칙 5)
- [x] 검증기 소프트 경고를 비평가에게 전달 → 수정 지시로 전환
- [x] 마무리 다듬기 패스 — 문턱을 넘어도 남은 흠을 한 번 더 고친다(점수가 떨어지면 폐기)
- [x] 골든 20건 회귀 harness (`make golden` → docs/golden-report.md)
- [x] 스텁 엔진 골든: 하드 검증 100% · 프레이즈 완성 100% · 난이도 ±1 60%
- [x] **세션 엔진(`GOLDEN_ENGINE=session`)** — API 없이 이 Claude 세션이 작곡가·비평가를 맡는다.
      프롬프트를 파일로 내놓고 응답 JSON 을 기다린다. 검증기·지표·표절 검사는 코드가 그대로 실행.
      문서: docs/SESSION_ENGINE.md
- [x] **세션 작곡 5곡 완료** — 전부 하드 검증 통과, 병행 5·8도 0건, 비평 총점 7.55~7.95.
      결과·비용: runs/golden/SUMMARY.md
- [x] 프롬프트 캐싱(고정 컨텍스트) · Batch API 경로 · 곡당 토큰·비용 로깅
- [ ] **실제 Claude API 골든 실측** — `.env` 에 키를 넣고 `GOLDEN_ENGINE=claude make golden`.
      곡당 예상 비용은 세션 작곡 실측 기준 캐시 적용 약 $0.49 (runs/golden/SUMMARY.md)

## M4 — 에디터
- [x] AI 구간 재생성 경로(비평 루프가 같은 코드로 프레이즈를 다시 쓴다)
- [ ] Command 패턴 편집 코어 · SelectionOverlay 드래그 러버밴드 · A/B 비교 청취

## M5 — 해설·운지·내보내기·모의 심사
- [x] 모의 심사 3인 패널(judge/) — 페르소나·루브릭·지적 마디가 곡 안에 있는지 테스트
- [x] 콩쿨 결과 기록 → '학원 실전 데이터' 요약(recital/learning.py)
- [x] 해설 프롬프트(guide/prompts/guide.md)
- [x] 연주법 해설(§6.6) 배선 — 마디 앵커 유효성 검사, 실패 시 1회 재요청
- [x] 제목 확정(후보 3 + 추천)
- [x] MIDI 내보내기(손별 트랙 분리)
- [ ] pianoplayer 운지 · PDF/MP3 4종 (ffmpeg·MuseScore 필요)

## ~~M6 — 오디오→MIDI 채보~~ · ~~M7 — 시각화·릴스~~ — **제외**
원장 결정(2026-08-31)으로 B축 전체를 구현하지 않는다. 근거와 되살리는 방법은 docs/SCOPE.md.

## 작곡 품질 개선 (2026-08-31 2차)
- [x] **프레이즈 길이 가변화** — 2~8마디. 제시 4+4 · 전개 4+2+2 · 재현 마지막 6마디 확장.
      Plan 규칙에 길이 하드 검사와 "전부 같은 길이" 경고를 넣었고, 클라이맥스 정렬을
      4마디 격자가 아니라 실제 프레이즈 시작에 맞췄다.
- [x] **연주 시간 예산 78%** — 제한의 절반도 안 쓰면 Plan 규칙이 경고한다.
      골든 20건이 22~96마디로 늘었고 전부 통과한다.
- [x] **표현 다양성 지표(§7.4 아홉 번째)** — 리듬 어휘·선율 음역·마디 리듬 중복·표현 기호를
      난이도 목표에 상대적으로 잰다. 순위가 아니라 바닥 감지기다(근거: analysis/README.md).
- [x] **골든 5곡 재작곡** — 24~80마디, 제한 시간의 73~78% 사용, 전부 하드 검증 통과·경고 0.
      이전 판은 `runs/golden-v1/` 에 보관.

## M8 — 연주회 빌더 + 품질 고도화
- [x] 프로그램 대비 검사(연속 조성·템포 중복 100% 검출) · 총 러닝타임(등퇴장 45초) · 순서 규칙 3종
- [x] 콩쿨 결과 학습 주입 경로
- [ ] 일괄 생성 큐 · 프로그램북 PDF · 난이도/음악성 가중치 보정

## M9 (선택)
- [ ] NotaGen 엔진 B(모티브 다양성 보강) · Tauri 데스크톱 패키징

---

## 알려진 한계 (정직하게)

1. **API 를 통한 대량 실측은 아직이다.** 세션 엔진으로 5곡을 실제로 작곡해 파이프라인
   전체가 사람(또는 모델)의 실제 출력으로 돌아간다는 것은 확인했다(2차 재작곡 포함). 다만 20곡 골든을
   `COMPOSER_MODEL` 로 돌린 통계는 없다 — `.env` 에 키를 넣고
   `GOLDEN_ENGINE=claude make golden` 으로 돌려야 한다. SPEC §1.2 의 "수정 없이 바로
   쓸 수 있는 비율 60%" 는 원장이 실제 곡을 평가해야 나오는 값이고, 그 수집 경로는
   `/api/feedback` 으로 열어 두었다.
2. **규칙 기반 스텁 엔진의 표현 폭은 난이도 3~7 이다.** 유치부(2)나 중등 상급(8~9)
   목표는 스텁으로 맞추지 못한다. 파이프라인 결함이 아니라 test double 의 한계이며,
   골든에서 엔진별 기준선(`DIFFICULTY_BASELINE`)으로 분리해 두었다.
3. **저장소는 SQLite 스냅샷이다.** 쓰기가 일어난 요청마다 전체를 파일로 내린다
   (`server/app/store/persistence.py`, 기본 경로 `data/store.sqlite3`).
   재시작해도 곡과 코퍼스가 남는다. 다만 동시 접속이 많아지면 스냅샷 방식이
   병목이 되므로, 그때 PostgreSQL+pgvector 로 옮긴다 — 전환 지점은 여전히
   `Store` 한 군데다. `STORE_PERSIST=0` 이면 예전처럼 메모리만 쓴다.
4. **긴 작업이 동기 실행이다.** Celery 워커는 compose 파일에 있으나 태스크 배선은
   아직 없다. 32마디 스텁 생성은 1초 이내라 문제되지 않지만, 실제 Claude 호출은
   프레이즈당 수 초이므로 M3b 실측 전에 Celery + SSE 를 붙여야 한다.
5. **ffmpeg·MuseScore·Audiveris 가 없는 환경에서는** MP3/PDF 내보내기와 OMR 이 동작하지
   않는다. `make check-tools` 가 정확히 무엇이 빠졌는지 보고한다.
6. **악보 렌더·피아노 음원은 첫 실행에 인터넷이 필요하다.** OSMD 와 Tone.js 를 CDN 에서
   받는다(무빌드 원칙 유지). 오프라인이면 악보는 안 그려지고 화면이 그 이유를 적으며,
   재생은 브라우저 내장 오실레이터로 계속된다. 완전 오프라인 배포가 필요하면
   두 라이브러리를 `web/vendor/` 에 받아 두고 script 경로만 바꾸면 된다.
7. **표현 다양성 지표는 순위를 매기지 못한다.** 제대로 쓴 곡들은 0.85~1.00 에 몰린다.
   밋밋한 곡(0.25)을 걸러내는 바닥 감지기이지 '어느 곡이 더 흥미로운가' 의 답이 아니다.
   그 판단은 원장이 듣고 `/api/feedback` 으로 남긴다.

---

## 원장 피드백 (§8 teacher_feedback)

- [x] 스키마 — 평가 시점의 음악성·비평·난이도를 **함께 얼려서** 저장한다.
      나중에 회귀하려면 "그때 이 곡의 지표가 얼마였는지" 가 있어야 한다.
- [x] 이유 태그를 §7.4 지표·§7.5 루브릭 이름과 겹쳐 두었다 — "원장이 👎 준 곡은 어떤
      지표가 낮았나" 를 바로 대조할 수 있다.
- [x] `edited_measures` — 실제로 손댄 마디. 어디가 약한지 가장 정직한 신호다.
- [x] API `/api/feedback` + 화면의 평가 패널
- [ ] **가중치 보정은 하지 않는다.** 표본 30건이 모이면 M8 에서 시작한다
      (`/api/feedback/stats` 의 `ready_for_recalibration`).
