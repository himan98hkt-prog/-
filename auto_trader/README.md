# Multi-Agent 주식 완전 자동매매 프로그램

한국투자증권(KIS) Open API로 **국내 주식**을 대상으로, Claude와 Gemini 두 AI의 **합의(Consensus)** 에 따라
매수/매도/관망을 결정하고 자동 실행하는 프로그램입니다.

> **현재 상태: Step 5(합의·리스크·주문) 완료.** 스케줄러 조립은 Step 6에서 진행합니다.

## 절대 규칙

1. **모의투자 우선** — 기본 도메인은 KIS 모의투자(`openapivts...:29443`). 실전 전환은 `.env`의 `KIS_ENV=REAL` 로만 가능.
2. **DRY_RUN 필수** — `DRY_RUN=true`면 주문 API를 호출하지 않고 로그·알림만 남깁니다.
3. **리스크 규칙 > AI 판단** — 리스크 규칙을 위반하는 주문은 AI가 강하게 권해도 실행하지 않습니다.
4. **AI 응답 파싱 실패 = HOLD**.
5. **프로그램은 죽지 않는다** — 종목·사이클 단위 예외를 모두 잡고, 치명적 오류만 알림 후 안전 종료.

## 빠른 시작

```bash
cd auto_trader
python -m venv .venv && source .venv/bin/activate     # Python 3.11+
pip install -r requirements.txt

cp .env.example .env        # 키 입력 (KIS_ENV=VTS, DRY_RUN=true 유지)
python -c "from config.loader import load; print(load())"   # 설정 검증 (비밀값 마스킹 출력)
python main.py              # 로깅 구성 + SQLite 스키마 생성 + 구성 요약

pytest                      # 단위 테스트 (외부 API는 전부 mock)
python scripts/test_kis.py      # 모의계좌 실연동 검증 (조회 + 1주 매수/매도)
python scripts/test_pipeline.py # 유니버스 → 스냅샷 수집 → data/snapshots/ 저장
python scripts/test_agents.py   # 스냅샷 → Claude·Gemini 병렬 분석
python scripts/test_cycle.py    # 한 종목 end-to-end (DRY_RUN 권장)
```

`ta` 설치가 `setup.py bdist_wheel` 오류로 실패하면 `pip install --use-pep517 ta` 로 설치하세요.

`scripts/test_kis.py` 는 토큰 캐시 → 시세·일봉·호가 → 잔고 → **1주 시장가 매수 → 체결 확인 → 1주 매도**
순으로 확인합니다. 조회만 하려면 `--no-order`, 종목을 바꾸려면 `--code 000660`.
실전(`KIS_ENV=REAL`)에서는 주문 단계를 자동으로 건너뜁니다.

`.env` 필수 키가 빠지면 **누락 항목을 한 번에 모아** 알려줍니다.

## 설정

| 파일 | 용도 |
|---|---|
| `.env` | 비밀값·실행 환경 (`KIS_ENV`, `DRY_RUN`, API 키). git 제외 |
| `config/settings.yaml` | 매매 파라미터 (유니버스·스케줄·리스크·AI) |
| `config/holidays.txt` | KRX 휴장일 (`YYYY-MM-DD` 한 줄씩, 선택 — 없거나 비면 주말만 제외하고 경고) |

주요 리스크 파라미터: 운용 총액 `total_investment_cap_krw`, 종목당 비중 `max_position_pct`,
동시 보유 `max_positions`, 당일 손실 한도 `daily_loss_limit_pct`, 손절 `stop_loss_pct`, 익절 `take_profit_pct`.

## 구조

