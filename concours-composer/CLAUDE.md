# ConcoursComposer — 작업 규칙

## 제품
학생 맞춤형 AI 콩쿨 독창곡 생성기. 피아노(2단 보표)만 지원.
스펙은 SPEC.md, **실제 구현 범위는 docs/SCOPE.md**, 현재 마일스톤은 docs/STATUS.md.
SoT = 서버 MusicXML 버전. 재생·분석용 절대시간 표현은 NoteEvents JSON.

**범위**: SPEC.md 의 B축(§6.10 채보 · §6.11 시각화 · §6.12 릴스, M6·M7)은 원장 결정으로 제외.
이 저장소의 목표는 단 하나 — **콩쿨곡 작곡 품질**. 새 기능 제안은 그것에 기여할 때만 받는다.

## 절대 규칙
1. LLM이 MusicXML XML 문자열을 직접 생성하게 하지 않는다. LLM → JSON → music21 → MusicXML.
2. 검증기를 통과하지 않은 악보는 저장하지 않는다.
3. copyright_status=copyrighted 코퍼스의 음표열은 어떤 프롬프트에도 넣지 않는다(tests/test_copyright_guard.py).
4. 모든 <note>에 안정적인 id 속성을 유지한다.
5. (제외된 규칙 — 시각화 렌더러)
6. (제외된 규칙 — 채보 엔진)
7. 학생 이름을 외부로 내보내는 산출물(악보 표지·프로그램북)은 students.media_consent 를 검사하고,
   동의가 없으면 Student.display_name() 의 마스킹을 쓴다.
8. 새 기능은 마일스톤 Acceptance 테스트를 먼저 작성/갱신한 뒤 구현한다.
9. 작곡은 반드시 모티브 잠금 → Plan → 프레이즈 단위 Realize → 비평 루프 순서. 32마디를 한 호출로 생성하는 코드는 금지.
10. 작곡가(realize)와 비평가(critic)는 별도 프롬프트·별도 호출. 비평 문턱 미달 곡은 원장에게 "초안(미통과)"으로만 표시.
11. 프롬프트 변경은 `make golden` 회귀(검증 통과율·musicality·비평 총점) 비교 결과를 PR에 첨부한다.
12. 모델 문자열은 env(COMPOSER_MODEL, WRITER_MODEL)로만 참조. 코드에 하드코딩 금지. 시작 시 docs.claude.com 모델 목록으로 유효성 확인.

## 작곡 품질 기준(요약)
SPEC.md §7.4 음악성 지표, §7.5 비평 루브릭, §7.6 검증기, §7.9 이상한 곡 방지 6원칙을 항상 적용.

## 스택
web: Next.js 15 + TS + Tailwind + Zustand + opensheetmusicdisplay + tone
server: Python 3.12 + FastAPI + SQLAlchemy 2 + music21 + Celery + pgvector
tools: MuseScore 4 CLI(xvfb-run), Audiveris, ffmpeg, fluidsynth, pianoplayer

## 명령
make up / make down / make test / make e2e / make golden / make demo-m3 / make demo-judge / make seed
server: .venv/bin/pytest server/tests ; web: pnpm test ; e2e: pnpm playwright test

## 코드 규칙
- Python: ruff + mypy strict, Pydantic v2 스키마는 schemas/ 에만.
- TS: strict, 악보 편집은 Command 패턴, 직접 DOM 조작은 SelectionOverlay/NoteEditOverlay 안에서만.
- 프롬프트는 server/app/generation/prompts/*.md, server/app/judge/prompts/*.md 로만 관리.
- 긴 작업(>5s)은 Celery 태스크 + jobs 테이블 + SSE.
- 한국어 UI 문구는 web/messages/ko.json.

## 작업 방식
- 한 번에 하나의 마일스톤 항목만. docs/STATUS.md 체크리스트 갱신 → 구현 → Acceptance 결과 기록.
- 외부 도구(mscore, audiveris, ffmpeg, chromium) 호출은 타임아웃·에러 캡처·로그 필수.
- 음악 이론 규칙·음악성 지표 문턱의 근거는 server/app/analysis/README.md 에 적는다.
