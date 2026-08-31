# ConcoursComposer — 진행 상황

> CLAUDE.md 작업 방식: 마일스톤 항목을 하나씩. 시작 전 이 파일 갱신 → Acceptance 테스트 작성 → 구현 → 결과 기록.

현재 마일스톤: **M0·M2·M3a·M3b 코어 완료 · M5 부분 · 다음은 M1(악보 렌더·재생)**
테스트 93건 통과 · 골든 20건 회귀 통과
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
- [ ] OSMD 악보 렌더 · 커서 동기
- [ ] Tone.js Sampler 재생 · 손 분리 · 루프
- [ ] Next.js 15 전환 (web/README.md 에 컴포넌트 분해 계획)

## M2 — 코퍼스 수집·분석
- [x] StyleProfile 추출(§7.1) — music21 기반, 채보/생성물에도 동일 적용
- [x] 난이도 점수 1~10(§7.7)
- [x] 멜로디 n-gram 인덱스 + 표절 검사(8마디)
- [x] 저작권 가드(copyrighted 곡 음표열은 프롬프트 유입 차단)
- [ ] pgvector 검색 · OMR 검수 UI

## M3a — 모티브·설계 공동작곡
- [x] ComposerContext 조립(Stage 0) — 하드/소프트 제약, 콩쿨 프로필, 코퍼스 발췌 규칙
- [x] Stage 1 모티브 후보 생성 + 원장 선택/직접 입력, `motif_locked`
- [x] Stage 2 CompositionPlan + Plan 규칙 검사(제한 시간·종지·대비·쇼케이스·클라이맥스 위치)
- [x] 모티브 선택 · 설계 승인 화면(web/index.html)
- [ ] 4마디 피아노롤 직접 입력

## M3b — 실현·비평 루프
- [x] Stage 3 프레이즈(4마디) 단위 순차 Realize — 32마디 1호출 금지 가드
- [x] Stage 4 Assemble(music21 결정적) → MusicXML 3.1, 모든 `<note id>`
- [x] Stage 5 음악성 지표(§7.4) + 비평 루프(최대 2라운드, 별도 프롬프트·별도 호출)
- [x] 검증기 하드 규칙(§7.6) — 실패 시 저장 불가
- [x] 오프라인 결정적 스텁 엔진(테스트·데모용, API 키 없이 파이프라인 전체 실행)
- [x] 골든 20건 회귀 harness (`make golden` → docs/golden-report.md)
- [x] 스텁 엔진 골든: 하드 검증 100% · 프레이즈 완성 100% · 난이도 ±1 60%
- [ ] **실제 Claude 엔진 골든 실측** — `ANTHROPIC_API_KEY` 와 `GOLDEN_ENGINE=claude` 필요.
      M3b Acceptance(비평 총점 ≥ 7.0 도달률 ≥ 80%, 원장 블라인드 평가 ≥ 3.8)는 이 실측 뒤에 판정한다

## M4 — 에디터
- [x] AI 구간 재생성 경로(비평 루프가 같은 코드로 프레이즈를 다시 쓴다)
- [ ] Command 패턴 편집 코어 · SelectionOverlay 드래그 러버밴드 · A/B 비교 청취

## M5 — 해설·운지·내보내기·모의 심사
- [x] 모의 심사 3인 패널(judge/) — 페르소나·루브릭·지적 마디가 곡 안에 있는지 테스트
- [x] 콩쿨 결과 기록 → '학원 실전 데이터' 요약(recital/learning.py)
- [x] 해설 프롬프트(guide/prompts/guide.md)
- [ ] Guide 호출 배선 · pianoplayer 운지 · PDF/MP3 4종 (ffmpeg·MuseScore 필요)

## ~~M6 — 오디오→MIDI 채보~~ · ~~M7 — 시각화·릴스~~ — **제외**
원장 결정(2026-08-31)으로 B축 전체를 구현하지 않는다. 근거와 되살리는 방법은 docs/SCOPE.md.

## M8 — 연주회 빌더 + 품질 고도화
- [x] 프로그램 대비 검사(연속 조성·템포 중복 100% 검출) · 총 러닝타임(등퇴장 45초) · 순서 규칙 3종
- [x] 콩쿨 결과 학습 주입 경로
- [ ] 일괄 생성 큐 · 프로그램북 PDF · 난이도/음악성 가중치 보정

## M9 (선택)
- [ ] NotaGen 엔진 B(모티브 다양성 보강) · Tauri 데스크톱 패키징

---

## 알려진 한계 (정직하게)

1. **실제 모델 품질은 아직 측정되지 않았다.** 파이프라인·검증기·지표는 전부 동작하고
   테스트로 확인했지만, `COMPOSER_MODEL` 을 실제로 호출한 골든 실측은 API 키가 있는
   환경에서 `GOLDEN_ENGINE=claude make golden` 으로 돌려야 한다. SPEC §1.2 의
   "수정 없이 바로 쓸 수 있는 비율 60%" 는 그 뒤에 판정할 수 있다.
2. **규칙 기반 스텁 엔진의 표현 폭은 난이도 3~7 이다.** 유치부(2)나 중등 상급(8~9)
   목표는 스텁으로 맞추지 못한다. 파이프라인 결함이 아니라 test double 의 한계이며,
   골든에서 엔진별 기준선(`DIFFICULTY_BASELINE`)으로 분리해 두었다.
3. **저장소는 아직 프로세스 메모리다.** `server/app/api/deps.py` 의 `Store` 한 곳만
   PostgreSQL 로 바꾸면 되도록 모아 두었다. Alembic 마이그레이션은 아직 없다.
4. **긴 작업이 동기 실행이다.** Celery 워커는 compose 파일에 있으나 태스크 배선은
   아직 없다. 32마디 스텁 생성은 1초 이내라 문제되지 않지만, 실제 Claude 호출은
   프레이즈당 수 초이므로 M3b 실측 전에 Celery + SSE 를 붙여야 한다.
5. **ffmpeg·MuseScore·Audiveris 가 없는 환경에서는** MP3/PDF 내보내기와 OMR 이 동작하지
   않는다. `make check-tools` 가 정확히 무엇이 빠졌는지 보고한다.