```
auto_trader/
├── main.py                 진입점 (Step 1: 부트스트랩 / Step 6: 스케줄러)
├── config/loader.py        .env + settings.yaml 로드·검증 (비밀값 마스킹)
├── agents/                 Claude·Gemini 판단 엔진, 프롬프트, 스키마      (Step 4)
├── trading/                KIS 인증·API·주문 실행·장 운영일 판단          (Step 2, 5)
├── data_pipeline/          유니버스·시세/지표·뉴스 수집                   (Step 3)
├── logic/                  합의 엔진·리스크 규칙·포트폴리오               (Step 5)
├── utils/                  로거·DB·알림·재시도                            (Step 1, 2, 5)
├── data/                   trader.db, token.json, snapshots/  (git 제외)
└── logs/                   trader_YYYYMMDD.log (10MB × 5 회전, git 제외)
```

## KIS 연동 (Step 2)

| 모듈 | 역할 |
|---|---|
| `trading/kis_auth.py` | 토큰 발급·캐시(`data/token.json`)·갱신, hashkey, 공통 헤더, TR_ID 매핑 |
| `trading/kis_api.py` | 시세·잔고·주문 래퍼 + 초당 호출 제한 |
| `trading/market_calendar.py` | 장 운영일/시간 판단 (09:00–15:30 KST, 휴장일 파일) |

- **토큰은 만료 10분 전에만 재발급**합니다. KIS 발급 횟수 제한 때문에 매 실행 발급은 금지이며,
  환경(모의↔실전)이나 APP KEY가 바뀌면 캐시를 재사용하지 않습니다.
- **초당 호출 제한**: 모의 2건/초, 실전 19건/초(공식 20건에서 1건 여유)를 rate limiter가 강제합니다.
- **주문 API는 재시도하지 않습니다** — 중복 주문을 막기 위해, 실패 시 체결 조회로 상태를 확인합니다.
  조회 API만 `@retry(max=3, backoff=2)` 대상입니다.
- TR_ID는 `trading/kis_auth.py:TR_IDS` 한 곳에서 실전(`T`)/모의(`V`) 접두어로 매핑합니다.
  매수 `TTTC0802U`/`VTTC0802U`, 매도 `TTTC0801U`/`VTTC0801U`, 시장가 `ORD_DVSN=01`, 지정가 `00`.
- **거래량 순위 API는 모의투자 도메인에서 제공되지 않습니다.** VTS에서 호출하면 명확한
  `KisApiError`를 던지므로, 유니버스는 `watchlist` 모드를 사용하세요(Step 3에서 자동 폴백 처리).

## 데이터 파이프라인 (Step 3)

| 모듈 | 역할 |
|---|---|
| `data_pipeline/universe.py` | 매매 대상 종목 선정 → `data/universe_YYYYMMDD.json` |
| `data_pipeline/market_data.py` | 현재가·일봉 60일·호가 수집 + 지표 계산 → 고정 스키마 스냅샷 |
| `data_pipeline/news.py` | 네이버 뉴스 검색 (키 없거나 실패하면 빈 리스트) |

- **보유 종목은 유니버스 모드와 무관하게 항상 포함**되고 맨 앞에 옵니다(매도 판단 필요).
  `max_candidates_per_cycle` 상한은 후보에만 적용되고 보유 종목은 제외됩니다.
- 제외 키워드 중 한 글자(`우`)는 **우선주 접미사로만** 판정합니다 — `우리금융지주`처럼
  이름에 포함만 된 종목이 걸러지지 않도록 하기 위함입니다(`삼성전자우`, `현대차2우B`는 제외).
- `volume_rank` 모드에서 거래량 순위 API가 실패하면(모의투자 미지원) **`watchlist`로 자동 폴백**하고
  유니버스 파일에 `source: watchlist(fallback)`으로 기록합니다.
- 지표는 전부 `ta` 라이브러리로 계산합니다: MA5/20/60, RSI14, MACD(12,26,9), 볼린저(20,2),
  거래량 20일 평균 대비 배율. 데이터가 기간보다 짧거나 NaN이면 **0.0으로 접어** JSON 직렬화를 보장합니다.
