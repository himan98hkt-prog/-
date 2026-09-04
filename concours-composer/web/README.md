# web — 원장용 화면

`index.html` 하나로 도는 무빌드 UI다. API 서버(`make up` 또는 `uvicorn app.main:app`)를
띄운 뒤 이 파일을 브라우저로 열면 된다. API 주소를 바꾸려면 콘솔에서
`localStorage.setItem("cc_api", "http://192.168.0.10:8000")`.

담는 것은 작곡 워크플로 전부다.

- 요청 — 학생 제약과 실현 가능한 난이도 대역을 즉시 보여준다
- 모티브 고르기 — **들어보기** 버튼(Web Audio 로 즉시 재생). §7.3 Stage 1 은 듣고 고르는 단계다
- 설계 승인 — 형식·마디별 화성·모티브 처리 표
- 결과 — 음악성 지표 8종, 비평가의 마디별 수정 지시, **3안 비교표**
- 모의 심사 3인 · 연주법 해설(4주 연습 계획·암보 구획)
- MusicXML · MIDI 내려받기

미리듣기는 삼각파 오실레이터다. 음정·리듬을 판단하기엔 충분하지만 음색은 피아노가 아니다.
M1 에서 Tone.js + Salamander 샘플로 바꾼다.

## 아직 없는 것 (M1 / M4)
악보 렌더(OSMD)와 재생(Tone.js), 마우스 편집은 브라우저 라이브러리가 필요하다.
그 단계에서 Next.js 15 + TypeScript 로 옮기고 이 파일의 흐름을 그대로 컴포넌트로 나눈다:

- `ScoreView` — MusicXML → OSMD, `<note id>` ↔ GraphicalNote 매핑
- `Player` — Tone.js Sampler + Salamander 샘플, OSMD 커서 동기
- `SelectionOverlay` / `EditToolbar` — 드래그 러버밴드 선택, Command 패턴 편집
- `MotifPicker` / `PlanReview` / `QualityReport` / `JudgePanel` — 이 파일의 각 섹션

서버 API 는 그대로 쓴다. 화면을 바꿔도 §7.6 검증기와 §7.4 지표는 서버에 남는다.
