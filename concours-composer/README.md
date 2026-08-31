# ConcoursComposer

학생 맞춤형 AI 콩쿨 독창곡 생성기. 원장이 학생의 수준·손 크기·성향·콩쿨 부문을 넣으면
**연주 가능한 독창곡**을 MusicXML 로 만든다.

명세는 [SPEC.md](SPEC.md), 실제 구현 범위는 [docs/SCOPE.md](docs/SCOPE.md),
진행 상황과 한계는 [docs/STATUS.md](docs/STATUS.md), 작업 규칙은 [CLAUDE.md](CLAUDE.md).

## 이 프로그램의 전제

언어모델에게 "32마디 콩쿨곡 써줘" 라고 하면 문법은 맞지만 밋밋하거나 앞뒤가 따로 노는
곡이 나온다. 그래서 이 시스템은 **작곡가가 일하는 순서**를 코드로 강제한다.

```
Stage 0  스타일 컨텍스트 조립      학생 하드 제약 + 콩쿨 규정 + 참고 스타일(저작권 가드 통과분)
Stage 1  모티브 후보 3~5개    ★   원장이 고른다. 고른 모티브는 잠기고 이후 전 단계가 참조한다
Stage 2  설계(Plan)          ★   형식·마디별 화성·클라이맥스·쇼케이스. 규칙 검사 통과해야 진행
Stage 3  프레이즈 단위 실현       2~8마디씩 순차 생성. 앞 8마디를 문맥으로 받는다. 즉시 검증
Stage 4  조립                    JSON → music21 → MusicXML 3.1 (결정적)
Stage 5  채점 + 비평 루프         규칙 지표 9종 + 별도 비평가 호출 → 미달이면 해당 프레이즈만 재생성
Stage 6  후처리                  운지·해설·모의 심사
Stage 7  원장 편곡           ★   구간 재생성·직접 편집
```

★ 는 사람이 개입하는 지점이다. **품질을 결정하는 것은 모델이 아니라 이 파이프라인의 설계**다.

## 품질을 지키는 장치

| 층 | 무엇을 막는가 |
|---|---|
| **검증기**(§7.6) | 마디 길이·손 스팬·음역·손 교차·기보 가능한 음길이·제한 시간·종지·임시표 비율·표절 n-gram·콩쿨 규정. 하나라도 어기면 **저장되지 않는다** |
| **음악성 지표**(§7.4) | 모티브 일관성 · 반복/변화 균형 · 선율 윤곽 · 화성 일치 · 프레이즈 호흡 · 다이내믹 곡선 · 텍스처 대비 · 연주 편의 · **표현 다양성**(난이도 대비 리듬 어휘·음역·표현 기호 — 밋밋한 곡을 걸러내는 바닥 감지기). 문턱의 근거는 [analysis/README.md](server/app/analysis/README.md) |
| **비평 루프**(§7.5) | 작곡가와 **다른 프롬프트·다른 호출**의 비평가가 10항목으로 채점하고 마디 범위별 수정 지시를 낸다. 문턱 미달이면 최대 2회 다시 쓴다 |
| **모의 심사**(§6.13) | 성향이 다른 심사위원 3인이 채점하고 "곡에서 고칠 점"과 "연습에서 보완할 점"을 분리해 준다 |
| **골든 회귀**(§7.8) | 요청 20건에 대해 검증 통과율·음악성·비평 총점을 기록. 프롬프트를 바꾸면 이 결과를 비교한다 |
| **3안 비교**(§7.9 원칙 5) | 같은 모티브로 최대 3안을 만들어 종합점수 최고안을 기본 표시하고 나머지는 비교 청취 |
| **자기 코퍼스**(§6.1 §7.8) | 원장이 올린 콩쿨 명곡·교재에서 StyleProfile 을 뽑아 요청마다 비슷한 곡을 찾아 주입. 저작권곡은 통계만 쓰고 음표열은 **보관조차 하지 않는다** |
| **원장 피드백**(§8) | 👍/👎 · 이유 태그 · **실제로 손댄 마디** 를 평가 시점의 지표와 함께 얼려 저장. 가중치 보정은 표본 30건 뒤(M8) |

## 작곡 엔진 세 가지

파이프라인은 어느 엔진인지 모른다 — 같은 `ComposerEngine` Protocol 을 구현한다.

| 엔진 | 언제 | 검증기·지표 |
|---|---|---|
| `ClaudeComposerEngine` | 운영. `.env` 에 API 키가 있으면 자동 | 그대로 적용 |
| `SessionComposerEngine` | Claude Code 세션이 직접 작곡 (API 미호출) | 그대로 적용 |
| `StubComposerEngine` | 테스트·CI·오프라인 데모 | 그대로 적용 |