- 호가·뉴스 수집 실패는 기본값으로 넘어가고, 현재가·일봉 실패만 예외로 올립니다(판단 근거가 없으므로).

## AI 에이전트 (Step 4)

| 모듈 | 역할 |
|---|---|
| `agents/schemas.py` | `AgentDecision` + 응답 검증(범위 clamp, 형식 오류는 예외) |
| `agents/prompts.py` | 시스템/유저 프롬프트와 응답 JSON 스키마 (한 곳에서 관리) |
| `agents/base_agent.py` | 호출 → JSON 추출 → 검증 → 재요청 → HOLD 폴백, 병렬 실행 |
| `agents/claude_agent.py` | Claude (anthropic SDK, Structured Outputs) |
| `agents/gemini_agent.py` | Gemini (google-genai SDK, `response_mime_type=application/json`) |

- **파싱 실패 = HOLD**: 마크다운 코드블록·설명문이 섞이면 첫 `{`~마지막 `}` 만 잘라 파싱하고,
  그래도 실패하면 "JSON만 출력"을 재강조해 `max_retries` 까지 재요청합니다.
  끝내 실패하면 `ok=False`인 HOLD를 반환합니다 — 호출 실패·타임아웃도 동일합니다.
- 두 에이전트는 `concurrent.futures` 로 **병렬 호출**하며, 시작 시점 기준 공통 마감시각으로
  각자 `timeout_sec` 을 갖습니다. 한쪽이 타임아웃·예외로 죽어도 다른 쪽 결과는 살아남습니다.
- 응답 형식은 프롬프트뿐 아니라 **API 차원에서도 강제**합니다(Claude: `output_config.format`
  json_schema / Gemini: `response_schema`). 프롬프트 지시만으로 기대하지 않습니다.

### `temperature` 에 대한 주의

지시서는 Claude에 `temperature=0.2` 를 지정하도록 되어 있으나, **Sonnet 5·Opus 5 등 최신 모델은
`temperature` 파라미터를 거부(HTTP 400)합니다.** 그래서 `CLAUDE_TEMPERATURE` 는 기본적으로 비워 두고
아예 전송하지 않습니다. 구형 모델을 쓸 때만 값을 넣으세요. 값이 설정된 채 모델이 거부하면
경고 로그를 남기고 파라미터를 뺀 뒤 한 번 재시도합니다. Gemini는 `temperature` 를 지원하므로
`GEMINI_TEMPERATURE`(기본 0.2)가 그대로 적용됩니다.

AI 호출 비용은 `CLAUDE_EFFORT`(low/medium/high/xhigh/max)와 `universe.max_candidates_per_cycle`
로 조절합니다.

## 합의·리스크·주문 (Step 5)

| 모듈 | 역할 |
|---|---|
| `logic/decision_maker.py` | 두 AI 판단 → 최종 행동 (합의 매트릭스) |
| `logic/risk_manager.py` | 매수 7개 규칙 + 강제 청산 판정 |
| `logic/portfolio.py` | KIS 잔고 동기화, 주문·결정 기록, 체결 대기 |
| `trading/order_executor.py` | 수량 계산 → 주문 → 체결 확인 → 기록 → 알림 |
| `utils/notifier.py` | 텔레그램/디스코드 알림 (4,096자 분할) |

### 합의 매트릭스

| Claude \\ Gemini | BUY | HOLD | SELL |
|---|---|---|---|
| **BUY** | STRONG_BUY (둘 다 confidence ≥ `min_confidence`) / 아니면 BUY_SMALL | HOLD | HOLD (보유 시 REDUCE) |
| **HOLD** | HOLD | HOLD | HOLD (보유 시 REDUCE) |
| **SELL** | HOLD (보유 시 REDUCE) | HOLD (보유 시 REDUCE) | SELL_ALL (보유 시) |

