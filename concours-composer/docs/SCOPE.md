# 범위 결정 기록

## 2026-08-31 — B축(오디오→MIDI 채보 · 연주 시각화 · 릴스 메이커) 제외

SPEC.md 는 두 축(A: 작곡 · B: 시각화·릴스)을 담고 있으나, 원장 결정으로 **B축은 구현하지 않는다**.
사유: 실제로 활용하지 않는 기능이며, 개발 역량을 **콩쿨곡 작곡 품질** 한 곳에 모으는 편이 낫다.

### 제외되는 SPEC 항목
- §6.10 오디오 → MIDI 채보 (Transcription)
- §6.11 연주 시각화 렌더러 (Synthesia 스타일)
- §6.12 릴스 메이커 (ReelStudio) · 브랜드 킷 · 하이라이트 추천 · 캡션 생성
- §11 M6, M7 마일스톤 전체
- 데이터 모델의 `media_assets` / `transcriptions` / `brand_kits` / `reel_*` 테이블
- API 의 `/api/media`, `/api/transcriptions`, `/api/brand-kits`, `/api/reel-templates`, `/api/reels/*`
- 서비스 `worker-render`, 패키지 `render-worker`, `web/lib/visualizer`
- 의존성 torch · piano_transcription_inference · basic-pitch · librosa · playwright chromium

### 유지되는 것
- `media_consent` 와 이름 마스킹 규칙 — 프로그램북·악보 표지의 학생 이름 표기에 그대로 쓴다.
- `NoteEvent` / `NoteEvents` 스키마 — 재생·미리듣기·음악성 분석이 절대 시간 표현을 쓴다.
- SPEC.md 원문은 기록으로 그대로 둔다. 이 문서가 실제 구현 범위의 기준이다.

### 되살릴 때
Stage 1 의 "흥얼거린 멜로디 → 채보 → 모티브" 입력만 채보가 필요하다.
그때는 §6.10 파이프라인 중 전처리·채보·후처리만 되살리면 되고, 릴스는 여전히 불필요하다.

---

## 재조정된 마일스톤

| | 내용 | 상태 |
|---|---|---|
| M0 | 골격 · check-tools | 완료 |
| M1 | 뷰어 + 재생 | 진행 |
| M2 | 코퍼스 분석 · 난이도 · 표절 | 코어 완료 |
| M3a | 모티브 · Plan 공동작곡 | 코어 완료 |
| M3b | 프레이즈 Realize · 비평 루프 | 코어 완료 |
| M4 | 에디터 | 진행 |
| M5 | 해설 · 운지 · 내보내기 · 모의 심사 | 진행 |
| ~~M6~~ | ~~채보~~ | **제외** |
| ~~M7~~ | ~~시각화·릴스~~ | **제외** |
| M8 | 연주회 빌더 · 품질 고도화(골든 회귀·가중치 보정) | 진행 |