세션 엔진 사용법과 산출물은 [docs/SESSION_ENGINE.md](docs/SESSION_ENGINE.md).
실제로 만든 5곡(24~80마디, 제한 시간의 73~78% 사용)의 결과·비용은
[runs/golden/SUMMARY.md](runs/golden/SUMMARY.md). 개선 전 판은 `runs/golden-v1/`.

**API 키는 프로젝트 `.env` 파일에서만 읽는다.** 시스템 환경변수는 쓰지 않는다.

## 빠르게 돌려보기

```bash
cp .env.example .env          # ANTHROPIC_API_KEY 를 넣는다. 없으면 규칙 기반 스텁으로 돈다
make venv && make check-tools # 외부 도구 점검
make test                     # 159건
make demo-m3                  # 모티브 → 설계 → 작곡 → 채점 → 비평, 전 과정 출력
make demo-judge               # 모의 심사 3인
make golden                   # 골든 20건 회귀 → docs/golden-report.md
```

화면은 API 를 띄우고 `web/index.html` 을 브라우저로 열면 된다. 결과 화면에서
악보(OSMD)를 보고 피아노 음원(Tone.js)으로 들을 수 있다 — 양손/오른손/왼손 분리,
템포 조절, 마디 커서. 두 라이브러리는 CDN 에서 받으므로 **첫 실행에 인터넷이 필요**하고,
오프라인이면 악보 대신 안내가 뜨고 재생은 브라우저 내장 음원으로 계속된다.

만든 곡과 올린 코퍼스는 `data/store.sqlite3` 에 남는다 — 서버를 껐다 켜도 사라지지 않는다
(`STORE_PERSIST=0` 이면 예전처럼 메모리만 쓴다).

```bash
cd server && ../.venv/bin/python -m uvicorn app.main:app --port 8000
# 다른 터미널에서
python3 -m http.server 8080 --directory web    # → http://localhost:8080/index.html
```

전체를 컨테이너로 띄우려면 `make up` (web · api · worker-py · db+pgvector · redis).

## API

```
POST /api/requests                                  요청 등록 → 하드 제약 + 실현 가능 난이도 대역
POST /api/requests/{id}/motifs                      Stage 1 모티브 후보
POST /api/requests/{id}/motifs/custom               원장이 직접 그린 모티브
POST /api/requests/{id}/motifs/{mid}/select         모티브 잠금 + Stage 2 설계 + 규칙 검사
PATCH /api/requests/{id}/plan                       원장이 고친 설계 재검사
POST /api/requests/{id}/realize                     Stage 3~5 실현·채점·비평 루프
GET  /api/compositions/{id}/musicxml|quality|measures
POST /api/compositions/{id}/judge                   모의 심사 3인
POST /api/recitals                                  연주회 순서·대비 검사·러닝타임

POST /api/corpus                                    참고 악보 업로드(MusicXML/MIDI) → StyleProfile
GET  /api/corpus · GET /api/corpus/{id}/profile     라이브러리 · 특징 벡터
POST /api/corpus/search?request_id=...              이 요청에 붙을 참고곡 미리보기
POST /api/compositions/{id}/guide                   §6.6 연주법 해설(4주 연습 계획·암보 구획)
POST /api/compositions/{id}/title                   제목 후보 3 + 추천
GET  /api/compositions/{id}/midi                    손별 트랙이 나뉜 MIDI

POST /api/feedback                                  원장 평가(👍/👎·이유 태그·손댄 마디)
GET  /api/feedback/stats                            '수정 없이 사용' 비율 · 보정 준비 여부
```

워크플로 순서는 URL 로 강제된다 — 모티브 없이 설계할 수 없고, 승인되지 않은 설계로
작곡할 수 없다.

## 콩쿨 입상에 대해

입상은 곡 · 학생의 연주 · 심사위원의 취향이 함께 만든다. **어떤 소프트웨어도 이를
보장할 수 없다.** 이 시스템이 하는 일은 입상 확률을 구조적으로 높이는 것이다 —
부문 규정을 어기지 않게 하고, 학생의 강점이 드러나는 구간을 설계하고, 심사위원이 듣는
첫 8마디와 클라이맥스와 마무리를 강하게 만들고, 모의 심사로 약점을 미리 찾고,
실제 대회 결과를 기록해 다음 곡에 반영한다.

대회마다 창작곡 허용 여부와 악보 제출 규정이 다르다. **곡을 만들기 전에 요강을 확인하고
콩쿨 프로필에 입력하라.** `original_allowed=false` 인 대회는 생성이 차단된다.