- 한쪽이라도 파싱 실패(`ok=False`)면 **무조건 HOLD** — 만장일치 매도라도 실행하지 않습니다.
- 미보유 종목의 SELL/REDUCE는 HOLD로 치환합니다.
- `STRONG_BUY` 비중 = 두 AI 권장 비중의 평균, `BUY_SMALL` = 그 절반. 상한은 `max_position_pct`.
- `REDUCE` = 보유수량의 50%, `SELL_ALL` = 전량.

### 리스크 규칙 (AI 판단보다 상위)

1. 총 투자액 + 신규 금액 ≤ `total_investment_cap_krw`
2. 종목 금액(기보유분 포함) ≤ 총액 × `max_position_pct`
3. 보유 종목 수 < `max_positions` (보유 종목 추가매수는 허용)
4. 당일 손익 > `-daily_loss_limit_pct`
5. 현재 시각 ≤ `last_new_buy`
6. 주문 금액 ≥ `min_order_krw`
7. 동일 종목 당일 매수 1회

거부 사유는 로그와 텔레그램 사이클 요약에 그대로 실립니다.
**손절선 도달은 AI 판단 없이 즉시 전량 매도**하고, 익절선 도달은 플래그로 합의 엔진에 전달해
AI가 응답하지 않으면 절반 매도합니다.

### 주문

- `DRY_RUN=true` 면 주문 API를 호출하지 않고 `[DRY_RUN]` 로그·알림만 남기며, `orders` 테이블에
  `dry_run=1` 로 기록합니다.
- 매수 수량 = `floor(min(가용현금, 총액×비중%) / 현재가)` — 0주면 스킵합니다.
- 체결은 최대 30초 동안 5초 간격으로 확인하고, **지정가 미체결은 취소**, 시장가 미체결은
  다음 사이클에서 재조회합니다.

## 데이터베이스 (`data/trader.db`)

| 테이블 | 내용 |
|---|---|
| `positions` | 보유 포지션 스냅샷 (매 사이클 KIS 잔고로 동기화) |
| `orders` | 주문·체결 내역 (DRY_RUN 주문 포함, `dry_run`·`kis_env` 컬럼으로 구분) |
| `decisions` | AI 원문 응답 + 파싱 결과 + 최종 결정 + 리스크 판정 (사후 검증용) |
| `daily_pnl` | 일자별 손익 요약 |

## 로깅

- `logs/trader_YYYYMMDD.log` — 10MB 롤링 5개, 콘솔 동시 출력, 시각은 항상 KST.
- `utils.logger.register_secret()` 에 등록한 값은 모든 로그에서 `***REDACTED***` 로 치환됩니다.

## 개발 단계

| Step | 범위 | 상태 |
|---|---|---|
| 1 | 뼈대: 구조·설정 로더·로거·DB 스키마 | ✅ 완료 |
| 2 | KIS 연동 (토큰 캐시, 시세/잔고/주문 API, 장 운영일) | ✅ 코드·테스트 완료 / 모의계좌 실연동 검증 대기 |
| 3 | 데이터 파이프라인 (유니버스·지표·뉴스) | ✅ 코드·테스트 완료 / 실연동 검증 대기 |
| 4 | AI 에이전트 (Claude/Gemini 병렬 호출·JSON 파싱) | ✅ 코드·테스트 완료 / 실API 검증 대기 |
| 5 | 합의·리스크·주문 실행·알림 | ✅ 코드·테스트 완료 / 실연동 검증 대기 |
| 6 | 스케줄러 조립 (apscheduler, 시그널, 일간 리포트) | 대기 |
| 7 | 모의투자 실주문 검증 (5거래일 무인 운영) | 대기 |

각 Step은 완료 후 사용자 확인을 받고 다음 단계로 넘어갑니다.

## 범위 밖

백테스팅, 해외주식, 선물/옵션, 신용거래, 웹 대시보드는 이번 개발 범위에 포함하지 않습니다.
